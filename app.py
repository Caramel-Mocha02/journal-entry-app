import os
from pathlib import Path

import streamlit as st

from smart_journal_ai.db import (
    init_db,
    save_document,
    save_extraction,
    save_journal_entry,
    save_journal_history,
    fetch_similar_history,
    fetch_approved_journal_rows,
    fetch_journal_history_rows,
)
from smart_journal_ai.engine import estimate_journal_entry, detect_duplicate_document, export_approved_journal_csv
from smart_journal_ai.ocr import extract_document_fields
from smart_journal_ai.ollama_client import is_ollama_available
from smart_journal_ai.rules import add_rule, load_rules


st.set_page_config(page_title="Smart Journal AI", layout="wide")

init_db()

st.title("Smart Journal AI")
st.caption("ローカル証憑から仕訳案を自動生成するハイブリッドAIアプリ")

with st.sidebar:
    st.header("環境")
    st.write(f"Ollama利用可否: {'OK' if is_ollama_available() else '未導入'}")
    st.write("AIはローカルLLMのみ使用。クラウド送信は行いません。")

    st.header("CSV出力")
    rows = fetch_approved_journal_rows()
    if rows:
        csv_text = export_approved_journal_csv(rows)
        st.download_button(
            label="承認済み仕訳をCSV出力",
            data=csv_text,
            file_name="approved_journal.csv",
            mime="text/csv",
        )
    else:
        st.caption("承認済み仕訳はまだありません")

    st.header("レビュー履歴")
    review_history = fetch_journal_history_rows(5)
    if review_history:
        for item in review_history:
            st.caption(f"{item['vendor_name']} / {item['description']}")
            st.write(f"理由: {item['reason']}")
            st.write(f"修正後: {item['revised_entry']}")
    else:
        st.caption("承認レビューはまだありません")

    st.header("仕訳ルール設定")
    current_rules = load_rules()
    for rule in current_rules:
        st.caption(f"{rule['debit_account']} / キーワード: {rule['keywords']}")
    with st.form("rule_form"):
        keywords = st.text_input("キーワード")
        debit_account = st.text_input("借方科目")
        credit_account = st.text_input("貸方科目", value="買掛金")
        submit_rule = st.form_submit_button("ルールを追加")
        if submit_rule and keywords and debit_account:
            add_rule(keywords, debit_account, credit_account, "ユーザー追加")
            st.success("ルールを保存しました。")
            st.rerun()

