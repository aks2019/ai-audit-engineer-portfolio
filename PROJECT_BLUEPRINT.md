# AI Audit Engineer — Project Blueprint
## Version 5.1 FINAL | 2026-04-25

---

## 1. PROJECT OVERVIEW

**Name:** AI Audit Engineer  
**Creator:** Ashok Kumar Sharma — 17+ years internal audit, SAP FICO/MM, FMCG Manufacturing  
**GitHub:** https://github.com/aks2019/ai-audit-engineer-portfolio  
**Deployed URL:** https://aiauditengineer.onrender.com  
**Mission:** Automate internal audit as far as possible using AI — 100% population testing, checklist-grounded findings, RAG-cited policy references, Board-ready reporting.

---

## 2. ARCHITECTURE

### 2.1 Six Core Principles (Locked)
1. **Zero Hardcoded Column Names** — `utils/column_mapper.py`
2. **Zero Hardcoded Compliance Dates** — `config/compliance_calendar.yaml`
3. **Zero Z-Tcode Dependency** — standard SAP alternatives only
4. **Plugin Architecture** — `utils/base_audit_check.py`
5. **Industry-Agnostic Core** — `config/industry_profiles/*.yaml`
6. **Shared Audit Trail** — SQLite `data/audit.db`

### 2.2 Tech Stack
| Layer | Technology |
|---|---|
| UI | Streamlit (multi-page) |
| LLM | Gemini 1.5 Pro (Render) / llama.cpp local |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | pgvector on Neon PostgreSQL |
| ML | IsolationForest + XGBoost + SHAP + MLPRegressor |
| Rules Engine | YAML-driven compliance calendar |
| Audit Trail | SQLite (`data/audit.db`) |
| PDF Export | ReportLab |
| Scheduling | Prefect |
| Graph | NetworkX |
| Fuzzy Matching | fuzzywuzzy + python-Levenshtein |

---

## 3. MODULE MAP (26 Pages)

### Phase 1 — Core Detection & Analysis (P1–P21)
| # | Module | File | Key Feature |
|---|---|---|---|
| P1 | Payment Anomaly Detector | `pages/anomaly_detector.py` | IsolationForest + XGBoost ensemble, SHAP, Benford's Law |
| P2 | Policy RAG Bot | `pages/policy_rag_bot.py` | pgvector RAG, chat history, PDF export |
| P3 | Dynamic Audit Builder | `pages/dynamic_audit_builder.py` | 5 no-code audit templates |
| P4 | Financial Statement Auditor | `pages/financial_statement_auditor.py` | LLM-drafted Mfg/Trading/P&L/BS/CF |
| P5 | BRS Reconciliation | `pages/brs_reconciliation.py` | Auto-match bank vs GL, stale cheques |
| P6 | Receivables & Bad Debt | `pages/receivables_bad_debt.py` | DSO, opportunity cost, XGBoost classifier |
| P7 | Unified Dashboard | `pages/unified_dashboard.py` | Risk gauge, trend, compliance calendar |
| P8 | GST/TDS Compliance | `pages/gst_tds_compliance.py` | GSTR-2A mismatch, TDS rate validation |
| P9 | Related-Party Monitor | `pages/related_party_monitor.py` | NetworkX graph, concentration analysis |
| P10 | Duplicate Invoice Detector | `pages/duplicate_invoice_detector.py` | Fuzzy Levenshtein, PO variance |
| P11 | Inventory Anomaly | `pages/inventory_anomaly.py` | K-Means clustering, slow-moving, expiry |
| P12 | Fixed Asset Auditor | `pages/fixed_asset_auditor.py` | Autoencoder, depreciation variance |
| P13 | Expense Claim Auditor | `pages/expense_claim_auditor.py` | Grade limits, self-approval SOD |
| P14 | Audit Planning Engine | `pages/audit_planning_engine.py` | Gap report, LLM annual plan |
| P15 | Risk Register | `pages/risk_register.py` | 5×5 heat map, quarterly priority |
| P16 | Audit Report Center | `pages/audit_report_center.py` | Centralized reports, MIS CFO PDF |
| P17 | Audit Committee Pack | `pages/audit_committee_pack.py` | ATR, editable responses, Board escalation |
| P18 | Payroll Audit | `pages/payroll_audit.py` | Ghost employee, PF/ESI mismatch |
| P19 | Sales Revenue Auditor | `pages/sales_revenue_auditor.py` | Ind AS 115 gap, credit note concentration |
| P20 | ITGC & SAP Access | `pages/itgc_sap_access_auditor.py` | SoD matrix, privileged access |
| P21 | Contract Management | `pages/contract_management_auditor.py` | Expiry, LD non-recovery, concentration |

