@router.post("/api/anomaly-rag-audit")
async def generate_anomaly_audit(payload: dict):
    result = anomaly_rag_auditor.invoke({
        "flagged_transactions": payload["flagged_transactions"]  # e.g. [{"transaction_id": "...", "amount": 840000, "vendor_code": "V123", "shap_explanation": "..."}]
    })
    return {
        "audit_summary": result["audit_summary"],
        "citations": result["citations"],
        "log_hash": result["log_hash"]
    }