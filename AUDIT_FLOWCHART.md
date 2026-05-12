# AI Audit Engineer — Audit Flowchart
## Version 2.0 | Updated: 2026-05-13

---

## 1. PROJECT OVERVIEW

**SARVAGYA** is a comprehensive AI-powered internal audit intelligence platform that automates audit detection, policy-grounded review, workflow tracking, and Board-ready reporting.

| Attribute | Detail |
|---|---|
| **Creator** | Ashok Kumar Sharma (17+ years Internal Audit, SAP FICO/MM) |
| **GitHub** | https://github.com/aks2019/ai-audit-engineer-portfolio |
| **Live App** | https://aiauditengineer.onrender.com |
| **Modules** | 27 active audit pages |
| **Architecture** | Multi-page Streamlit with ML + RAG + LLM |

---

## 2. COMPLETE PROJECT STRUCTURE

```
ai-audit-engineer-portfolio/
├── app.py                          # Streamlit main entry point
├── api.py                          # FastAPI wrapper
├── main.py                         # Alternative entry point
├── run_training.py                 # Model training script
│
├── pages/                          # 27 Audit Module Pages
│   ├── anomaly_detector.py         # P1: Payment Anomaly Detection
│   ├── policy_rag_bot.py           # P2: Policy RAG Chatbot
│   ├── dynamic_audit_builder.py     # P3: No-code Audit Builder
│   ├── financial_statement_auditor.py  # P4: Financial Statement Audit
│   ├── brs_reconciliation.py       # P5: Bank Reconciliation
│   ├── receivables_bad_debt.py     # P6: Receivables & Bad Debt
│   ├── unified_dashboard.py        # P7: Unified Risk Dashboard
│   ├── gst_tds_compliance.py       # P8: GST/TDS Compliance
│   ├── related_party_monitor.py    # P9: Related Party Analysis
│   ├── duplicate_invoice_detector.py   # P10: Duplicate Detection
│   ├── inventory_anomaly.py        # P11: Inventory Anomalies
│   ├── fixed_asset_auditor.py      # P12: Fixed Assets Audit
│   ├── expense_claim_auditor.py     # P13: Expense Claims
│   ├── audit_planning_engine.py    # P14: Audit Planning
│   ├── risk_register.py            # P15: Risk Register
│   ├── audit_report_center.py      # P16: Report Center
│   ├── audit_committee_pack.py     # P17: Committee Pack
│   ├── payroll_audit.py            # P18: Payroll Audit
│   ├── sales_revenue_auditor.py    # P19: Sales Revenue
│   ├── itgc_sap_access_auditor.py  # P20: ITGC & SAP Access
│   ├── contract_management_auditor.py  # P21: Contract Management
│   ├── audit_workflow.py           # P22: Workflow Engine
│   ├── nlp_document_intelligence.py   # P23: NLP Document Processing
│   ├── multi_company_dashboard.py  # P24: Multi-Company View
│   ├── statistical_sampling.py     # P25: Statistical Sampling
│   ├── audit_kpi_dashboard.py      # P26: KPI Dashboard
│   ├── audit_session_manager.py    # P27: Session Management
│   └── policy_management.py        # P28: Policy Management
│
├── core/                           # Core Audit Engine
│   ├── __init__.py
│   ├── audit_program.py            # Audit program generation
│   ├── controls.py                 # Control framework management
│   ├── engagements.py               # Engagement management
│   ├── evidence.py                 # Evidence collection
│   ├── init_audit_system.py        # System initialization
│   ├── policy_manager.py           # Policy CRUD operations
│   ├── policy_review.py            # Policy review workflow
│   ├── rbac.py                     # Role-based access control
│   └── standards_registry.py        # Audit standards registry
│
├── services/                       # Business Services
│   ├── __init__.py
│   └── ai_service.py               # LLM/RAG integration service
│
├── utils/                          # Utility Modules
│   ├── __init__.py
│   ├── audit_db.py                 # SQLite database operations
│   ├── audit_page_helpers.py       # Streamlit page helpers
│   ├── base_audit_check.py         # Base check plugin interface
│   ├── column_mapper.py            # Dynamic column mapping
│   ├── compliance_loader.py         # Compliance data loader
│   ├── industry_filter.py          # Industry-specific filtering
│   ├── rag_engine.py               # RAG retrieval engine
│   └── redis_cache.py              # Redis caching layer
│
├── agents/                         # AI Agents
│   └── anomaly_rag_auditor.py      # Anomaly + RAG hybrid agent
│
├── checks/                         # Specialized Check Modules
│   ├── __init__.py
│   ├── financial_statement/        # Financial statement checks
│   └── sap/                        # SAP-specific checks
│
├── config/                         # Configuration Files
│   ├── compliance_calendar.yaml    # Compliance dates registry
│   ├── navigation_registry.yaml    # Navigation config
│   └── industry_profiles/          # Industry-specific configs
│       ├── financial_services.yaml
│       ├── healthcare_pharma.yaml
│       ├── it_services.yaml
│       ├── manufacturing_fmcg.yaml
│       └── retail.yaml
│
├── models/                        # Trained ML Models
│   ├── isolation_forest.joblib     # Anomaly detection model
│   └── xgboost_risk_regressor.joblib  # Risk scoring model
│
├── scripts/                       # Utility Scripts
│   ├── add_stage_findings.py       # Add staged findings
│   ├── apply_full_pattern.py       # Apply full RAG pattern
│   ├── apply_rag_pattern_v2.py      # RAG pattern v2
│   ├── apply_rag_pattern_v3.py      # RAG pattern v3
│   ├── apply_rag_pattern.py         # Apply RAG pattern
│   ├── check_pattern.py             # Check pattern usage
│   ├── demo_use_case.py            # Demo runner
│   ├── fix_helpers.py              # Helper fixes
│   ├── run_inference.py            # Run ML inference
│   ├── seed_audit_data.py          # Seed test data
│   └── train_detector.py           # Train anomaly detector
│
├── tests/                         # Unit Tests
│   ├── __init__.py
│   ├── test_data_loaders.py        # Data loader tests
│   ├── test_features.py            # Feature engineering tests
│   ├── test_models.py              # Model tests
│   └── test_pipelines.py           # Pipeline tests
│
├── synthetic_data/                # Synthetic Data Generation
│   ├── generate_all_synthetic_data.py
│   └── nlp_document-intelligence.pdf
│
├── notebooks/                     # Jupyter Notebooks
│   ├── 01_eda.ipynb               # Exploratory Data Analysis
│   └── README.md
│
├── reports/                       # Report Templates
│   └── __init__.py
│
├── backend/                      # Backend Services
│   └── main.py
│
├── src/                          # Source Package
│   └── audit_anomaly_detector/
│
├── Internal Audit Checklist/      # Internal Documentation
│   ├── 1. PROJECT_STATUS.md
│   ├── 2. ROADMAP.md
│   ├── 3. TECH_STACK.md
│   └── A.3 FUTURE FULL SCALE PROJECT PLANNING.docx
│
├── data/                          # Runtime Data (auto-created)
│   └── audit.db                   # SQLite audit trail
│
└── Configuration Files
    ├── requirements.txt           # Python dependencies
    ├── pyproject.toml             # Package metadata
    ├── Dockerfile                 # Docker container
    ├── docker-compose.yml         # Docker compose
    ├── .env.example               # Environment template
    ├── runtime.txt                # Python runtime
    └── Procfile                   # Deployment config
```

