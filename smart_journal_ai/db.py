import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "smart_journal_ai.db"


def _initialize_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            file_hash TEXT,
            document_type TEXT,
            upload_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'uploaded'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            vendor_name TEXT,
            description TEXT,
            invoice_number TEXT,
            transaction_date TEXT,
            amount_excluding_tax REAL,
            tax_amount REAL,
            amount_including_tax REAL,
            tax_rate REAL,
            source_text TEXT,
            metadata TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            transaction_date TEXT,
            debit_account TEXT,
            debit_amount REAL,
            debit_tax_class TEXT,
            credit_account TEXT,
            credit_amount REAL,
            credit_tax_class TEXT,
            summary TEXT,
            method TEXT,
            status TEXT DEFAULT 'draft',
            evidence TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS accounting_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            tax_method TEXT,
            default_currency TEXT,
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keywords TEXT,
            debit_account TEXT,
            credit_account TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS journal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT,
            description TEXT,
            original_entry TEXT,
            revised_entry TEXT,
            reason TEXT,
            modified_at TEXT DEFAULT CURRENT_TIMESTAMP,
            approved_at TEXT,
            accounting_policy TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO accounting_policies (id, name, tax_method, default_currency, notes)
        VALUES (1, '標準方針', 'tax_included', 'JPY', '通常の税込経理')
        """
    )
    default_rules = [
        ("文房具,ノート,ペン,紙,封筒,事務用品,消耗品", "消耗品費", "買掛金", "文房具等の事務用品"),
        ("電車,定期券,駅,旅費,交通", "旅費交通費", "現金", "交通費"),
        ("電話,通信,インターネット,ネット,プロバイダ", "通信費", "買掛金", "通信費"),
        ("広告,宣伝,掲載,CM", "広告宣伝費", "買掛金", "広告掲載"),
        ("賃料,家賃,地代,貸借", "地代家賃", "現金", "賃料")
    ]
    for keywords, debit_account, credit_account, notes in default_rules:
        conn.execute(
            "INSERT OR IGNORE INTO rules (keywords, debit_account, credit_account, notes) VALUES (?, ?, ?, ?)",
            (keywords, debit_account, credit_account, notes),
        )


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _initialize_schema(conn)
    return conn


def init_db():
    with get_connection() as conn:
        pass
    return DB_PATH


def save_document(file_name, file_hash, document_type):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO documents (file_name, file_hash, document_type) VALUES (?, ?, ?)",
            (file_name, file_hash, document_type),
        )
        return cursor.lastrowid


def save_extraction(document_id, payload):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ocr_extractions (
                document_id, vendor_name, description, invoice_number, transaction_date,
                amount_excluding_tax, tax_amount, amount_including_tax, tax_rate, source_text, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                payload.get("vendor_name"),
                payload.get("description"),
                payload.get("invoice_number"),
                payload.get("transaction_date"),
                payload.get("amount_excluding_tax"),
                payload.get("tax_amount"),
                payload.get("amount_including_tax"),
                payload.get("tax_rate"),
                payload.get("source_text"),
                str(payload),
            ),
        )


def save_journal_entry(document_id, payload):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO journal_entries (
                document_id, transaction_date, debit_account, debit_amount, debit_tax_class,
                credit_account, credit_amount, credit_tax_class, summary, method, status, evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                payload.get("transaction_date"),
                payload.get("debit_account"),
                payload.get("debit_amount"),
                payload.get("debit_tax_class", "10%"),
                payload.get("credit_account"),
                payload.get("credit_amount"),
                payload.get("credit_tax_class", "10%"),
                payload.get("summary"),
                payload.get("method", "rule"),
                payload.get("status", "draft"),
                payload.get("evidence", ""),
            ),
        )
        return cursor.lastrowid


def fetch_approved_journal_rows():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT transaction_date, debit_account, debit_amount, debit_tax_class,
                   credit_account, credit_amount, credit_tax_class, summary, document_id
            FROM journal_entries WHERE status = 'approved' ORDER BY id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def save_journal_history(vendor_name, description, original_entry, revised_entry, reason, accounting_policy):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO journal_history (vendor_name, description, original_entry, revised_entry, reason, accounting_policy, approved_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (vendor_name, description, str(original_entry), str(revised_entry), reason, accounting_policy),
        )


def fetch_similar_history(vendor_name, description, policy_name=None):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM journal_history WHERE vendor_name = ? OR description = ? ORDER BY approved_at DESC LIMIT 5",
            (vendor_name, description),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_journal_history_rows(limit=10):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM journal_history ORDER BY approved_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