### Phase 2 — Advanced Tools (P22–P26)
| # | Module | File | Key Feature |
|---|---|---|---|
| P22 | Audit Workflow Engine | `pages/audit_workflow.py` | Status lifecycle, SLA tracking, audit trail |
| P23 | NLP Document Intelligence | `pages/nlp_document_intelligence.py` | LLM extraction from emails/board papers |
| P24 | Multi-Company Dashboard | `pages/multi_company_dashboard.py` | Group consolidation, plant-level filtering |
| P25 | Statistical Sampling | `pages/statistical_sampling.py` | MUS, Random, Cell, Stratified |
| P26 | Audit KPI Dashboard | `pages/audit_kpi_dashboard.py` | Closure rate, productivity, trends |

---

## 4. DATABASE SCHEMA

### audit_findings (core)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_id | TEXT | Batch identifier |
| company_code | TEXT | Multi-company support |
| plant_code | TEXT | Location |
| area | TEXT | Audit area |
| checklist_ref | TEXT | e.g., "Purchasing A.7" |
| finding | TEXT | Description |
| amount_at_risk | REAL | ₹ value |
| vendor_name | TEXT | Counterparty |
| finding_date | TEXT | ISO date |
| period | TEXT | YYYY-MM |
| risk_band | TEXT | CRITICAL/HIGH/MEDIUM/LOW |
| status | TEXT | Open → Closed |
| sla_deadline | TEXT | SLA date |
| assigned_to | TEXT | Owner |
| opened_at | TEXT | Timestamp |
| closed_at | TEXT | Timestamp |
| days_to_close | INTEGER | Calculated |

### workflow_history
| Column | Type |
|---|---|
| id | INTEGER PK |
| finding_id | INTEGER FK |
| old_status | TEXT |
| new_status | TEXT |
| changed_by | TEXT |
| changed_at | TEXT |
| comment | TEXT |

### audit_kpi
| Column | Type |
|---|---|
| id | INTEGER PK |
| metric_name | TEXT |
| metric_value | REAL |
| period | TEXT |
| recorded_at | TEXT |

### sampling_runs
| Column | Type |
|---|---|
| id | INTEGER PK |
| run_name | TEXT |
| population_size | INTEGER |
| sample_size | INTEGER |
| method | TEXT |
| confidence_level | REAL |
| materiality_threshold | REAL |
| executed_at | TEXT |

---

## 5. ENVIRONMENT VARIABLES

```bash
GOOGLE_API_KEY=<Gemini API key>
USE_LOCAL_LLM=false                     # true for local llama.cpp
DATABASE_URL=<Neon PostgreSQL URL>
```

---

## 6. DEPLOYMENT CHECKLIST

- [ ] Set `GOOGLE_API_KEY` on Render
- [ ] Set `DATABASE_URL` (Neon) on Render
- [ ] Set `USE_LOCAL_LLM=false`
- [ ] Run `ingest_policies.py` to index 17 checklists into pgvector
- [ ] Verify all 26 pages load without ImportError
- [ ] Verify `data/audit.db` auto-creates on first run
- [ ] Test `_get_llm()` returns Gemini (not local) on Render

---

*This blueprint is the single source of truth for architecture decisions.*
