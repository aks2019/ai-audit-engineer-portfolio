from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from typing import TypedDict, List, Dict
import json
from datetime import datetime
import hashlib
from utils.logging import audit_log  # your existing audit logger

class AnomalyRAGState(TypedDict):
    flagged_transactions: List[Dict]  # from anomaly detector output
    vendor_contracts: List[Dict]      # RAG retrievals
    audit_summary: str
    citations: List[str]
    log_hash: str

def extract_anomaly_data(state: AnomalyRAGState):
    # Input is already structured from Payment Anomaly Detector (SAP FICO-MM format)
    return state

def policy_rag_check(state: AnomalyRAGState):
    # Reuse your existing RAG chain (hybrid pgvector + keyword + metadata filter on vendor_code)
    query = f"""
    Analyse these flagged payment anomalies for policy violations:
    {json.dumps(state['flagged_transactions'], indent=2)}
    
    Check against vendor contracts, procurement SOPs, GST/TDS circulars, related-party rules.
    Flag any Section 4.2 related-party breach or GST/TDS mismatch.
    """
    # Your existing LangGraph RAG node call here (from local RAG bot)
    response = rag_chain.invoke({"messages": [HumanMessage(content=query)]})  # rag_chain already in your code
    state['vendor_contracts'] = response.get("retrieved_docs", [])
    state['citations'] = [doc.metadata["source"] for doc in response.get("retrieved_docs", [])]
    return state

def generate_audit_summary(state: AnomalyRAGState):
    prompt = f"""
    You are an audit-compliant AI Audit Engineer (FMCG/manufacturing, SAP FICO-MM).
    Write a professional audit finding for the following flagged transactions.
    Include SHAP reasons, policy violations (with exact clause), risk rating, and recommendation.
    Use plain English + citations.
    Transactions: {json.dumps(state['flagged_transactions'])}
    Retrieved contracts: {json.dumps(state['vendor_contracts'])}
    """
    # Call Claude 4.6 Opus / Gemini 1.5 Pro (your existing LLM)
    summary = llm.invoke(prompt)
    state['audit_summary'] = summary.content
    
    # Audit trail
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": "audit_user",  # from Streamlit session
        "flagged_count": len(state['flagged_transactions']),
        "summary_hash": hashlib.sha256(summary.content.encode()).hexdigest(),
        "citations": state['citations']
    }
    audit_log(log_entry)
    state['log_hash'] = log_entry["summary_hash"]
    return state

# Build the subgraph (add to your existing LangGraph workflow)
workflow = StateGraph(AnomalyRAGState)
workflow.add_node("extract", extract_anomaly_data)
workflow.add_node("policy_check", policy_rag_check)
workflow.add_node("summary", generate_audit_summary)
workflow.set_entry_point("extract")
workflow.add_edge("extract", "policy_check")
workflow.add_edge("policy_check", "summary")
workflow.add_edge("summary", END)

anomaly_rag_auditor = workflow.compile()