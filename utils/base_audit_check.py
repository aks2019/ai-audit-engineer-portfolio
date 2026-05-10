"""Base Audit Check — Abstract base class for all 21 detection modules.

Principle 4: Plugin Architecture. Adding a new audit check means writing one new
class — zero changes to any existing page or engine. The check registers itself;
pages enumerate available checks dynamically.
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseAuditCheck(ABC):
    name: str = "Base Check"
    description: str = ""
    checklist_ref: str = ""
    sap_tcode_primary: str = ""
    sap_tcode_standard_alt: str = ""
    required_columns: list = []
    optional_columns: list = []
    industry_applicable: list = ["all"]

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Returns df subset with flag_reason column added."""
        pass

    def explain(self, flagged_df: pd.DataFrame) -> pd.DataFrame:
        """Add plain-language explanation columns (optional override)."""
        return flagged_df

    def rag_prompt(self, flagged_rows: list) -> str:
        """Build a RAG-ready prompt for policy lookup."""
        return f"Audit flagged items per {self.checklist_ref}: {flagged_rows}"

    def validate_columns(self, df: pd.DataFrame) -> list:
        """Return list of missing required columns."""
        return [c for c in self.required_columns if c not in df.columns]

    def log_to_db(self, flagged_df: pd.DataFrame, area: str, period: str, run_id: str,
                  company_code: str = "HQ", plant_code: str = "", insert_official: bool = False):
        """Optionally write findings to official SQLite audit trail.

        Default is False because detection pages now use draft staging + maker-checker
        confirmation before anything enters the official trail.
        """
        if not insert_official:
            return
        import sqlite3
        from pathlib import Path
        Path("data").mkdir(exist_ok=True)
        conn = sqlite3.connect("data/audit.db")
        for _, row in flagged_df.head(100).iterrows():
            conn.execute(
                """INSERT INTO audit_findings
                (run_id, company_code, plant_code, area, checklist_ref, finding, amount_at_risk, vendor_name,
                 finding_date, period, risk_band, status)
                VALUES (?,?,?,?,?,?,?,?,date('now'),?,?,'Open')""",
                (
                    run_id,
                    company_code,
                    plant_code,
                    area,
                    self.checklist_ref,
                    row.get("flag_reason", "Anomaly detected"),
                    float(row.get("amount", 0)),
                    str(row.get("vendor_name", "")),
                    period,
                    row.get("risk_band", "HIGH"),
                ),
            )
        conn.commit()
        conn.close()

    def compute_risk_band(self, amount: float, recurrence: int = 1) -> str:
        """Compute risk band from amount and recurrence count."""
        impact = 1 + (amount > 100000) + (amount > 1000000) + \
                 (amount > 5000000) + (amount > 10000000)
        likelihood = 1 if recurrence == 1 else (3 if recurrence == 2 else 5)
        score = impact * likelihood
        if score >= 20:
            return "CRITICAL"
        elif score >= 12:
            return "HIGH"
        elif score >= 6:
            return "MEDIUM"
        return "LOW"
