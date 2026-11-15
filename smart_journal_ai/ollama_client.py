import json
import re
import shutil
import subprocess

from .ai_schema import AIJudgmentResult


def is_ollama_available():
    return shutil.which("ollama") is not None


def fetch_ollama_decision(extraction):
    if not is_ollama_available():
        return None
    try:
        prompt = f"""
次の証憑情報をもとに、会計仕訳の候補をJSONのみで返してください。
- 取引先: {extraction.get('vendor_name', '不明')}
- 取引内容: {extraction.get('description', '不明')}
- 証憑種別: {extraction.get('document_type', '請求書')}
- 税抜金額: {extraction.get('amount_excluding_tax', 0)}
- 税込金額: {extraction.get('amount_including_tax', 0)}
- 取引日: {extraction.get('transaction_date', '不明')}
- 根拠: {extraction.get('source_text', '')[:1000]}

返すJSONキー: debit_account, credit_account, debit_amount, credit_amount, reason, evidence, alternative, review_priority
"""
        result = subprocess.run(
            ["ollama", "run", "llama3.1:8b-instruct", prompt],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        if result.returncode != 0:
            return None
        stdout = result.stdout.strip()
        if not stdout:
            return None
        match = re.search(r"```json\s*(.*?)\s*```", stdout, re.S)
        if match:
            stdout = match.group(1)
        payload = json.loads(stdout)
        validated = AIJudgmentResult.model_validate(payload)
        return {
            "debit_account": validated.debit_account,
            "credit_account": validated.credit_account,
            "debit_amount": validated.debit_amount,
            "credit_amount": validated.credit_amount,
            "reason": validated.reason,
            "evidence": validated.evidence or extraction.get("source_text", ""),
            "alternative": validated.alternative,
            "review_priority": validated.review_priority,
        }
    except (json.JSONDecodeError, ValueError, subprocess.TimeoutExpired, OSError):
        return None
