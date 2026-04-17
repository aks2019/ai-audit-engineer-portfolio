from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from utils.rag_engine import generate_rag_audit_report, _get_vectorstore_safe

app = FastAPI(
    title="AI Audit Engineer API",
    description="Vendor Payment Anomaly + Policy RAG Audit endpoints",
    version="1.0.0",
)


# ── Request / Response models ─────────────────────────────────────────────

class AuditRequest(BaseModel):
    flagged_transactions: List[Dict[str, Any]] = Field(
        ..., min_length=1, description="List of flagged transaction dicts from the anomaly detector"
    )
    vendor_name: Optional[str] = Field(None, description="Primary vendor name for the audit report")
    contract_text: Optional[str] = Field(None, description="Optional raw vendor contract text for inline RAG")


class AuditResponse(BaseModel):
    audit_summary: str
    citations: List[str]
    log_hash: str


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    db_error: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health_check():
    """Liveness + DB connectivity check."""
    _, db_error = _get_vectorstore_safe()
    return HealthResponse(
        status="ok",
        db_connected=(db_error is None),
        db_error=db_error,
    )


@app.post("/api/anomaly-rag-audit", response_model=AuditResponse, tags=["audit"])
async def generate_anomaly_audit(payload: AuditRequest):
    """
    Run a policy RAG audit against a list of flagged transactions.
    Returns an audit summary, policy citations, and an immutable log hash.
    """
    try:
        result = generate_rag_audit_report(
            flagged_transactions=payload.flagged_transactions,
            vendor_name=payload.vendor_name,
            contract_text=payload.contract_text,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # generate_rag_audit_report never raises — it returns error text in audit_summary.
    # Surface a 503 if the DB or LLM was unreachable so callers can retry.
    if result.get("log_hash") in ("offline", "llm-error"):
        raise HTTPException(status_code=503, detail=result["audit_summary"])

    return AuditResponse(
        audit_summary=result["audit_summary"],
        citations=result["citations"],
        log_hash=result["log_hash"],
    )


# ── Entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
