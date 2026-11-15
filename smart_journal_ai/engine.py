import ast
import csv
import io

from .db import fetch_similar_history
from .ollama_client import is_ollama_available, fetch_ollama_decision
from .rules import load_rules


RULES = [
    {
        "keywords": ["文房具", "ノート", "ペン", "紙", "封筒", "事務用品", "消耗品"],
        "debit_account": "消耗品費",
    },
    {
        "keywords": ["電車", "定期券", "駅", "旅費", "交通"],
        "debit_account": "旅費交通費",
    },
    {
        "keywords": ["電話", "通信", "インターネット", "ネット", "プロバイダ"],
        "debit_account": "通信費",
    },
    {
        "keywords": ["広告", "宣伝", "掲載", "CM"],
        "debit_account": "広告宣伝費",
    },
    {
        "keywords": ["賃料", "家賃", "地代", "貸借"],
        "debit_account": "地代家賃",
    },
]


def detect_duplicate_document(existing_documents, candidate_document):
    candidate_hash = candidate_document.get("hash")
    if not candidate_hash:
        return False
    return any(item.get("hash") == candidate_hash for item in existing_documents)


def _default_credit(doc_type):
    return "買掛金" if str(doc_type or "").startswith("請求") else "現金"


def _rule_account_for(extraction):
    text = " ".join(
        filter(
            None,
            [
                extraction.get("vendor_name", ""),
                extraction.get("description", ""),
                extraction.get("document_type", ""),
            ],
        )
    )
    lowered = text.lower()
    rules = load_rules()
    if rules:
        for rule in rules:
            keywords = (rule.get("keywords") or "").split(",")
            if any(keyword.strip().lower() in lowered for keyword in keywords if keyword.strip()):
                return rule.get("debit_account") or "雑費"
    for rule in RULES:
        if any(keyword.lower() in lowered for keyword in rule["keywords"]):
            return rule["debit_account"]
    return "雑費"


def _review_priority(extraction):
    text = " ".join(filter(None, [extraction.get("vendor_name", ""), extraction.get("description", ""), extraction.get("source_text", "")]))
    flags = []
    if extraction.get("transaction_date") in (None, "", "不明"):
        flags.append("取引日が不明")
    if extraction.get("amount_excluding_tax") in (None, 0):
        flags.append("金額が不足")
    if any(keyword in text for keyword in ["PC", "パソコン", "設備", "固定資産", "機器", "サーバー"]):
        flags.append("固定資産の可能性")
    if len(flags) >= 2:
        return "高", flags
    if flags:
        return "中", flags
    return "低", []


def _similar_history_context(extraction):
    vendor_name = (extraction.get("vendor_name") or "").strip()
    description = (extraction.get("description") or "").strip()
    if not vendor_name and not description:
        return False, None

    history = fetch_similar_history(vendor_name, description)
    if not history:
        return False, None

    latest = history[0]
    revised_entry = latest.get("revised_entry") or "{}"
    parsed_entry = revised_entry
    if isinstance(revised_entry, str):
        try:
            parsed_entry = ast.literal_eval(revised_entry)
        except (ValueError, SyntaxError):
            parsed_entry = {}

    if not isinstance(parsed_entry, dict):
        parsed_entry = {}

    debit_account = parsed_entry.get("debit_account")
    credit_account = parsed_entry.get("credit_account")
    reason = latest.get("reason") or "過去の類似取引を参照しました。"
    return True, {
        "debit_account": debit_account,
        "credit_account": credit_account,
        "reason": reason,
    }


