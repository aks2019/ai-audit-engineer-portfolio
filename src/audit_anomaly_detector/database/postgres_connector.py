<<<<<<< HEAD
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
=======
from __future__ import annotations

"""
PostgreSQL connector for the Vendor Payment Anomaly Detector.

This module is designed for local experimentation only. It reads connection
details from environment variables, optionally loaded via a .env file:

    PG_HOST=localhost
    PG_PORT=5432
    PG_DBNAME=audit_db
    PG_USER=postgres
    PG_PASSWORD=123

For a quick local PostgreSQL instance, you can use Docker:

    docker run --name audit-postgres -e POSTGRES_PASSWORD=yourpassword \\
        -p 5432:5432 -d postgres:17

In a real environment, credentials should be stored securely (vault/secret
manager) rather than in plain .env files.
"""

import os
from datetime import datetime
from typing import Optional

import pandas as pd
import psycopg2
from dotenv import load_dotenv


load_dotenv()  # Load variables from .env if present.


def _get_connection(dbname: Optional[str] = None) -> psycopg2.extensions.connection:
    """Create a new PostgreSQL connection using environment variables."""

    host = os.getenv("PG_HOST", "localhost")
    port = int(os.getenv("PG_PORT", "5432"))
    database = dbname or os.getenv("PG_DBNAME", "audit_db")
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "yourpassword")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password,
    )


def create_audit_table() -> None:
    """Create the flagged_transactions audit table if it does not exist."""

    conn = _get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS flagged_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    vendor_name TEXT,
                    amount NUMERIC,
                    anomaly_score INTEGER,
                    anomaly_probability DOUBLE PRECISION,
                    risk_explanation TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
    finally:
        conn.close()


def save_flagged_to_postgres(df: pd.DataFrame) -> int:
    """Append flagged transaction rows into the audit table.

    Returns the number of rows successfully inserted.
    """

    if df.empty:
        return 0

    conn = _get_connection()
    inserted = 0
    try:
        with conn, conn.cursor() as cur:
            # Ensure table exists before insertion.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS flagged_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    vendor_name TEXT,
                    amount NUMERIC,
                    anomaly_score INTEGER,
                    anomaly_probability DOUBLE PRECISION,
                    risk_explanation TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            rows = [
                (
                    str(row["transaction_id"]),
                    str(row.get("vendor_name", "")),
                    float(row.get("amount")) if pd.notna(row.get("amount")) else None,
                    int(row.get("anomaly_score")) if pd.notna(row.get("anomaly_score")) else None,
                    float(row.get("anomaly_probability"))
                    if pd.notna(row.get("anomaly_probability"))
                    else None,
                    str(row.get("risk_explanation", "")),
                    datetime.utcnow(),
                )
                for _, row in df.iterrows()
            ]

            cur.executemany(
                """
                INSERT INTO flagged_transactions (
                    transaction_id,
                    vendor_name,
                    amount,
                    anomaly_score,
                    anomaly_probability,
                    risk_explanation,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                rows,
            )
            inserted = len(rows)
    finally:
        conn.close()

    return inserted

>>>>>>> e493e81aee087ef3d70c60041e0d312900c25112
