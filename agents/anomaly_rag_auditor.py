from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, TypedDict

from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import _get_vectorstore_safe, get_rag_chain

logger = logging.getLogger(__name__)


# ── State schema ──────────────────────────────────────────────────────────

class AnomalyRAGState(TypedDict):
    flagged_transactions: List[Dict]   # input: anomaly detector output
    vendor_contracts: List[Dict]       # retrieved policy/contract chunks
    audit_summary: str
    citations: List[str]
    log_hash: str


# ── Node: pass-through validation ─────────────────────────────────────────

def extract_anomaly_data(state: AnomalyRAGState) -> AnomalyRAGState:
    return state


# ── Node: RAG retrieval ───────────────────────────────────────────────────

def policy_rag_check(state: AnomalyRAGState) -> AnomalyRAGState:
    query = (
        "Analyse these flagged payment anomalies for policy violations: "
        + json.dumps(state["flagged_transactions"][:10])  # cap to avoid context overflow
        + " Check vendor contracts, procurement SOPs, GST/TDS circulars, related-party rules."
    )

    vectorstore, db_error = _get_vectorstore_safe()
    if vectorstore is None:
        logger.warning("Vectorstore unavailable: %s", db_error)
        state["vendor_contracts"] = []
        state["citations"] = []
        return state

    retrieved_docs = vectorstore.similarity_search(query[:1000], k=4)
    state["vendor_contracts"] = [
        {
            "content": doc.page_content[:500],
            "source": doc.metadata.get("source", "policy doc"),
            "page": doc.metadata.get("page", ""),
        }
        for doc in retrieved_docs
    ]
    state["citations"] = [
        f"{d['source']} (page {d['page']})" for d in state["vendor_contracts"]
    ]
    return state


# ── Node: LLM summary generation ──────────────────────────────────────────

def generate_audit_summary(state: AnomalyRAGState) -> AnomalyRAGState:
    context = "\n\n".join(d["content"] for d in state["vendor_contracts"])
    question = (
        "You are an audit-compliant AI Audit Engineer (FMCG/manufacturing, SAP FICO-MM). "
        "Write a professional audit finding for the following flagged transactions. "
        "Include policy violations (with exact clause), risk rating, and recommendation.\n\n"
        f"Transactions:\n{json.dumps(state['flagged_transactions'][:10])}"
    )

    try:
        chain = get_rag_chain()
        response = chain.invoke({"context": context, "question": question})
        summary = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        summary = f"⚠️ LLM unavailable — could not generate audit summary.\n\n`{exc}`"

    log_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "flagged_count": len(state["flagged_transactions"]),
        "summary_hash": log_hash,
        "citations": state["citations"],
    }
    logger.info("Audit log: %s", json.dumps(log_entry))

    state["audit_summary"] = summary
    state["log_hash"] = log_hash
    return state


# ── Graph ─────────────────────────────────────────────────────────────────

workflow = StateGraph(AnomalyRAGState)
workflow.add_node("extract", extract_anomaly_data)
workflow.add_node("policy_check", policy_rag_check)
workflow.add_node("summary", generate_audit_summary)
workflow.set_entry_point("extract")
workflow.add_edge("extract", "policy_check")
workflow.add_edge("policy_check", "summary")
workflow.add_edge("summary", END)

anomaly_rag_auditor = workflow.compile()
