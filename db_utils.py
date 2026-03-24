import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

def get_db_connection():
    return psycopg2.connect(os.getenv("NEON_CONNECTION_STRING"))

def save_audit_run(df, run_name="Manual Upload"):
    conn = get_db_connection()
    cur = conn.cursor()
   
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            run_timestamp TIMESTAMP,
            run_name TEXT,
            transaction_id TEXT,
            vendor_name TEXT,
            amount FLOAT,
            risk_score FLOAT,
            anomaly INT,
            raw_json JSONB
        );
    """)
   
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO audit_logs
            (run_timestamp, run_name, transaction_id, vendor_name, amount, risk_score, anomaly, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now(),
            run_name,
            str(row.get('transaction_id', '')),
            str(row.get('vendor_name', '')),
            float(row.get('amount', 0)),
            float(row.get('Risk_Score', 0)),
            int(row.get('Anomaly', 0)),
            row.to_json()
        ))
   
    conn.commit()
    cur.close()
    conn.close()

# RAG audit logging (this was missing)
def log_rag_query(query, response):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_audit_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            query TEXT,
            response TEXT,
            user_id TEXT DEFAULT 'Ashok'
        );
    """)
    cur.execute("""
        INSERT INTO rag_audit_logs (timestamp, query, response)
        VALUES (%s, %s, %s)
    """, (datetime.now(), query, response))
    conn.commit()
    cur.close()
    conn.close()