---

## 3. AUDIT MODULE MAP (27 Pages)

### Phase 1 — Core Detection & Analysis

| # | Module | File | Key Features |
|---|---|---|---|
| P1 | **Payment Anomaly Detector** | `anomaly_detector.py` | IsolationForest + XGBoost ensemble, SHAP explanations, Benford's Law |
| P2 | **Policy RAG Bot** | `policy_rag_bot.py` | pgvector RAG retrieval, chat history, PDF export |
| P3 | **Dynamic Audit Builder** | `dynamic_audit_builder.py` | 5 no-code audit templates, checklist generation |
| P4 | **Financial Statement Auditor** | `financial_statement_auditor.py` | LLM-drafted Manufacturing/Trading P&L, Balance Sheet, Cash Flow |
| P5 | **BRS Reconciliation** | `brs_reconciliation.py` | Auto-match bank vs GL, stale cheques, unreconciled items |
| P6 | **Receivables & Bad Debt** | `receivables_bad_debt.py` | DSO analysis, opportunity cost, XGBoost default classifier |
| P7 | **Unified Dashboard** | `unified_dashboard.py` | Risk gauge, trend charts, compliance calendar widget |
| P8 | **GST/TDS Compliance** | `gst_tds_compliance.py` | GSTR-2A mismatch detection, TDS rate validation, filing status |
| P9 | **Related-Party Monitor** | `related_party_monitor.py` | NetworkX relationship graph, concentration analysis |
| P10 | **Duplicate Invoice Detector** | `duplicate_invoice_detector.py` | Fuzzy Levenshtein matching, PO variance, vendor clustering |
| P11 | **Inventory Anomaly** | `inventory_anomaly.py` | K-Means clustering, slow-moving stock, expiry alerts |
| P12 | **Fixed Asset Auditor** | `fixed_asset_auditor.py` | Autoencoder anomaly detection, depreciation variance |
| P13 | **Expense Claim Auditor** | `expense_claim_auditor.py` | Grade-based limits, self-approval SoD violation detection |
| P14 | **Audit Planning Engine** | `audit_planning_engine.py` | Gap analysis report, LLM-generated annual audit plan |
| P15 | **Risk Register** | `risk_register.py` | 5×5 risk heat map, quarterly priority scoring |
| P16 | **Audit Report Center** | `audit_report_center.py` | Centralized report library, CFO MIS PDF export |
| P17 | **Audit Committee Pack** | `audit_committee_pack.py` | Action Taken Report, editable management responses |
| P18 | **Payroll Audit** | `payroll_audit.py` | Ghost employee detection, PF/ESI compliance mismatch |
| P19 | **Sales Revenue Auditor** | `sales_revenue_auditor.py` | Ind AS 115 revenue recognition gap, credit note concentration |
| P20 | **ITGC & SAP Access** | `itgc_sap_access_auditor.py` | Segregation of Duties matrix, privileged access review |
| P21 | **Contract Management** | `contract_management_auditor.py` | Expiry tracking, LD non-recovery, vendor concentration |

