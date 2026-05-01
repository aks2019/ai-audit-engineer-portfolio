"""Base Audit Check - Abstract base class for audit detection modules.

Detection modules should stage proposed findings first. Formal reporting reads only
confirmed rows from audit_findings after auditor review/confirmation.
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
                  company_code: str = "HQ", plant_code: str = ""):
        """Stage proposed findings for auditor confirmation.

        Kept as log_to_db for backward compatibility with existing pages, but it
        no longer inserts directly into audit_findings. Official findings are
        created only by confirm_draft_findings().
        """
        from utils.audit_db import stage_findings

        draft_df = flagged_df.head(100).copy()
        if "checklist_ref" not in draft_df.columns:
            draft_df["checklist_ref"] = self.checklist_ref
        if "proposed_finding" not in draft_df.columns:
            draft_df["proposed_finding"] = draft_df.get("flag_reason", "Anomaly detected")
        if "amount_at_risk" not in draft_df.columns and "amount" in draft_df.columns:
            draft_df["amount_at_risk"] = draft_df["amount"]
        return stage_findings(
            draft_df,
            module=area,
            run_id=run_id,
            period=period,
            metadata={
                "area": area,
                "company_code": company_code,
                "plant_code": plant_code,
                "checklist_ref": self.checklist_ref,
                "generated_by": "system_detection",
            },
        )

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