uploaded_files = st.file_uploader(
    "証憑をアップロード",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

if uploaded_files:
    os.makedirs("data/uploads", exist_ok=True)
    for uploaded_file in uploaded_files:
        try:
            file_bytes = uploaded_file.read()
            target_path = Path("data/uploads") / uploaded_file.name
            target_path.write_bytes(file_bytes)
            extracted = extract_document_fields(str(target_path))

            duplicate = detect_duplicate_document(
                [{"hash": extracted.get("hash")}],
                {"hash": extracted.get("hash")},
            )
            if duplicate:
                st.warning(f"{uploaded_file.name} は重複証憑として検出されました。")

            document_id = save_document(uploaded_file.name, extracted.get("hash"), extracted.get("document_type"))
            save_extraction(document_id, extracted)

            suggestion = estimate_journal_entry(
                extracted,
                accounting_policy={"tax_method": "tax_included"},
                ai_enabled=True,
            )
            similar_history = fetch_similar_history(
                extracted.get("vendor_name", "不明"),
                extracted.get("description", "取引"),
            )
            st.subheader(f"{uploaded_file.name}")
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("### 抽出情報")
                st.json({
                    "証憑種別": extracted.get("document_type"),
                    "取引先": extracted.get("vendor_name"),
                    "取引内容": extracted.get("description"),
                    "取引日": extracted.get("transaction_date"),
                    "税抜金額": extracted.get("amount_excluding_tax"),
                    "消費税": extracted.get("tax_amount"),
                    "税込金額": extracted.get("amount_including_tax"),
                    "税率": extracted.get("tax_rate"),
                })
                st.text_area("証憑原文（抜粋）", extracted.get("source_text", "")[:2000], height=220)

            with col_right:
                st.markdown("### 仕訳案")
                st.info(f"確認推奨度: {suggestion.get('review_priority', '中')}")
                st.json({
                    "借方科目": suggestion.get("debit_account"),
                    "借方金額": suggestion.get("debit_amount"),
                    "貸方科目": suggestion.get("credit_account"),
                    "貸方金額": suggestion.get("credit_amount"),
                    "方法": suggestion.get("method"),
                    "履歴参照": suggestion.get("history_match", False),
                    "理由": suggestion.get("reason"),
                    "確認事項": suggestion.get("review_flags", []),
                })
                st.markdown("### 監査証跡")
                review_summary = suggestion.get("review_summary") or {}
                st.json({
                    "状態": review_summary.get("status", "要確認"),
                    "リスク": review_summary.get("risk_level", "中"),
                    "借貸一致": review_summary.get("balanced", False),
                    "税額整合": review_summary.get("tax_consistent", False),
                    "履歴利用": review_summary.get("history_used", False),
                    "証拠": review_summary.get("evidence_summary", "証拠不明"),
                    "理由一覧": review_summary.get("reasons", []),
                })
                st.write(f"判断根拠: {suggestion.get('reason', 'なし')}")
                st.write(f"確認項目: {suggestion.get('review_flags', []) or 'なし'}")
                if suggestion.get("history_match"):
                    st.caption("類似履歴を参照して補正を反映しました。")
                st.markdown("### 過去の類似仕訳")
                if similar_history:
                    for item in similar_history:
                        st.caption(f"{item['vendor_name']} / {item['description']}")
                        st.write(item['revised_entry'])
                        st.write(f"理由: {item['reason']}")
                else:
                    st.write("類似履歴はまだありません。")
                with st.form(key=f"entry_{document_id}"):
                    debit_account = st.text_input("借方科目", value=suggestion.get("debit_account"))
                    credit_account = st.text_input("貸方科目", value=suggestion.get("credit_account"))
                    debit_amount = st.number_input("借方金額", value=float(suggestion.get("debit_amount", 0)))
                    credit_amount = st.number_input("貸方金額", value=float(suggestion.get("credit_amount", 0)))
                    summary = st.text_input("摘要", value=suggestion.get("summary", "取引"))
                    if st.form_submit_button("承認して保存"):
                        save_journal_entry(document_id, {
                            "transaction_date": extracted.get("transaction_date"),
                            "debit_account": debit_account,
                            "debit_amount": debit_amount,
                            "credit_account": credit_account,
                            "credit_amount": credit_amount,
                            "summary": summary,
                            "method": suggestion.get("method", "rule"),
                            "status": "approved",
                            "evidence": suggestion.get("evidence", ""),
                        })
                        save_journal_history(
                            extracted.get("vendor_name", "不明"),
                            extracted.get("description", "取引"),
                            {
                                "debit_account": suggestion.get("debit_account"),
                                "credit_account": suggestion.get("credit_account"),
                                "debit_amount": suggestion.get("debit_amount"),
                                "credit_amount": suggestion.get("credit_amount"),
                            },
                            {
                                "debit_account": debit_account,
                                "credit_account": credit_account,
                                "debit_amount": debit_amount,
                                "credit_amount": credit_amount,
                            },
                            suggestion.get("reason", "ユーザー承認"),
                            "標準方針",
                        )
                        st.success("仕訳を承認済みとして保存しました。")

            st.markdown("---")
        except Exception as exc:
            st.error(f"{uploaded_file.name} の解析中にエラーが発生しました。ファイル形式や内容を確認してください。")
            st.warning("リロードして再試行してください。")
            st.code(str(exc))
            continue