def build_review_summary(extraction, suggestion):
    debit_amount = suggestion.get("debit_amount") or 0
    credit_amount = suggestion.get("credit_amount") or 0
    tax_rate = extraction.get("tax_rate")
    source_text = extraction.get("source_text") or ""
    amount_excluding_tax = extraction.get("amount_excluding_tax")
    amount_including_tax = extraction.get("amount_including_tax")

    balanced = abs(float(debit_amount) - float(credit_amount)) < 0.01
    tax_consistent = True
    if amount_excluding_tax is not None and amount_including_tax is not None and tax_rate not in (None, ""):
        expected = float(amount_excluding_tax) * (1 + float(tax_rate) / 100)
        tax_consistent = abs(expected - float(amount_including_tax)) < 1.0

    reasons = []
    if balanced:
        reasons.append("借貸一致")
    else:
        reasons.append("借貸不一致")
    if tax_consistent:
        reasons.append("税額整合")
    else:
        reasons.append("税額要確認")
    if suggestion.get("history_match"):
        reasons.append("類似履歴参照")

    risk_level = "低"
    if not balanced or not tax_consistent:
        risk_level = "中"
    if not balanced and not tax_consistent:
        risk_level = "高"

    return {
        "balanced": balanced,
        "tax_consistent": tax_consistent,
        "risk_level": risk_level,
        "history_used": bool(suggestion.get("history_match")),
        "evidence_summary": "証憑原文と過去履歴を根拠に判定" if source_text else "証憑情報が少ないため確認が必要",
        "status": "要確認" if risk_level != "低" else "正常",
        "reasons": reasons,
    }


def estimate_journal_entry(extraction, accounting_policy=None, ai_enabled=True):
    accounting_policy = accounting_policy or {"tax_method": "tax_included"}
    doc_type = extraction.get("document_type", "請求書")
    debit_account = _rule_account_for(extraction)
    credit_account = _default_credit(doc_type)
    tax_method = accounting_policy.get("tax_method", "tax_included")
    base_amount = extraction.get("amount_excluding_tax")
    if base_amount is None:
        base_amount = extraction.get("amount_including_tax") or 0
    if tax_method == "tax_excluded":
        debit_amount = base_amount
    else:
        debit_amount = base_amount or 0
    review_level, review_flags = _review_priority(extraction)
    history_match, history_context = _similar_history_context(extraction)
    result = {
        "debit_account": debit_account,
        "credit_account": credit_account,
        "debit_amount": debit_amount,
        "credit_amount": debit_amount,
        "method": "rule",
        "summary": extraction.get("description") or "取引",
        "tax_class": extraction.get("tax_rate", 10),
        "reason": "規定ルールと取引内容の一致を確認したため、ルールベースで仕訳案を作成しました。",
        "evidence": extraction.get("source_text", ""),
        "review_priority": review_level,
        "review_flags": review_flags,
        "history_match": history_match,
    }

    if history_match and history_context:
        if history_context.get("debit_account"):
            result["debit_account"] = history_context["debit_account"]
        if history_context.get("credit_account"):
            result["credit_account"] = history_context["credit_account"]
        result["reason"] = (
            "類似履歴に基づく補正を反映しました。"
            f"{history_context.get('reason', '過去の取引と整合しています。')} "
            "規定ルールと取引内容の一致を確認したため、ルールベースで仕訳案を作成しました。"
        )

    result["review_summary"] = build_review_summary(extraction, result)

    if ai_enabled and is_ollama_available():
        ai_result = fetch_ollama_decision(extraction)
        if ai_result:
            result["method"] = "ai"
            result["debit_account"] = ai_result.get("debit_account", result["debit_account"])
            result["credit_account"] = ai_result.get("credit_account", result["credit_account"])
            result["reason"] = ai_result.get("reason", result["reason"])
            result["evidence"] = ai_result.get("evidence", result["evidence"]) or result["evidence"]
            result["review_summary"] = build_review_summary(extraction, result)

    return result


def export_approved_journal_csv(rows):
    fieldnames = [
        "取引日",
        "借方科目",
        "借方金額",
        "借方税区分",
        "貸方科目",
        "貸方金額",
        "貸方税区分",
        "摘要",
        "証憑ID",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "取引日": row.get("transaction_date", ""),
            "借方科目": row.get("debit_account", ""),
            "借方金額": row.get("debit_amount", 0),
            "借方税区分": row.get("debit_tax_class", ""),
            "貸方科目": row.get("credit_account", ""),
            "貸方金額": row.get("credit_amount", 0),
            "貸方税区分": row.get("credit_tax_class", ""),
            "摘要": row.get("summary", ""),
            "証憑ID": row.get("document_id", ""),
        })
    return "\ufeff" + buffer.getvalue()
