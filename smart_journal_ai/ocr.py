import hashlib
import os
import re
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


def _safe_read_pdf_text(path):
    text_chunks = []
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if text:
                text_chunks.append(text)
    return "\n".join(text_chunks)


def _safe_read_image_text(path):
    if not os.system("which tesseract >/dev/null 2>&1") == 0:
        return ""
    image = Image.open(path)
    return pytesseract.image_to_string(image, lang="jpn+eng")


def read_document_text(file_path):
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return _safe_read_pdf_text(file_path)
    if suffix in {".png", ".jpg", ".jpeg"}:
        return _safe_read_image_text(file_path)
    if suffix == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    return ""


def _extract_amounts(text):
    numbers = re.findall(r"[0-9,]+(?:\.[0-9]+)?", text.replace("、", ""))
    values = [float(value.replace(",", "")) for value in numbers if value]
    if not values:
        return 0, 0, 0, 0
    total = max(values)
    tax = 0
    for value in values:
        if value < total and value > 0:
            tax = max(tax, total - value)
    excluding_tax = total - tax if tax else total
    return excluding_tax, tax, total, 10


def extract_document_fields(file_path):
    text = read_document_text(file_path)
    vendor = "不明"
    description = "未記載"
    invoice_number = "不明"
    transaction_date = "不明"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        vendor = lines[0][:80] if lines[0] else vendor
    for pattern in [r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", r"(\d{4}/\d{1,2}/\d{1,2})"]:
        match = re.search(pattern, text)
        if match:
            transaction_date = match.group(1).replace("/", "-")
            break
    if "請求書" in text or "領収書" in text:
        description = "取引明細" if "明細" in text else "取引内容"
    excluding_tax, tax_amount, including_tax, tax_rate = _extract_amounts(text)
    file_hash = hashlib.md5(Path(file_path).read_bytes()).hexdigest()
    return {
        "document_type": "請求書" if "請求" in text else "領収書",
        "vendor_name": vendor,
        "description": description,
        "invoice_number": invoice_number,
        "transaction_date": transaction_date,
        "amount_excluding_tax": excluding_tax,
        "tax_amount": tax_amount,
        "amount_including_tax": including_tax,
        "tax_rate": tax_rate,
        "source_text": text[:4000],
        "hash": file_hash,
    }