### Phase 2 — Advanced Tools & Governance

| # | Module | File | Key Features |
|---|---|---|---|
| P22 | **Audit Workflow Engine** | `audit_workflow.py` | Finding lifecycle, SLA tracking, audit trail history |
| P23 | **NLP Document Intelligence** | `nlp_document_intelligence.py` | LLM extraction from emails, board papers, contracts |
| P24 | **Multi-Company Dashboard** | `multi_company_dashboard.py` | Group consolidation view, plant-level filtering |
| P25 | **Statistical Sampling** | `statistical_sampling.py` | MUS, Random, Cell, Stratified sampling methods |
| P26 | **Audit KPI Dashboard** | `audit_kpi_dashboard.py` | Closure rate, productivity metrics, trend analysis |
| P27 | **Audit Session Manager** | `audit_session_manager.py` | Session state management, multi-user support |
| P28 | **Policy Management** | `policy_management.py` | Policy CRUD, version control, review workflow |

---

## 4. CORE ENGINE COMPONENTS

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SARVAGYA ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit UI  │───▶│   Pages (27)    │───▶│  Page Helpers   │
│   (app.py)      │    │                 │    │  (audit_db,     │
└─────────────────┘    └─────────────────┘    │  column_mapper) │
                                              └─────────────────┘
                                                     │
                                                     ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LLM Layer     │◀──▶│  AI Service     │◀───│  RAG Engine     │
