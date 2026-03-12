import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def create_audit_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flagged_transactions (
            id SERIAL PRIMARY KEY,
            transaction_id TEXT,
            vendor_id TEXT,
            vendor_name TEXT,
            amount NUMERIC,
            anomaly_score INTEGER,
            risk_explanation TEXT,
            composite_risk_score NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("✅ Audit table created/verified in PostgreSQL")

def save_flagged_to_postgres(df):
    create_audit_table()
    conn = get_connection()
    cur = conn.cursor()
    
    # Convert to list of tuples
    data = [tuple(x) for x in df[[
        'transaction_id', 'vendor_id', 'vendor_name', 'amount',
        'anomaly_score', 'risk_explanation', 'composite_risk_score'
    ]].values]
    
    query = """
        INSERT INTO flagged_transactions 
        (transaction_id, vendor_id, vendor_name, amount, anomaly_score, risk_explanation, composite_risk_score)
        VALUES %s
    """
    execute_values(cur, query, data)
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"✅ Saved {len(df)} flagged transactions to PostgreSQL audit table")