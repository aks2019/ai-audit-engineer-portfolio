"""Central AI Service Layer - Unified AI/RAG for SARVAGYA.

Provides: model selection, fallback, prompt templates, citation handling,
token limits, response logging, error handling.
"""
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Union

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

# ====================== MODEL PROVIDER ABSTRACTION ======================

class AIService:
    """Central AI service with model provider abstraction and fallback."""

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "gemini").lower()
        self.use_local = os.getenv("USE_LOCAL_LLM", "true").lower() == "true"
        self._llm = None
        self._vectorstore = None
        self._log_file = "data/ai_audit_log.jsonl"

    def get_llm(self):
        """Get or create LLM instance based on provider setting."""
        if self._llm is not None:
            return self._llm

        if self.use_local:
            # Local LLM via llama.cpp
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:8080/v1"),
                api_key=os.getenv("LOCAL_LLM_API_KEY", "llama.cpp"),
                model=os.getenv("LOCAL_LLM_MODEL", "gemma-4-E2B-it-Q4_K_M.gguf"),
                temperature=0.7,
                max_tokens=8000
            )
        else:
            # Online provider
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                    api_key=os.getenv("OPENAI_API_KEY"),
                    temperature=0.3,
                    max_tokens=4000
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                    api_key=os.getenv("ANTHROPIC_API_KEY"),
                    temperature=0.3,
                    max_tokens=4000
                )
            else:  # Default to Gemini
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._llm = ChatGoogleGenerativeAI(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                    google_api_key=os.getenv("GOOGLE_API_KEY"),
                    temperature=0.3,
                    max_tokens=4000
                )

        return self._llm

    def get_vectorstore(self):
        """Get vectorstore for RAG."""
        if self._vectorstore is not None:
            return self._vectorstore

        try:
            from langchain_postgres import PGVector
            from langchain_huggingface import HuggingFaceEmbeddings

            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self._vectorstore = PGVector(
                embeddings=embeddings,
                collection_name="audit_policies",
                connection=os.getenv("NEON_CONNECTION_STRING", os.getenv("DATABASE_URL")),
                use_jsonb=True
            )
        except Exception as e:
            print(f"Vectorstore init failed: {e}")
            self._vectorstore = None

        return self._vectorstore

    def rag_retrieve(self, query: str, k: int = 4) -> List[str]:
        """Retrieve documents for RAG."""
        vectorstore = self.get_vectorstore()
        if vectorstore is None:
            return []

        try:
            retriever = vectorstore.as_retriever(search_kwargs={"k": k})
            docs = retriever.invoke(query[:1000])
            return [doc.page_content[:500] for doc in docs]
        except Exception as e:
            print(f"RAG retrieve failed: {e}")
            return []

    def generate_with_rag(self, query: str, prompt_template: str = None,
                         system_message: str = None, k: int = 4) -> Dict[str, Any]:
        """Generate response with RAG context and citation handling."""
        # Retrieve context
        context_docs = self.rag_retrieve(query, k=k)
        context = "\n\n".join(context_docs)

        # Build prompt
        if system_message is None:
            system_message = """You are SARVAGYA AI - a senior internal auditor.
Answer based only on the provided context. Cite sources.
If uncertain, say so clearly."""

        if prompt_template is None:
            prompt_template = "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        full_prompt = prompt_template.format(context=context, question=query)

        # Log request
        request_hash = self._log_request(query, system_message, self.provider)

        try:
            llm = self.get_llm()
            from langchain_core.messages import HumanMessage, SystemMessage
            response = llm.invoke([
                SystemMessage(content=system_message),
                HumanMessage(content=full_prompt)
            ])

            content = response.content if hasattr(response, 'content') else str(response)
            response_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

            return {
                "content": content,
                "citations": context_docs,
                "request_hash": request_hash,
                "response_hash": response_hash,
                "provider": self.provider,
                "model": os.getenv(f"{self.provider.upper()}_MODEL", "default"),
                "status": "success"
            }

        except Exception as e:
            return {
                "content": f"AI generation failed: {str(e)}",
                "citations": [],
                "request_hash": request_hash,
                "response_hash": "error",
                "provider": self.provider,
                "error": str(e),
                "status": "error"
            }

    def _log_request(self, query: str, system_message: str, provider: str) -> str:
        """Log AI request to audit trail."""
        request_hash = hashlib.sha256(
            f"{query}{system_message}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        Path("data").mkdir(exist_ok=True)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request_hash": request_hash,
            "query_preview": query[:200],
            "provider": provider,
            "status": "requested"
        }

        try:
            with open(self._log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass

        return request_hash

    def log_response(self, request_hash: str, response: str, status: str = "success"):
        """Log AI response to audit trail."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "request_hash": request_hash,
                "response_preview": response[:200],
                "status": status
            }
            with open(self._log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass


# ====================== PROMPT TEMPLATES ======================

PROMPT_TEMPLATES = {
    "audit_finding": """You are a senior internal auditor with 17+ years experience.
Draft a clear, concise audit finding from this exception:

Exception Details:
{exception_details}

Context from policies/standards:
{context}

Provide:
1. Finding Title (one line)
2. Observation (2-3 sentences)
3. Risk/Impact
4. Root Cause
5. Recommendation
6. Policy/Standard Reference

Be objective and fact-based.""",

    "policy_review": """You are a policy compliance analyst.
Review this policy document for gaps against standard controls:

Policy Excerpt:
{policy_text}

Standard Controls to Check:
{controls}

Identify:
1. Missing clauses
2. Weak controls
3. Compliance gaps
4. Recommendations""",

    "financial_explanation": """You are a financial auditor.
Explain this financial exception in context:

Exception: {exception}

Trial Balance Context:
{tb_context}

Standards Reference:
{standards}

Provide clear explanation for management.""",

    "caro_checklist": """You are an audit senior.
For CARO 2020 clause {clause}, provide:

Clause: {clause_text}
Company Response: {response}

Provide:
1. Audit Procedure performed
2. Evidence obtained
3. Finding (if any)
4. Impact on audit opinion""",

    "report_summary": """You are an audit report writer.
Draft an executive summary for audit findings:

Findings:
{findings}

Engagement: {engagement}
Period: {period}

Provide structured summary for audit committee."""
}


def get_prompt(template_name: str, **kwargs) -> str:
    """Get formatted prompt template."""
    template = PROMPT_TEMPLATES.get(template_name, "")
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


# ====================== SINGLETON INSTANCE ======================

ai_service = AIService()


# ====================== CONVENIENCE FUNCTIONS ======================

def get_ai():
    """Get AI service instance."""
    return ai_service


def ask_with_rag(question: str, k: int = 4) -> Dict[str, Any]:
    """Quick RAG query."""
    return ai_service.generate_with_rag(question, k=k)


def draft_finding(exception_details: str, context: str = "") -> str:
    """Draft an audit finding using AI."""
    prompt = get_prompt("audit_finding",
                       exception_details=exception_details,
                       context=context)
    result = ai_service.generate_with_rag(prompt, k=2)
    return result.get("content", "Drafting failed")


def review_policy(policy_text: str, controls: str = "") -> Dict[str, Any]:
    """Review policy for compliance gaps."""
    prompt = get_prompt("policy_review",
                       policy_text=policy_text[:3000],
                       controls=controls)
    return ai_service.generate_with_rag(prompt, k=4)


def summarize_findings(findings: list, engagement: str, period: str) -> str:
    """Summarize findings for audit committee."""
    findings_text = "\n".join([f"- {f}" for f in findings[:10]])
    prompt = get_prompt("report_summary",
                       findings=findings_text,
                       engagement=engagement,
                       period=period)
    result = ai_service.generate_with_rag(prompt, k=2)
    return result.get("content", "Summary failed")


def explain_financial_exception(exception: str, tb_context: str = "",
                               standards: str = "") -> str:
    """Explain financial exception."""
    prompt = get_prompt("financial_explanation",
                       exception=exception,
                       tb_context=tb_context,
                       standards=standards)
    result = ai_service.generate_with_rag(prompt, k=3)
    return result.get("content", "Explanation failed")