from .db import get_connection, init_db

DEFAULT_RULES = [
    {
        "keywords": ["文房具", "ノート", "ペン", "紙", "封筒", "事務用品", "消耗品"],
        "debit_account": "消耗品費",
        "credit_account": "買掛金",
        "notes": "文房具等の事務用品",
    },
    {
        "keywords": ["電車", "定期券", "駅", "旅費", "交通"],
        "debit_account": "旅費交通費",
        "credit_account": "現金",
        "notes": "交通費",
    },
    {
        "keywords": ["電話", "通信", "インターネット", "ネット", "プロバイダ"],
        "debit_account": "通信費",
        "credit_account": "買掛金",
        "notes": "通信費",
    },
    {
        "keywords": ["広告", "宣伝", "掲載", "CM"],
        "debit_account": "広告宣伝費",
        "credit_account": "買掛金",
        "notes": "広告掲載",
    },
    {
        "keywords": ["賃料", "家賃", "地代", "貸借"],
        "debit_account": "地代家賃",
        "credit_account": "現金",
        "notes": "賃料",
    },
]


def load_rules():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, keywords, debit_account, credit_account, notes, is_active FROM rules WHERE is_active = 1 ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        init_db()
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, keywords, debit_account, credit_account, notes, is_active FROM rules WHERE is_active = 1 ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]


def add_rule(keywords, debit_account, credit_account="買掛金", notes=""):
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO rules (keywords, debit_account, credit_account, notes, is_active) VALUES (?, ?, ?, ?, 1)",
            (keywords, debit_account, credit_account, notes),
        )
        return cursor.lastrowid
