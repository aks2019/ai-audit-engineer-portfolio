import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/audit.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def create_audit_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flagged_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            vendor_name TEXT,
            amount REAL,
            anomaly_score INTEGER,
            anomaly_probability REAL,
            risk_explanation TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_flagged_to_db(df: pd.DataFrame):
    create_audit_table()
    conn = sqlite3.connect(DB_PATH)
    df = df.copy()
    df['created_at'] = datetime.now().isoformat()
    df[['transaction_id', 'vendor_name', 'amount', 'anomaly_score',
        'anomaly_probability', 'risk_explanation', 'created_at']].to_sql(
        'flagged_transactions', conn, if_exists='append', index=False)
    conn.close()
    print(f"✅ Saved {len(df)} flagged transactions to SQLite (data/audit.db)")