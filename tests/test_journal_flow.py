from smart_journal_ai.db import (
    save_journal_entry,
    fetch_approved_journal_rows,
    fetch_journal_history_rows,
    save_journal_history,
)
from smart_journal_ai.engine import (
    estimate_journal_entry,
    detect_duplicate_document,
    export_approved_journal_csv,
    build_review_summary,
)
from smart_journal_ai.ocr import extract_document_fields


def test_rule_based_office_supplies():
    extraction = {
        "document_type": "請求書",
        "vendor_name": "文房具屋",
        "description": "事務用品一式",
        "amount_excluding_tax": 5500,
        "tax_amount": 550,
        "amount_including_tax": 6050,
        "tax_rate": 10,
    }

    result = estimate_journal_entry(extraction, accounting_policy={"tax_method": "tax_included"})

    assert result["method"] == "rule"
    assert result["debit_account"] == "消耗品費"
    assert result["credit_account"] == "買掛金"
    assert result["debit_amount"] == 5500
    assert result["credit_amount"] == 5500


def test_detect_duplicate_document():
    first = {"hash": "abc123", "vendor_name": "ABC商事"}
    second = {"hash": "abc123", "vendor_name": "ABC商事"}

    assert detect_duplicate_document([first], second) is True


def test_csv_export_has_expected_columns():
    rows = [{
        "transaction_date": "2026-11-10",
        "debit_account": "消耗品費",
        "debit_amount": 5500,
        "debit_tax_class": "10%",
        "credit_account": "買掛金",
        "credit_amount": 5500,
        "credit_tax_class": "10%",
        "summary": "文房具購入",
        "document_id": "DOC-001",
    }]

    csv_text = export_approved_journal_csv(rows)

    assert "取引日" in csv_text
    assert "借方科目" in csv_text
    assert "貸方科目" in csv_text
    assert "証憑ID" in csv_text
    assert "DOC-001" in csv_text


def test_ollama_disabled_falls_back_to_rule_only():
    extraction = {
        "document_type": "領収書",
        "vendor_name": "電車駅",
        "description": "定期券",
        "amount_excluding_tax": 12000,
        "tax_amount": 0,
        "amount_including_tax": 12000,
        "tax_rate": 0,
    }

    result = estimate_journal_entry(extraction, accounting_policy={"tax_method": "tax_excluded"}, ai_enabled=False)

    assert result["method"] == "rule"
    assert result["debit_account"] == "旅費交通費"
    assert result["credit_account"] == "現金"


def test_db_fetches_approved_journal_rows_for_csv_export():
    save_journal_entry(99, {
        "transaction_date": "2026-11-10",
        "debit_account": "消耗品費",
        "debit_amount": 5500,
        "debit_tax_class": "10%",
        "credit_account": "買掛金",
        "credit_amount": 5500,
        "credit_tax_class": "10%",
        "summary": "文房具購入",
        "method": "rule",
        "status": "approved",
        "evidence": "証憑"
    })

    rows = fetch_approved_journal_rows()
    assert any(row["debit_account"] == "消耗品費" for row in rows)

    csv_text = export_approved_journal_csv(rows)
    assert "文房具購入" in csv_text


def test_fetch_journal_history_rows_returns_latest_review_reason():
    save_journal_history(
        "文房具屋",
        "事務用品一式",
        {"debit_account": "消耗品費", "credit_account": "買掛金"},
        {"debit_account": "消耗品費", "credit_account": "買掛金"},
        "事務用品と見積もりが一致したため",
        "標準方針",
    )

    history = fetch_journal_history_rows()
    assert history
    assert any(row["vendor_name"] == "文房具屋" for row in history)
    assert any("事務用品と見積もりが一致したため" in str(row["reason"]) for row in history)


def test_estimate_uses_similar_history_as_evidence():
    save_journal_history(
        "文房具屋",
        "事務用品一式",
        {"debit_account": "消耗品費", "credit_account": "買掛金"},
        {"debit_account": "消耗品費", "credit_account": "買掛金"},
        "過去の同種取引と一致したため",
        "標準方針",
    )

    extraction = {
        "document_type": "請求書",
        "vendor_name": "文房具屋",
        "description": "事務用品一式",
        "amount_excluding_tax": 5500,
        "tax_amount": 550,
        "amount_including_tax": 6050,
        "tax_rate": 10,
    }

    result = estimate_journal_entry(extraction, accounting_policy={"tax_method": "tax_included"}, ai_enabled=False)

    assert result["history_match"] is True
    assert "類似履歴" in result["reason"]


def test_build_review_summary_detects_balancing_and_evidence():
    extraction = {
        "document_type": "請求書",
        "vendor_name": "文房具屋",
        "description": "事務用品一式",
        "amount_excluding_tax": 5500,
        "tax_amount": 550,
        "amount_including_tax": 6050,
        "tax_rate": 10,
        "source_text": "取引明細: 文房具一式 6050円",
    }
    suggestion = {
        "debit_account": "消耗品費",
        "debit_amount": 5500,
        "credit_account": "買掛金",
        "credit_amount": 5500,
        "history_match": True,
        "reason": "類似履歴に基づく補正を反映しました。",
    }

    summary = build_review_summary(extraction, suggestion)

    assert summary["balanced"] is True
    assert summary["risk_level"] in {"低", "中"}
    assert "証憑" in summary["evidence_summary"]
    assert summary["history_used"] is True


def test_extract_document_fields_handles_missing_file_without_crashing():
    result = extract_document_fields("/tmp/does-not-exist.pdf")

    assert result["document_type"] in {"請求書", "領収書", "不明"}
    assert result["vendor_name"] == "不明"
    assert result["description"] == "未記載"
    assert result["source_text"] == ""