│  (Gemini/OpenAI)│    │  (ai_service.py)│    │  (rag_engine.py)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Core Modules  │  │   ML Models     │  │  Vector Store   │
│                 │  │                 │  │                 │
│ • audit_program │  │ • Isolation     │  │  pgvector       │
│ • controls      │  │   Forest       │  │  (Neon Postgres)│
│ • engagements   │  │ • XGBoost      │  │                 │
│ • evidence      │  │ • SHAP         │  │                 │
│ • policy_manager│  │                 │  │                 │
│ • rbac          │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AUDIT TRAIL (SQLite + PostgreSQL)                │
│                                                                     │
│  • audit_findings     • workflow_history     • audit_kpi            │
│  • sampling_runs      • policy_versions     • user_sessions         │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Module Descriptions

| Module | Purpose |
|---|---|
| `audit_program.py` | Generate and manage annual/quarterly audit programs |
| `controls.py` | Maintain control frameworks (COSO, SOX, Ind AS) |
| `engagements.py` | Manage individual audit engagements, scope, and resources |
| `evidence.py` | Evidence collection, documentation, and retention |
| `init_audit_system.py` | System initialization, migration, health checks |
| `policy_manager.py` | Policy CRUD, versioning, approval workflow |
| `policy_review.py` | Periodic policy review scheduling and tracking |
| `rbac.py` | Role-based permissions (Admin, Auditor, Viewer) |
| `standards_registry.py` | Audit standards (ISA, SAI, PCAOB, SEBI) |

---

## 5. DATA FLOW DIAGRAM

```
┌──────────────┐
│  User Input  │
│  (CSV/XLSX)  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                       │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │Column Mapper│  │Industry     │  │Compliance          │   │
│  │(auto-detect │  │Filter       │  │Loader              │   │
│  │ columns)    │  │(FMCG/Mfg/   │  │(calendar.yaml)     │   │
│  │             │  │Retail/etc)  │  │                    │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    ML DETECTION LAYER                         │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │Isolation    │  │XGBoost      │  │Statistical          │   │
│  │Forest       │  │Risk         │  │Tests                │   │
│  │(anomalies)  │  │Scorer       │  │(Benford/Z-score)    │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │Autoencoder │  │K-Means      │  │Fuzzy Matching       │   │
│  │(fixed asset│  │Clustering   │  │(Levenshtein)        │   │
│  │ anomalies) │  │(inventory)  │  │                     │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    RAG + LLM LAYER                            │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │pgvector     │  │Gemini 1.5   │  │Policy               │   │
│  │Retrieval    │  │Pro          │  │Referencing          │   │
│  │             │  │(LLM)        │  │(checklist cites)    │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    FINDINGS & REPORTING                       │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │SQLite       │  │PDF Report   │  │Audit Trail          │   │
│  │audit_findings│ │Generator    │  │(workflow_history)   │   │
│  │             │  │             │  │                     │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. DATABASE SCHEMA

### Table: audit_findings

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_id | TEXT | Batch identifier |
| company_code | TEXT | Multi-company support |
| plant_code | TEXT | Location/plant |
| area | TEXT | Audit area (e.g., "Purchasing") |
| checklist_ref | TEXT | Reference (e.g., "Purchasing A.7") |
| finding | TEXT | Finding description |
| amount_at_risk | REAL | ₹ value at risk |
| vendor_name | TEXT | Counterparty name |
| finding_date | TEXT | ISO date |
| period | TEXT | YYYY-MM |
| risk_band | TEXT | CRITICAL/HIGH/MEDIUM/LOW |
| status | TEXT | Open → Under Review → Closed |
| sla_deadline | TEXT | SLA target date |
| assigned_to | TEXT | Owner |
| opened_at | TEXT | Creation timestamp |
| closed_at | TEXT | Closure timestamp |
| days_to_close | INTEGER | Calculated |

### Table: workflow_history

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| finding_id | INTEGER FK | Linked finding |
| old_status | TEXT | Previous status |
| new_status | TEXT | New status |
| changed_by | TEXT | User who changed |
| changed_at | TEXT | Timestamp |
| comment | TEXT | Change comment |

### Table: audit_kpi

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| metric_name | TEXT | KPI name |
| metric_value | REAL | Numeric value |
| period | TEXT | YYYY-MM |
| recorded_at | TEXT | Timestamp |

### Table: sampling_runs

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_name | TEXT | Sample run name |
| population_size | INTEGER | Total items |
| sample_size | INTEGER | Sampled items |
| method | TEXT | MUS/Random/Cell/Stratified |
| confidence_level | REAL | Confidence % |
| materiality_threshold | REAL | Materiality ₹ |
| executed_at | TEXT | Timestamp |

---

## 7. TECHNOLOGY STACK

| Layer | Technology |
|---|---|
| **UI** | Streamlit 1.28+ (multi-page) |
| **LLM** | Gemini 1.5 Pro (primary) / llama.cpp (local) |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` |
| **Vector DB** | pgvector on Neon PostgreSQL |
| **ML** | scikit-learn, XGBoost, SHAP, MLPRegressor |
| **Graph** | NetworkX (relationship analysis) |
| **Rules Engine** | YAML-driven compliance calendar |
| **Audit Trail** | SQLite (`data/audit.db`) + PostgreSQL |
| **PDF Export** | ReportLab |
| **Fuzzy Matching** | fuzzywuzzy + python-Levenshtein |
| **API** | FastAPI |
| **Cache** | Redis |
| **Deployment** | Render (web) + Docker |

---

## 8. PLUGIN ARCHITECTURE

New audit checks can be added by implementing `base_audit_check.py`:

```python
from utils.base_audit_check import BaseAuditCheck

class MyCustomCheck(BaseAuditCheck):
    name = "Custom Vendor Check"
    area = "Purchasing"
    checklist_ref = "A.99"
    
    def run(self, df, config):
        # Your detection logic here
        findings = [...]
        return self.create_findings(findings)
```

---

## 9. NAVIGATION FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN NAVIGATION                          │
└─────────────────────────────────────────────────────────────┘

  Home (app.py)
       │
       ├─── P1-P21: Detection Modules
       │       │
       │       ├── P1  Payment Anomaly → Finding → audit_findings
       │       ├── P5  BRS Reconciliation ──────────────────┼──┐
       │       ├── P8  GST/TDS ─────────────────────────────┼──┼──┐
       │       ├── P10 Duplicate Invoice ────────────────────┼──┼──┼─▶ RAG Policy Ref
       │       └── ...                                       │  │  │
       │                                                     │  │  │
       ├─── P14-P17: Planning & Reporting                     │  │  │
       │       │                                             │  │  │
       │       ├── P14 Audit Planning ───────────────────────┼──┼──┘
       │       ├── P15 Risk Register ─────────────────────────┼──┘
       │       ├── P16 Audit Report Center ───────────────────┘
       │       └── P17 Committee Pack
       │
       ├─── P22-P26: Advanced Tools
       │       │
       │       ├── P22 Audit Workflow ──▶ SLA Tracking ──▶ audit_findings.status
       │       ├── P23 NLP Intelligence
       │       ├── P24 Multi-Company
       │       ├── P25 Statistical Sampling ──▶ sampling_runs
       │       └── P26 KPI Dashboard ──▶ audit_kpi
       │
       ├─── P2 Policy RAG Bot ──▶ pgvector ──▶ Policy Cites
       └─── P3 Dynamic Builder ──▶ audit_program
```

---

## 10. KEY FILE INTERDEPENDENCIES

```
app.py
  ├── requires: pages/*
  ├── requires: core/*
  └── requires: utils/audit_page_helpers.py

pages/* (each page)
  ├── imports: utils/audit_db.py
  ├── imports: utils/column_mapper.py
  ├── imports: services/ai_service.py
  └── optionally: core/rbac.py

services/ai_service.py
  ├── connects: pgvector (policies)
  ├── connects: Gemini API
  └── uses: utils/rag_engine.py

utils/rag_engine.py
  └── uses: pgvector

core/policy_manager.py
  └── manages: config/*.yaml

core/audit_program.py
  └── uses: core/controls.py
```

---

*Last Updated: 2026-05-13 | v2.0*