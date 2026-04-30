# AI AUDIT ENGINEER — MASTER PLANNING DOCUMENT
## Self-Contained Project Bible | Version 5.0 FINAL | 2026-04-25
### Read this once → understand everything → implement the full project

---

## HOW TO USE THIS DOCUMENT (For Future Claude Sessions)

This document contains the complete specification for a 21-project AI-powered Internal Audit platform. When a user hands you this document along with the project folder:
1. Read Sections 1–4 first (identity, codebase state, stack, architecture)
2. Then read the specific project(s) they want you to work on from Section 6
3. Never deviate from the 6 Architectural Principles in Section 4
4. Always implement in the sequence in Section 8 (dependencies matter)
5. Run the verification checklist in Section 10 after each project

---

## SECTION 1: PROJECT IDENTITY

**Project Name:** AI Audit Engineer  
**Creator:** Ashok Kumar Sharma — 17+ years internal audit experience, SAP FICO / MM / FMCG Manufacturing specialist  
**GitHub:** https://github.com/aks2019/ai-audit-engineer-portfolio  
**Deployed URL:** https://aiauditengineer.onrender.com (Render.com free tier)  
**Local Dev:** Windows 11, Python venv, local llama.cpp (Qwen 35B) on port 8080  
**Email:** kr.ashoksharma@gmail.com  

**Mission:** Automate internal audit of an organisation as far as possible using AI — 100% population testing, checklist-grounded findings, RAG-cited policy references, Board-ready reporting.

**Target Users:** Internal auditors in Indian manufacturing / FMCG companies using SAP ERP. Audit findings must cite specific checklist items, SAP T-codes, and comply with Indian statutory requirements (Companies Act, GST, TDS, PF, ESI).

**Current Status (as of 2026-04-25):**
- 4 pages LIVE on Render (Projects 1–4) — with bugs listed in Section 2
- pgvector on Neon PostgreSQL — operational
- Gemini 1.5 Pro API key available via env var GOOGLE_API_KEY
- 17 internal audit checklist Excel files available in `Internal Audit Checklist/` folder
- All 17 checklists need to be ingested into pgvector via `ingest_policies.py`

---

## SECTION 2: CURRENT CODEBASE STATE

### Existing Files (Do Not Delete)
```
app.py                              ← Home page (needs upgrade to 21 links)
pages/
  anomaly_detector.py               ← Project 1 — LIVE, has bugs
  policy_rag_bot.py                 ← Project 2 — local only (LLM bug)
  dynamic_audit_builder.py          ← Project 3 — WIP
  financial_statement_auditor.py    ← Project 4 — thin prototype
utils/
  rag_engine.py                     ← CRITICAL — has 2 blocking bugs
ingest_policies.py                  ← Ingests checklists into pgvector
requirements.txt                    ← Needs updates (Section 3)
Internal Audit Checklist/           ← 17 Excel + 3 MD files (DO NOT MODIFY)
data/                               ← Runtime data dir (create if missing)
```

### Critical Bugs to Fix Before Any New Work

**BUG-1 (blocks Render deployment — all 4 pages):**  DONE
File: `utils/rag_engine.py` — `get_rag_chain()` and `get_free_form_chain()` both hardcode:
```python
ChatOpenAI(base_url="http://127.0.0.1:8080/v1", ...)  # local llama.cpp — fails on Render
```
Fix: Replace with `_get_llm()` function:
```python
def _get_llm():
    if os.getenv("USE_LOCAL_LLM", "false").lower() == "true":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(base_url="http://127.0.0.1:8080/v1", api_key="llama.cpp",
                          model="local", temperature=1.0)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3,
                                  google_api_key=os.getenv("GOOGLE_API_KEY"))
```
SOLUTION: __BUG-1__ (`utils/rag_engine.py`): Added `_get_llm()` to dynamically switch between local `ChatOpenAI` (`USE_LOCAL_LLM=true`) and `ChatGoogleGenerativeAI` (Gemini 1.5 Pro via `GOOGLE_API_KEY`). Both `get_rag_chain()` and `get_free_form_chain()` now use it, unblocking Render deployment.

**BUG-2 (crashes financial_statement_auditor):**  
File: `utils/rag_engine.py` line ~274 — `generate_financial_audit_report()` calls `get_vectorstore()` (throws if DB unavailable). Replace with `_get_vectorstore_safe()` (already exists in the file).

SOLUTION: __BUG-2__ (`utils/rag_engine.py`): `generate_financial_audit_report()` now uses `_get_vectorstore_safe()` instead of bare `get_vectorstore()`. If the DB is unreachable, it returns a graceful offline response, preventing a crash on the financial-statement page.

**BUG-3 (SHAP wrong for IsolationForest):**  
File: `pages/anomaly_detector.py` — `shap.TreeExplainer(iso)` does not work correctly with IsolationForest.  
Fix: `shap.Explainer(iso, X)` — use base Explainer, not TreeExplainer.

SOLUTION: __BUG-3__ (`pages/anomaly_detector.py`): Replaced `shap.TreeExplainer(iso)` with `shap.Explainer(iso, X)` and updated SHAP value access to `explainer(flagged_X).values`, fixing SHAP compatibility with `IsolationForest`.

**BUG-4 (XGBoost missing despite README claim):**  
File: `pages/anomaly_detector.py` — README states XGBoost is used but it is absent from code.  
Fix: Add XGBoost semi-supervised scorer after IsolationForest labels are assigned.

SOLUTION: __BUG-4__ (`pages/anomaly_detector.py`): Added XGBoost semi-supervised refinement after IsolationForest labels are assigned. An `XGBRegressor` is trained on the pseudo-labels and outputs `xgb_risk_score`, aligning live code with the README claim

**BUG-5 (import fails if cwd differs):**  
File: `pages/financial_statement_auditor.py` — missing `sys.path.insert(0, str(Path(__file__).parent.parent))` at top. Add it (anomaly_detector.py already has this correctly).

SOLUTION: __BUG-5__ (`pages/financial_statement_auditor.py`): Added `sys.path.insert(0, str(Path(__file__).parent.parent))` so `utils.rag_engine` imports correctly regardless of cwd, matching the fix already present in `anomaly_detector.py`.

**BUG-6 (incorrect caption):**  
File: `app.py` and `pages/anomaly_detector.py` — "Localhost only" caption is wrong for a Render-deployed app. Remove it.

SOLUTION: - __BUG-6__ (`app.py` & `pages/anomaly_detector.py`): Removed "Localhost only" captions; updated to "Cloud & Local Ready" (app.py) and removed the misleading tag (anomaly_detector.py).
- __Bonus__: Added missing `langchain-openai` to `requirements.txt`

### Key Existing Functions to Reuse (Do Not Rewrite)
- `_get_vectorstore_safe()` — in `utils/rag_engine.py` — safe pgvector connection
- `generate_rag_audit_report()` — in `utils/rag_engine.py` — works correctly, used by P1
- `get_free_form_chain()` — in `utils/rag_engine.py` — needs BUG-1 fix then reusable
- `_generate_report_pdf()` — in `pages/anomaly_detector.py` — reuse pattern for all PDF exports

---

## SECTION 3: TECHNOLOGY STACK

### Core Dependencies (full requirements.txt)
```
streamlit>=1.35.0
pandas>=2.0.0
numpy>=1.26.0
scikit-learn>=1.4.0
xgboost>=2.0.0
shap>=0.45.0
plotly>=5.18.0
langchain>=0.2.0
langchain-google-genai>=2.0.0
langchain-openai>=0.1.0
langchain-community>=0.2.0
langchain-huggingface>=0.0.3
google-generativeai>=0.8.0
psycopg2-binary>=2.9.0
pgvector>=0.2.4
sentence-transformers>=3.0.0
pypdf>=4.0.0
reportlab>=4.0.0
prophet>=1.1.5
networkx>=3.2
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.25.0
openpyxl>=3.1.0
pyyaml>=6.0
python-dateutil>=2.9.0
prefect>=2.16.0
```

### Environment Variables (Render + local .env)
```
GOOGLE_API_KEY=<Gemini API key>          # Required on Render
USE_LOCAL_LLM=false                       # Set true for local dev with llama.cpp
DATABASE_URL=<Neon PostgreSQL URL>        # pgvector connection
```

### Key Technical Choices (Locked In — Do Not Change)
- **LLM:** Gemini 1.5 Pro (Render) / llama.cpp local — switched via `USE_LOCAL_LLM` env var
- **Embeddings:** `all-MiniLM-L6-v2` (HuggingFace) — free, no API key needed
- **Vector DB:** pgvector on Neon PostgreSQL — collection name: `audit_policies`
- **Anomaly Detection:** IsolationForest (contamination=0.05) + XGBoost (semi-supervised)
- **Explainability:** SHAP — `shap.Explainer(model, X)` for all models
- **Audit Trail:** SQLite at `data/audit.db` — all pages write findings here
- **PDF Export:** ReportLab — pattern from `_generate_report_pdf()` in anomaly_detector.py
- **Autoencoder:** `sklearn.neural_network.MLPRegressor` — avoids TensorFlow on Render
- **Scheduling:** Prefect for nightly/weekly automated runs
- **Graph Analysis:** NetworkX for related-party relationship mapping
- **Fuzzy Matching:** fuzzywuzzy + Levenshtein for invoice deduplication

---

## SECTION 4: ARCHITECTURAL PHILOSOPHY (Never Deviate)

These six principles govern every line of code across all 21 projects:

**Principle 1 — Zero Hardcoded Column Names**  
ML logic and rule engines ONLY use internal standard column names (e.g., `amount`, `vendor_name`, `days_overdue`). Every page has a mapping UI at the top. `utils/column_mapper.py` handles synonym detection and profile persistence. SAP may export `WRBTR` or `NET_AMOUNT` — the mapper converts to `amount` before any logic runs.

**Principle 2 — Zero Hardcoded Compliance Dates**  
GST due dates, TDS rates, PF/ESI percentages, LD rates — ALL live in `config/compliance_calendar.yaml`. Users edit the YAML when government changes law. No code change is ever needed for regulatory updates.

**Principle 3 — Zero Z-Tcode Dependency**  
SAP Z-Tcodes (ZVOTAGE, ZCOTAGEN, ZMFGSTK, ZWR, ZPRD) are company-specific — different companies have different ones. Program logic accepts any CSV/Excel export regardless of which T-code produced it, as long as columns are mapped. For every Z-Tcode mentioned, the UI always shows the standard SAP alternative (see Section 9).

**Principle 4 — Plugin Architecture**  
Every audit check is a class implementing `BaseAuditCheck` (in `utils/base_audit_check.py`). Adding a new audit check means writing one new class — zero changes to any existing page or engine. The check registers itself; pages enumerate available checks dynamically.

**Principle 5 — Industry-Agnostic Core**  
IsolationForest, XGBoost, SHAP, RAG, LangGraph — all engines are universal. Only `config/industry_profiles/` YAML files control which modules are active, which thresholds apply, which compliance sections are highlighted. The same codebase serves Manufacturing, IT Services, Healthcare, Retail, and Financial Services.

**Principle 6 — Shared Audit Trail (SQLite)**  
Every detection page (Projects 1–14, 18–21) writes its findings to `data/audit.db → audit_findings` table. Projects 15 (Risk Register), 16 (MIS Report), and 17 (Audit Committee Pack) read from this single source of truth. No page is a silo. Schema:
```sql
CREATE TABLE IF NOT EXISTS audit_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    area TEXT,
    checklist_ref TEXT,
    finding TEXT,
    amount_at_risk REAL,
    vendor_name TEXT,
    finding_date TEXT,
    period TEXT,
    risk_band TEXT,
    status TEXT DEFAULT 'Open'
);
```

---

## SECTION 5: INFRASTRUCTURE PRE-REQUISITES

Build these FIRST — all 21 projects depend on them.

### PRE-1: Fix `utils/rag_engine.py` (BUG-1 + BUG-2)
Replace all hardcoded `ChatOpenAI(base_url=...)` with `_get_llm()`. Replace `get_vectorstore()` call in `generate_financial_audit_report` with `_get_vectorstore_safe()`.

### PRE-2: Create `utils/column_mapper.py`
```python
# Standard internal concept names — NEVER change in logic code
STANDARD_CONCEPTS = {
    "payment_anomaly": ["amount", "vendor_name", "posting_date", "document_date",
                        "days_overdue", "related_party", "invoice_number",
                        "credit_terms_days", "tolerance_override_flag", "plant_code"],
    "inventory": ["material_code", "material_desc", "plant", "unrestricted_qty",
                  "value", "last_movement_date", "material_type", "shelf_life_expiry",
                  "abc_class", "standard_price"],
    "payroll": ["employee_id", "employee_name", "pan", "bank_account", "department",
                "grade", "basic_da", "gross_salary", "pf_deducted", "esi_deducted",
                "overtime_hours", "last_attendance_date", "status"],
    "sales": ["invoice_no", "customer_name", "invoice_date", "dispatch_date",
              "amount", "discount_pct", "credit_note_no", "return_qty"],
    "contract": ["contract_no", "vendor_name", "start_date", "end_date", "value",
                 "last_payment_date", "ld_rate_pct", "renewal_status"],
    "access": ["user_id", "role", "tcode", "last_login", "status", "department"]
}

# SAP field synonym map — auto-detect column mapping
SYNONYMS = {
    "amount": ["amount", "net_amount", "wrbtr", "gross_amount", "payment_amount",
               "inv_amount", "bill_amount", "total", "value", "dmbtr", "netwr"],
    "vendor_name": ["vendor_name", "vendor", "lifnr", "supplier", "party_name",
                    "creditor", "name_1", "vendor_description", "kred"],
    "posting_date": ["posting_date", "budat", "post_date", "value_date", "date"],
    "days_overdue": ["days_overdue", "overdue_days", "aging_days", "days_outstanding"],
    "material_code": ["material_code", "matnr", "material", "mat_no", "item_code"],
    "employee_id": ["employee_id", "emp_id", "pernr", "staff_id", "personnel_no"],
    "pan": ["pan", "pan_no", "pan_number", "tax_id"],
    "invoice_no": ["invoice_no", "invoice_number", "vbeln", "belnr", "bill_no"],
}

def auto_suggest_mapping(df_columns: list, module: str) -> dict:
    suggestions = {}
    for concept in STANDARD_CONCEPTS.get(module, []):
        for col in df_columns:
            if col.lower().strip() in SYNONYMS.get(concept, []):
                suggestions[concept] = col
                break
    return suggestions

def save_profile(profile_name: str, module: str, mapping: dict, company: str = ""):
    from pathlib import Path; import json
    d = Path("data/column_profiles"); d.mkdir(parents=True, exist_ok=True)
    (d / f"{profile_name}.json").write_text(
        json.dumps({"profile_name": profile_name, "company": company,
                    "module": module, "mapping": mapping}, indent=2))

def load_profile(profile_name: str) -> dict:
    from pathlib import Path; import json
    return json.loads((Path("data/column_profiles") / f"{profile_name}.json").read_text())

def list_profiles(module: str) -> list:
    from pathlib import Path; import json
    d = Path("data/column_profiles")
    return [json.loads(f.read_text())["profile_name"]
            for f in d.glob("*.json")
            if json.loads(f.read_text()).get("module") == module]
```

**UI Pattern for every page (mandatory):**
```python
# 1. Upload file
# 2. Auto-suggest mapping (synonym detection)
auto_map = auto_suggest_mapping(df.columns.tolist(), module="payment_anomaly")
# 3. Show mapping UI — user confirms/corrects
# 4. Option to load saved profile
# 5. Save profile for next time
# 6. Run logic — ONLY on standardised column names
```

### PRE-3: Create `config/compliance_calendar.yaml`
```yaml
gst:
  GSTR-1_monthly:
    description: "Monthly outward supply (turnover >5 Cr)"
    due_day_of_following_month: 11
  GSTR-3B_category_1:
    description: "Monthly summary return — 28 states"
    due_day_of_following_month: 20
  GSTR-3B_category_2:
    due_day_of_following_month: 22
  GSTR-3B_category_3:
    due_day_of_following_month: 24
  GSTR-9:
    description: "Annual return"
    due_date: "December 31 of following year"

tds:
  general_deposit:
    due_day_of_following_month: 7
    march_exception: "April 30"
  sections:
    "194C": {description: "Contractor payments", rate_individual: 1.0, rate_company: 2.0, single_threshold: 30000, annual_threshold: 100000}
    "194I": {description: "Rent - land/building", rate: 10.0, threshold: 240000}
    "194J": {description: "Professional services", rate: 10.0, threshold: 30000}
    "194H": {description: "Commission/brokerage", rate: 5.0, threshold: 15000}
    "194A": {description: "Interest (non-bank)", rate: 10.0, threshold: 5000}
    "192":  {description: "Salary", rate: "Slab rate"}
    "195":  {description: "Non-resident payments", rate: "DTAA rate"}
  quarterly_returns:
    Q1: "July 31"
    Q2: "October 31"
    Q3: "January 31"
    Q4: "May 31"

pf:
  employee_rate: 12
  employer_rate: 12
  wage_ceiling: 15000
  due_day_of_following_month: 15

esi:
  employee_rate: 0.75
  employer_rate: 3.25
  wage_ceiling: 21000
  due_day_of_following_month: 15

contract_labour:
  registration_renewal: "Annual"
  form_v_required: true
  pf_esi_verification_required: true

audit_committee:
  companies_act_section: 177
  sebi_lodr_regulation: 18
  minimum_meetings_per_year: 4
  mandatory_agenda_items:
    - "Financial statements review"
    - "Related party transactions"
    - "Internal audit findings"
    - "Internal control adequacy"

payroll:
  overtime_quarterly_max_hours: 50
  advance_max_months_salary: 2
  self_approval_blocked: true

fixed_assets:
  cwip_max_outstanding_months: 12
  capex_approval_threshold: 100000
  revenue_keywords: ["repair", "maintenance", "consumable", "amc", "whitewash", "cleaning"]
  depreciation_rates:
    "Plant & Machinery": 6.67
    "Buildings (Factory)": 3.34
    "Furniture & Fixtures": 10.0
    "Computers": 33.33
    "Vehicles": 9.5
```

### PRE-4: Create `utils/base_audit_check.py`
```python
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
        return flagged_df

    def rag_prompt(self, flagged_rows: list) -> str:
        return f"Audit flagged items per {self.checklist_ref}: {flagged_rows}"

    def validate_columns(self, df: pd.DataFrame) -> list:
        return [c for c in self.required_columns if c not in df.columns]

    def log_to_db(self, flagged_df: pd.DataFrame, area: str, period: str, run_id: str):
        """Write findings to shared SQLite audit trail."""
        import sqlite3, json
        conn = sqlite3.connect("data/audit.db")
        for _, row in flagged_df.head(100).iterrows():
            conn.execute("""INSERT INTO audit_findings
                (run_id, area, checklist_ref, finding, amount_at_risk, vendor_name,
                 finding_date, period, risk_band)
                VALUES (?,?,?,?,?,?,date('now'),?,?)""",
                (run_id, area, self.checklist_ref,
                 row.get("flag_reason", "Anomaly detected"),
                 float(row.get("amount", 0)),
                 str(row.get("vendor_name", "")),
                 period, "HIGH"))
        conn.commit(); conn.close()
```

### PRE-5: Create `config/industry_profiles/` (5 YAML files)

**manufacturing_fmcg.yaml** (default — all 21 modules)
```yaml
industry: "Manufacturing / FMCG"
modules_enabled: "all"
thresholds:
  slow_moving_inventory_days: 90
  days_overdue_critical: 60
  credit_utilization_warning_pct: 80
  expense_daily_limit_grade_a: 5000
  amc_vendor_concentration_pct: 40
compliance_focus: [gst_full, tds_all_sections, pf, esi, contract_labour]
tds_high_risk: ["194C", "194I", "194J"]
```

**it_services.yaml** (no inventory, no contract labour)
```yaml
industry: "IT Services"
modules_disabled: ["inventory_anomaly", "contract_management"]
thresholds:
  days_overdue_critical: 45
  expense_daily_limit_grade_a: 8000
  amc_vendor_concentration_pct: 60
compliance_focus: [gst_18pct, tds_194J_primary, tds_194C]
tds_high_risk: ["194J", "194C", "194N"]
```

**healthcare_pharma.yaml**
```yaml
industry: "Healthcare / Pharma"
modules_enabled: "all"
thresholds:
  slow_moving_inventory_days: 30
  shelf_life_warning_days: 180
compliance_focus: [gst_multiple_slabs, tds_all, cdsco]
```

### PRE-6: Create `utils/audit_db.py` (shared SQLite helper)
```python
import sqlite3
from pathlib import Path

def init_audit_db():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect("data/audit.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT, area TEXT, checklist_ref TEXT, finding TEXT,
        amount_at_risk REAL, vendor_name TEXT, finding_date TEXT,
        period TEXT, risk_band TEXT, status TEXT DEFAULT 'Open'
    )""")
    conn.commit(); conn.close()

def load_findings(period: str = None, risk_bands: list = None) -> "pd.DataFrame":
    import pandas as pd
    conn = sqlite3.connect("data/audit.db")
    q = "SELECT * FROM audit_findings WHERE 1=1"
    params = []
    if period: q += " AND period=?"; params.append(period)
    if risk_bands: q += f" AND risk_band IN ({','.join('?'*len(risk_bands))})"; params += risk_bands
    df = pd.read_sql_query(q, conn, params=params)
    conn.close(); return df

def compute_risk_score(amount_at_risk: float, recurrence_count: int) -> tuple:
    impact = 1 + (amount_at_risk > 100000) + (amount_at_risk > 1000000) + \
             (amount_at_risk > 5000000) + (amount_at_risk > 10000000)
    likelihood = 1 if recurrence_count == 1 else (3 if recurrence_count == 2 else 5)
    score = impact * likelihood
    band = "CRITICAL" if score >= 20 else "HIGH" if score >= 12 else \
           "MEDIUM" if score >= 6 else "LOW"
    return score, band
```

### PRE-7: Ingest All 17 Checklists into pgvector
Run `ingest_policies.py` with metadata: `{"domain": "procurement", "checklist_item": "D.8", "industry": "manufacturing"}`
Files in `Internal Audit Checklist/` — all 17 must be indexed before RAG works properly.

### PRE-8: Update `requirements.txt` with full stack from Section 3.

---

## SECTION 6: ALL 21 PROJECT PLANS

---

### P1: PAYMENT ANOMALY DETECTOR
**File:** `pages/anomaly_detector.py` | **Status:** LIVE — needs upgrades

**Checklist refs:** SAP Unit 1.18 (ZVOTAGE→FBL1N), 1.30, 1.34; Vendor Mgmt E.1–E.4; Purchasing D.3–D.8

**Detection model:**
```python
# Step 1: IsolationForest
X = df[["amount", "days_overdue", "related_party"]].fillna(0)
iso = IsolationForest(contamination=0.05, random_state=42)
df["if_label"] = iso.fit_predict(X)  # -1=anomaly, 1=normal
df["if_prob"] = 1 - (iso.decision_function(X) - min) / (max - min + 1e-8)

# Step 2: XGBoost semi-supervised (BUG-4 fix — add this)
from xgboost import XGBClassifier
y_pseudo = (df["if_label"] == -1).astype(int)
xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")
xgb.fit(X, y_pseudo)
df["xgb_prob"] = xgb.predict_proba(X)[:, 1]

# Step 3: Ensemble
df["final_risk"] = 0.6 * df["if_prob"] + 0.4 * df["xgb_prob"]

# Step 4: SHAP (BUG-3 fix)
explainer = shap.Explainer(iso, X)   # NOT TreeExplainer
```

**Checklist-grounded rules (add to existing):**
- Credit breach: `days_overdue > credit_terms_days` (Vendor Checklist E.1)
- Tolerance override: `tolerance_override_flag == 1` (Purchasing D.7)
- Related-party anomaly: `related_party == 1 AND final_risk > 0.8` (Vendor Mgmt B.3)

**Metrics (4th metric to add):** "Overdue Credit Exposure ₹" (sum of amount where days_overdue > credit_terms_days)

**Benford's Law (add as expander):** First-digit frequency chart on `amount` column.

**SAP standard alt shown in UI:** FBL1N, S_ALR_87012085 (instead of ZVOTAGE)

**SQLite logging:** Call `BaseAuditCheck.log_to_db()` after flagging.

---

### P2: POLICY RAG BOT
**File:** `pages/policy_rag_bot.py` | **Status:** Local only (BUG-1)

**Fix BUG-1 first** — then functional on Render.

**Upgrades:**
1. Department routing → domain-filtered pgvector retrieval (filter by `domain` metadata)
2. LangGraph 3-node agent: `Extract → PolicyRAGCheck → AuditSummaryWriter`
3. SAP T-Code Quick Lookup in sidebar (standard T-codes from indexed checklist)
4. Compliance query: "Has GSTR-3B due date changed?" → RAG on indexed circulars
5. Excel export: Timestamp | Question | Answer | Checklist Items Cited | Sources | Log Hash
6. Industry profile switcher button

---

### P3: DYNAMIC AUDIT BUILDER
**File:** `pages/dynamic_audit_builder.py` | **Status:** WIP

**Existing templates (5):** Back-dated entries, Payment Anomaly, GRN Mismatch, Duplicate, ML Outlier

**New templates to add (5 more — checklist-grounded):**
1. **PO/DOA Approval Breach** — Purchasing A.8, A.22: `amount > approval_limit AND approver missing`
2. **Purchase Price Variance ≥5%** — SAP 1.5 / RM06IBP0: `|po_rate - inv_rate|/po_rate > 5%`
3. **Sub-Ledger to GL Mismatch** — F&A A.3 / FBL3N: upload two files, flag balance differences
4. **Round-Figure / Payment Splitting** — Purchasing D.8: `amount % 1000 == 0 OR split below threshold`
5. **Vendor Balance Ageing — Unadjusted Debits** — F&A A.7: debit balances >90 days

**Each template = one `BaseAuditCheck` subclass.**

---

### P4: FINANCIAL STATEMENT CONTINUOUS AUDITOR
**File:** `pages/financial_statement_auditor.py` | **Status:** Thin prototype (76 lines)

**Fix BUG-5 first** (add sys.path.insert). **Fix BUG-1** (LLM).

**Major upgrade — target ~350 lines:**
1. Ind AS compliance checks (6 rules): each shows Value | Status | Checklist Ref | Audit Action | SAP T-Code
2. Budget vs Actual variance table (upload budget file) — F&A B.2
3. Prior period comparison (upload two TBs) — S_PL0_86000028
4. TDS/statutory compliance summary from compliance_calendar.yaml (F&A C.10–C.21)
5. Autoencoder anomaly on BS/P&L values (MLPRegressor)
6. Prophet trend if 3+ monthly TBs uploaded

---

### P5: BRS ANOMALY & AUTO-MATCHING AGENT
**New file:** `pages/brs_reconciliation.py`

**Checklist refs:** SAP 1.33 (FF67/FBL3N); Treasury A.2, A.3, A.10, A.13, A.14e, A.20

**SAP standard (no Z-Tcode needed):** FF67 + FBL3N

**Build:**
1. Column mapping UI (bank statement + GL columns)
2. Auto-matching: amount ±₹0.01, date ±3 days
3. Rules: Bank credit delay >5 days (HO 1a), Stale cheques >6 months (HO 1b), Cash not deposited same day (A.20)
4. IsolationForest + XGBoost on unmatched items
5. BRS summary table, PDF export, SQLite log

---

### P6: CUSTOMER RECEIVABLES & BAD DEBT DETECTOR
**New file:** `pages/receivables_bad_debt.py`

**Checklist refs:** SAP Depot 5 (ZCOTAGEN→FBL5N), SAP HO 15; Credit policy

**SAP standard alt:** FBL5N, S_ALR_87012197 (instead of ZCOTAGEN)

**Build:**
1. >60 days critical (Depot 5 exact threshold)
2. Opportunity cost = `outstanding × 12% / 365 × days_overdue` (SAP HO 15)
3. Credit limit breach detection
4. XGBoost bad debt classifier + DBSCAN clustering
5. Prophet DSO forecasting (3+ monthly uploads)
6. SHAP per customer

---

### P7: UNIFIED ANOMALY INTELLIGENCE DASHBOARD
**New file:** `pages/unified_dashboard.py`

**Sections:**
1. Overall Risk Score gauge (ensemble of all modules via SQLite)
2. 30-day anomaly trend
3. Top vendors by risk | Department heat map
4. Compliance calendar — next 7 due dates (from YAML)
5. SAP Checklist Coverage % across all 17 files
6. Industry profile indicator + switch
7. Audit Committee export pack (ZIP of all current reports)

---

### P8: GST/TDS COMPLIANCE MISMATCH ENGINE
**New file:** `pages/gst_tds_compliance.py`

**Two tabs — different data flows:**

**Tab 1 — GST:**
- GSTR-2A vs books: 4 mismatch types (books not in 2A, 2A not in books, amount mismatch >₹100, GSTIN mismatch)
- ITC eligibility: Section 17(5) blocked items check
- ITC reversal: Rule 42/43 (mixed supplies)
- Filing timeliness: due dates from compliance_calendar.yaml (never hardcoded)
- Late fee: ₹50/day from CGST Act → in YAML

**Tab 2 — TDS:**
- Rate validation by section (from compliance_calendar.yaml sections map)
- Deposit timeliness (7th / 30th April from YAML)
- Interest: Section 201(1A) — 1.5%/month from YAML
- Form 26AS reconciliation
- Quarterly return timeliness (Q1–Q4 from YAML)

**VAT/Excise: NOT implemented** — obsolete since July 2017 GST rollout.

---

### P9: RELATED-PARTY TRANSACTIONS MONITOR
**New file:** `pages/related_party_monitor.py`

**Checklist refs:** Vendor Mgmt B.3–B.8, B.18; Purchasing A.5, A.34; SAP 1.30

**SAP standard alt:** FK03 (standard — not Z-Tcode)

**Build:**
1. Vendor master duplicates: same PAN, same bank account, same address
2. Director-vendor graph (NetworkX): shared PAN/entity
3. IsolationForest on: year-end clustering, round amounts, related-party flag
4. SOX/ICFR: missing board approval per DOA (A.34)
5. Related-party % of total procurement (concentration)
6. RAG cites B.3–B.8, Companies Act Section 188, SEBI LODR

---

### P10: DUPLICATE PAYMENTS & INVOICE FRAUD DETECTOR
**New file:** `pages/duplicate_invoice_detector.py`

**Checklist refs:** Purchasing D.3–D.12; SAP 1.4, 1.5, 1.6

**Build:**
1. Exact duplicate: `vendor_code + invoice_number + amount`
2. Fuzzy: Levenshtein >85% on invoice number + amount within ₹500
3. PO vs invoice rate variance ≥5% (SAP 1.5)
4. Payment splitting: same vendor + same day + total > approval limit
5. Tolerance override (D.7)
6. IsolationForest + XGBoost + SHAP
7. Benford's Law on invoice amounts (expander section)
8. SAP block recommendation: `fraud_score > 0.85 → "Block via FB02 — Payment Block = A"`

---

### P11: INVENTORY VALUATION & SLOW-MOVING STOCK DETECTOR
**New file:** `pages/inventory_anomaly.py`

**Checklist refs:** Inventory Mgmt A.6–A.11 (341-item checklist); SAP 1.9, 1.10, 1.11, 1.12, 1.13, 1.17, 1.19, 1.26

**SAP standard alts:** ZMFGSTK → MB52 + MB5M; ZWR/ZWR1 → MB51 (mvt 551/552)

**Thresholds from industry profile (never hardcoded):**
- Manufacturing: slow_moving_threshold_days = 90
- Healthcare/Pharma: slow_moving_threshold_days = 30

**Build:**
1. Slow-moving: `last_movement_date` gap > threshold from profile
2. Expiry: `shelf_life_expiry < today + 180 days`
3. Duplicate material codes (A.7)
4. A/B/C classification mismatch
5. Physical vs book (MI24 equivalent — A.19)
6. K-Means (4 clusters: Fast/Normal/Slow/Obsolete)
7. XGBoost write-off risk + SHAP

---

### P12: FIXED ASSET ADDITION & DEPRECIATION AUDITOR
**New file:** `pages/fixed_asset_auditor.py`

**Checklist refs:** Fixed Assets A.1–A.13, B.1–B.41 (71 items)

**Rules (rates from compliance_calendar.yaml):**
- Revenue vs capital: flag if `description` contains any keyword from `fixed_assets.revenue_keywords` in YAML
- CWIP >12 months outstanding (B.4 — threshold from YAML)
- Depreciation rate variance: applied_rate vs Companies Act rate (from YAML)
- Unapproved additions: `capex_value > fixed_assets.capex_approval_threshold` AND no approval
- Autoencoder on asset register values
- Depreciation schedule generator

---

### P13: EXPENSE & TRAVEL CLAIM AUDITOR
**New file:** `pages/expense_claim_auditor.py`

**Checklist refs:** Payroll Mgmt 7a, 14, 15, 21; SAP Depot 12, l

**Policy limits from industry profile YAML (never hardcoded):**
```yaml
expense_policy:
  grade_daily_limits: {"Grade A": 5000, "Grade B": 3000, "Grade C": 2000}
  max_claim_without_docs: 500
  self_approval_blocked: true
  alcohol_entertainment_blocked: true
```

**Rules:** Over-limit claim, weekend claim without justification, self-approved, no supporting documents, IsolationForest + XGBoost

---

### P14: PREDICTIVE RISK-BASED AUDIT PLANNING ENGINE
**New file:** `pages/audit_planning_engine.py`

**Key feature:** Checklist Automation Coverage Report — maps each of ~1000 checklist items to: Automated (by which project) / Partial / Manual-only (= next automation candidate)

**LangGraph 3-node agent:** Planner → Researcher (RAG) → Reporter (Annual Plan)

**Annual plan output:** Audit Area | Risk Score | Quarter | Audit Days | Key Risks | Checklist Ref | SAP T-Code | Standard Alt

---

### P15: AUDIT RISK REGISTER & PRIORITY MAPPING
**New file:** `pages/risk_register.py`

**Reads from:** `data/audit.db audit_findings` table (written by all detection pages)

**Risk scoring (from `utils/audit_db.py compute_risk_score()`):**
- Impact = 1–5 based on amount_at_risk (₹0–1L=1, ₹1–10L=2, ₹10–50L=3, ₹50L–1Cr=4, >1Cr=5)
- Likelihood = 1–5 based on recurrence (first=1, 2x=3, chronic 3+=5)
- Risk Score = Impact × Likelihood (max 25)
- Band: CRITICAL ≥20, HIGH ≥12, MEDIUM ≥6, LOW <6

**UI Sections:**
1. 5×5 Risk Heat Map (Plotly — red=CRITICAL, orange=HIGH, yellow=MEDIUM, green=LOW)
2. Risk-Ranked Findings Table (filter by area, period, band, status)
3. Auto Audit Priority Plan: CRITICAL→Q1, HIGH→Q2, MEDIUM→Q3, LOW→Q4
4. Department-wise risk exposure bar chart
5. Trend: this period vs last period
6. Excel download (standard internal audit risk register format)

---

### P16: AUDIT REPORT CENTER + MIS AUDIT REPORT
**New file:** `pages/audit_report_center.py`

**Tab 1 — Centralized Report Center:**
- Reads all RAG reports saved to SQLite for selected period
- Timeline: Area | Date | Finding Count | Risk Band | Status
- LLM synthesizes Combined Executive Summary across all areas via `_get_llm()`
- Downloads: Single multi-section PDF | Excel workbook (one tab per area)

**Tab 2 — MIS Audit Report (CFO-Ready):**
- Period selector: Q1/Q2/Q3/Q4/H1/H2/Annual
- Filter: HIGH + CRITICAL only
- LLM auto-drafts 6 sections:
  1. Executive Summary (3-4 lines)
  2. Risk Summary Table — Area | Finding | ₹ Impact | Risk Band | Status
  3. Compliance Gap Summary (GST/TDS/PF/ESI from calendar + findings)
  4. Top 10 Critical Observations (ranked by risk_score)
  5. Trend Analysis — better/worse vs last period (SQLite)
  6. Recommendations
- PDF: ReportLab with clean section headers
- Editable fields before download: Organisation, Period, Prepared by, Reviewed by

---

### P17: AUDIT COMMITTEE REPORT PACK
**New file:** `pages/audit_committee_pack.py`

**Regulatory basis:** Companies Act Section 177 + SEBI LODR Regulation 18 (listed entities)
**Config:** `compliance_calendar.yaml → audit_committee` section

**4 Sections (all editable before PDF export):**

**Section 1 — ATR (Action Taken Report from Previous Meeting):**
- SQLite query: previous period findings with status = "Management Response" or "Closed"
- Table: Observation | Previous Commitment | Current Status | Verified by Auditor

**Section 2 — New Critical Observations:**
- SQLite query: current period, risk_band IN ('HIGH','CRITICAL')
- Format: Obs No. | Area | Checklist Ref | Finding | Amount at Risk | Root Cause | Recommendation

**Section 3 — Management Response (editable in-app):**
```python
for idx, row in critical_findings.iterrows():
    mgmt_response = st.text_area(f"Management Response #{idx+1}", key=f"resp_{idx}")
    action_owner = st.text_input("Responsible Person", key=f"owner_{idx}")
    due_date = st.date_input("Action Due Date", key=f"due_{idx}")
    # Saved to SQLite for ATR in next period
```

**Section 4 — Board Escalation Items:**
- Auto-flag: risk_band = "CRITICAL" AND recurrence ≥ 2 periods AND status = "Open"

**Export:** Board-ready PDF — observation numbers, response table, auditor sign-off field, logo placeholder

---

### P18: PAYROLL & HR AUDIT
**New file:** `pages/payroll_audit.py`

**Checklist refs:** Payroll Management 1–21; F&A C.10; PF/ESI from compliance_calendar.yaml

**Why critical:** #2 global fraud scheme (ACFE). Ghost employees, PF/ESI mismatches, unauthorized increments — no detection exists currently.

**Key checks:**
```python
class GhostEmployeeCheck(BaseAuditCheck):
    name = "Ghost Employee Detection"
    checklist_ref = "Payroll Mgmt Item 7"
    sap_tcode_primary = "PA30"
    sap_tcode_standard_alt = "S_AHR_61016362"
    required_columns = ["employee_id", "pan", "bank_account", "status", "last_attendance_date"]

    def detect(self, df):
        dup_pan   = df[df.duplicated("pan", keep=False)].copy()
        dup_bank  = df[df.duplicated("bank_account", keep=False)].copy()
        df["days_absent"] = (pd.Timestamp.today() - pd.to_datetime(df["last_attendance_date"])).dt.days
        absent_active = df[(df["status"] == "Active") & (df["days_absent"] > 90)].copy()
        for d in [dup_pan, dup_bank, absent_active]:
            if "flag_reason" not in d.columns:
                d["flag_reason"] = "Ghost employee risk"
        return pd.concat([dup_pan, dup_bank, absent_active]).drop_duplicates("employee_id")

class PFESIMismatchCheck(BaseAuditCheck):
    name = "PF/ESI Statutory Deduction Mismatch"
    checklist_ref = "Payroll Mgmt Item 14 / F&A C.10"
    required_columns = ["employee_id", "basic_da", "pf_deducted", "esi_deducted", "gross_wages"]

    def detect(self, df):
        cal = load_compliance_calendar()
        df = df.copy()
        df["pf_expected"] = df["basic_da"].clip(upper=cal["pf"]["wage_ceiling"]) * cal["pf"]["employee_rate"] / 100
        df["pf_variance"] = abs(df["pf_deducted"] - df["pf_expected"])
        df["esi_applicable"] = df["gross_wages"] <= cal["esi"]["wage_ceiling"]
        df.loc[df["esi_applicable"], "esi_expected"] = df["gross_wages"] * cal["esi"]["employee_rate"] / 100
        df["esi_variance"] = abs(df["esi_deducted"] - df.get("esi_expected", 0))
        flagged = df[(df["pf_variance"] > 1) | (df["esi_variance"] > 1)].copy()
        flagged["flag_reason"] = "PF/ESI deduction mismatch — Payroll Mgmt Checklist 14"
        return flagged
```

**Additional rules:** Salary > grade_max from profile YAML, overtime > Factories Act limit from YAML, self-approved advance (Payroll 15 — SOD).

**Model:** IsolationForest + XGBoost on [gross_salary, overtime_hours, advance_outstanding, leave_encashment].

**SAP T-codes:** `PC00_M99_CALC`, `PA30`, `PT60`, `S_AHR_61016362`

---

### P19: SALES & REVENUE INTEGRITY AUDITOR
**New file:** `pages/sales_revenue_auditor.py`

**Checklist refs:** SAP HO — CSD, Export, CPD, Publicity sections; Ind AS 115

**Why critical:** Revenue is the top line. SAP HO Sales & Marketing section is entirely unaddressed. Ind AS 115 compliance is new and required.

**Key checks:**
```python
class CreditNoteManipulationCheck(BaseAuditCheck):
    name = "Period-End Credit Note Concentration"
    checklist_ref = "SAP HO Sales — Credit Note Pre-Audit"
    sap_tcode_primary = "VF05"
    required_columns = ["credit_note_no", "amount", "document_date", "customer_name"]

    def detect(self, df):
        df = df.copy()
        df["doc_date"] = pd.to_datetime(df["document_date"])
        df["month_end_3d"] = df["doc_date"].dt.day >= 28
        flagged = df[(df["month_end_3d"]) & (df["amount"] > df["amount"].quantile(0.80))].copy()
        flagged["flag_reason"] = "Large credit note in last 3 days of period — revenue understatement risk (SAP HO Sales)"
        return flagged

class IndAS115Check(BaseAuditCheck):
    name = "Ind AS 115 Revenue Recognition Timing"
    checklist_ref = "Ind AS 115 — Control Transfer at Dispatch"
    required_columns = ["invoice_no", "invoice_date", "dispatch_date", "amount"]

    def detect(self, df):
        df = df.copy()
        df["gap_days"] = (pd.to_datetime(df["invoice_date"]) -
                          pd.to_datetime(df["dispatch_date"])).dt.days
        early = df[df["gap_days"] < -1].copy()
        early["flag_reason"] = early["gap_days"].apply(
            lambda x: f"Invoice raised {abs(int(x))} days BEFORE dispatch — Ind AS 115 risk")
        return early
```

**Additional rules:** Discount > approved scheme %, channel stuffing (return rate >10% in period), export without LUT reference, dealer credit limit breach.

**SAP T-codes:** `VF05`, `VA05`, `VKM3`, `S_ALR_87012186`

---

### P20: IT GENERAL CONTROLS & SAP AUTHORIZATION AUDIT
**New file:** `pages/itgc_sap_access_auditor.py`

**Regulatory mandate:** Companies Act Section 143(3)(i) — internal financial controls reporting mandatory.

**No ML needed — rule-based SoD matrix + access anomaly detection.**

**Built-in SoD Conflict Matrix:**
```python
SOD_CONFLICTS = [
    {"a": "FK01", "b": "F110", "risk": "CRITICAL", "desc": "Vendor Create + Payment Run — complete financial fraud cycle", "ref": "COSO Principle 10"},
    {"a": "ME21N","b": "MIGO", "risk": "CRITICAL", "desc": "PO Create + GRN Approval — procurement fraud cycle", "ref": "Purchasing A.22"},
    {"a": "PC00", "b": "PA30", "risk": "CRITICAL", "desc": "Payroll Run + HR Master — ghost employee creation", "ref": "Payroll Mgmt 15"},
    {"a": "FD01", "b": "VF11", "risk": "HIGH",     "desc": "Customer Create + Invoice Cancel — revenue manipulation"},
    {"a": "FB50", "b": "FBV0", "risk": "HIGH",     "desc": "Journal Entry + Journal Approval — financial statement manipulation"},
    {"a": "FS00", "b": "FB50", "risk": "HIGH",     "desc": "GL Account Create + Journal Post — fictitious account risk"},
]

def check_sod_conflicts(user_access_df):
    conflicts = []
    for c in SOD_CONFLICTS:
        a_users = set(user_access_df[user_access_df["tcode"] == c["a"]]["user_id"])
        b_users = set(user_access_df[user_access_df["tcode"] == c["b"]]["user_id"])
        for user in a_users & b_users:
            conflicts.append({**c, "user_id": user})
    return pd.DataFrame(conflicts)
```

**Additional checks:**
- Privileged access: SAP_ALL / SAP_NEW role assigned to non-IT users
- Inactive users: last_login > 90 days AND status = Active
- Generic IDs: user_id in ["ADMIN", "TEST", "TEMP", "BACKUP"]
- SM20 audit log: critical T-code (F110, PA30) executed outside business hours or by unauthorized user

**Two data inputs:** (1) SUIM user access dump, (2) SM20 security audit log (both column-mapped)

**Output:** SoD Conflict Register (standard IA deliverable): User | Conflict | Risk | Recommendation | Ref

**SAP T-codes:** `SU01`, `SUIM`, `SM20`, `SM19`, `S_BCE_68001402`, `RSUSR002`

---

### P21: CONTRACT & AMC MANAGEMENT AUDITOR
**New file:** `pages/contract_management_auditor.py`

**Checklist refs:** Purchasing A.1–A.8; SAP HO AMC section; Contract Labour Act 1970 (from compliance_calendar.yaml)

**Why critical:** Expired AMC payments, unrecovered LD, concentration risk — chronic FMCG audit findings currently unaddressed.

**Key checks:**
```python
class ContractExpiryCheck(BaseAuditCheck):
    name = "Contract Expiry & Post-Expiry Payment"
    checklist_ref = "Purchasing A.4 — Contract Renewal Control"
    sap_tcode_primary = "ME33K"
    sap_tcode_standard_alt = "ME2K (POs per contract)"
    required_columns = ["contract_no", "vendor_name", "end_date", "last_payment_date"]

    def detect(self, df):
        today = pd.Timestamp.today()
        df = df.copy()
        df["days_to_expiry"] = (pd.to_datetime(df["end_date"]) - today).dt.days
        expiring = df[df["days_to_expiry"].between(0, 90)].copy()
        expiring["flag_reason"] = expiring["days_to_expiry"].apply(lambda x: f"Expiring in {int(x)} days")
        post = df[pd.to_datetime(df["last_payment_date"]) > pd.to_datetime(df["end_date"])].copy()
        post["flag_reason"] = "Payment after contract expiry — unauthorized continuation"
        return pd.concat([expiring, post])

class LDNonRecoveryCheck(BaseAuditCheck):
    name = "Liquidated Damages Non-Recovery"
    checklist_ref = "Purchasing A.7 — Penalty Clause Enforcement"
    required_columns = ["contract_no", "vendor_name", "delivery_date_agreed",
                        "delivery_date_actual", "ld_rate_pct", "contract_value", "ld_recovered"]

    def detect(self, df):
        df = df.copy()
        df["delay_days"] = (pd.to_datetime(df["delivery_date_actual"]) -
                            pd.to_datetime(df["delivery_date_agreed"])).dt.days.clip(lower=0)
        df["ld_applicable"] = df["delay_days"] * df["ld_rate_pct"] / 100 / 30 * df["contract_value"]
        flagged = df[(df["delay_days"] > 0) & (df["ld_recovered"] < df["ld_applicable"] * 0.9)].copy()
        flagged["flag_reason"] = flagged.apply(
            lambda r: f"LD ₹{r['ld_applicable']:,.0f} due ({r['delay_days']}d delay), ₹{r['ld_recovered']:,.0f} recovered",
            axis=1)
        return flagged
```

**Additional rules:** AMC vendor concentration > 40% of total spend (from profile YAML), rate escalation beyond WPI index, Contract Labour Act: `contractor_pf_esi_verified = False`.

**Benford's Law on contract values** — detects bid manipulation.

**SAP T-codes:** `ME33K`, `ME2K`, `ME35K`, `ME31K`

---

### CROSS-CUTTING: BENFORD'S LAW ANALYSIS
**Add to:** P1 (anomaly_detector.py) and P10 (duplicate_invoice_detector.py) as `st.expander`

```python
def benford_analysis(amounts: pd.Series) -> pd.DataFrame:
    expected = {1:30.1, 2:17.6, 3:12.5, 4:9.7, 5:7.9, 6:6.7, 7:5.8, 8:5.1, 9:4.6}
    first_digits = amounts[amounts > 0].astype(str).str[0].astype(int)
    observed = first_digits.value_counts(normalize=True).sort_index() * 100
    result = pd.DataFrame({"digit": list(expected.keys()),
                           "expected_pct": list(expected.values()),
                           "observed_pct": [observed.get(d, 0) for d in expected]})
    result["deviation"] = abs(result["observed_pct"] - result["expected_pct"])
    result["flag"] = result["deviation"] > 5
    return result
# Display as side-by-side bar chart — flagged digits in red
```

---

## SECTION 7: DESIGN DECISIONS (5 Strategic Questions — Answers Locked In)

**Q1 — SAP column headers differ from program logic:**  
Solution: `utils/column_mapper.py` (PRE-2). Three layers: synonym auto-detection → manual mapping UI → named company profiles (save once, reuse always). Zero column names hardcoded in ML/rule logic. All logic uses internal standard names only.

**Q2 — SAP Z-Tcode reports are company-specific:**  
Solution: Every Z-Tcode is documentation-only in this project. UI always shows standard SAP alternative. Program logic accepts any CSV/Excel from any T-code as long as columns are mapped. See Section 9 for full Z-Tcode → standard mapping table.

**Q3 — GST/TDS compliance dates change with government law:**  
Solution: `config/compliance_calendar.yaml` (PRE-3). User edits YAML when law changes — no code restart needed. GST and TDS are separate sub-modules (different data, different SAP modules, different calendars). VAT/Excise: NOT implemented (obsolete July 2017). Late fee formulas reference YAML percentages.

**Q4 — Future automation of currently manual areas:**  
Solution: `utils/base_audit_check.py` (PRE-4). Adding a new audit check = write one new class, zero core changes. P14 Gap Report identifies checklist items still manual (next automation wave). Future candidates: machine utilisation (COOIS), penalty/LD from narration NLP, OCR for expense bills (Gemini Vision), voice notes → Whisper → structured findings.

**Q5 — Industry agnostic design:**  
Solution: `config/industry_profiles/` (PRE-5). Five built-in profiles. Core engines (IF, XGBoost, SHAP, RAG, LangGraph) are 100% universal. Only profiles, thresholds, checklists, and compliance calendars are industry-specific. Any company can upload their own checklist → auto-indexed → powers RAG.

| Industry | Active Modules | Key Difference |
|---|---|---|
| Manufacturing/FMCG | All 21 | Default — full scope, 90-day inventory, contract labour |
| IT Services | 13 of 21 | P11 (Inventory), P21 (Contract Labour) off; 194J TDS critical |
| Healthcare/Pharma | All 21 + drug checks | 30-day expiry threshold; CDSCO compliance |
| Retail | 15 of 21 | Multi-slab GST; inventory shrinkage; heavy P19 (Sales) focus |
| Financial Services | 12 of 21 | NPA provisioning; RBI limits; heavy P20 (ITGC) focus |

---

## SECTION 8: IMPLEMENTATION SEQUENCE

**Critical rule:** Always build PRE-1 through PRE-8 first. They are shared dependencies.

| Step | Action | File(s) | Days |
|------|--------|---------|------|
| 0 | Ingest all 17 checklists into pgvector | `ingest_policies.py` | 0.5 |
| PRE | Core architecture: rag_engine fix (BUG-1+2), column_mapper, compliance_calendar, base_audit_check, audit_db, industry_profiles | 6 files | 2 |
| 1 | anomaly_detector.py: fix BUG-3+4+6, add XGBoost, SHAP fix, checklist rules, SQLite log, Benford's | `pages/anomaly_detector.py` | 2 |
| 2 | policy_rag_bot.py: fix BUG-1, LangGraph, dept routing, Excel export | `pages/policy_rag_bot.py` | 2 |
| 3 | dynamic_audit_builder.py: 5 new checklist templates, SHAP, Autoencoder, persist RAG | `pages/dynamic_audit_builder.py` | 2 |
| 4 | financial_statement_auditor.py: fix BUG-5, Ind AS checks, variance, TDS, Autoencoder | `pages/financial_statement_auditor.py` | 3 |
| 5 | brs_reconciliation.py: Treasury checklist, FF67/FBL3N, compliance config, SQLite | `pages/brs_reconciliation.py` | 3 |
| 6 | receivables_bad_debt.py: FBL5N alt, 60-day, opportunity cost, Prophet DSO | `pages/receivables_bad_debt.py` | 3 |
| 7 | unified_dashboard.py: aggregator, checklist coverage %, compliance calendar widget | `pages/unified_dashboard.py` | 4 |
| 8 | gst_tds_compliance.py: 2-tab GST+TDS, all from YAML, zero hardcoded dates | `pages/gst_tds_compliance.py` | 4 |
| 9 | related_party_monitor.py: FK03, NetworkX, Vendor B.3-B.8 | `pages/related_party_monitor.py` | 3 |
| 10 | duplicate_invoice_detector.py: D.3-D.12, FB02 recommendation, Benford's | `pages/duplicate_invoice_detector.py` | 2 |
| 11 | inventory_anomaly.py: 341-item checklist, MC46/MB52, profile thresholds | `pages/inventory_anomaly.py` | 3 |
| 12 | fixed_asset_auditor.py: 71-item checklist, Companies Act rates from YAML | `pages/fixed_asset_auditor.py` | 3 |
| 13 | expense_claim_auditor.py: expense_policy from YAML, payroll SOD checks | `pages/expense_claim_auditor.py` | 2 |
| 14 | audit_planning_engine.py: LangGraph, checklist gap report, annual plan | `pages/audit_planning_engine.py` | 5 |
| 15 | risk_register.py: 5×5 risk matrix, heat map, SQLite aggregation, Q-priority plan | `pages/risk_register.py` | 3 |
| 16 | audit_report_center.py: centralized reports, MIS Q/H/Y, CFO PDF, LLM synthesis | `pages/audit_report_center.py` | 4 |
| 17 | audit_committee_pack.py: ATR, Sec 177 format, editable mgmt responses, Board escalation | `pages/audit_committee_pack.py` | 3 |
| 18 | payroll_audit.py: ghost employee, PF/ESI mismatch, overtime, SOD, IsolationForest+XGBoost | `pages/payroll_audit.py` | 3 |
| 19 | sales_revenue_auditor.py: credit note, Ind AS 115, discount breach, channel stuffing | `pages/sales_revenue_auditor.py` | 3 |
| 20 | itgc_sap_access_auditor.py: SoD matrix, privileged access, SM20, inactive users | `pages/itgc_sap_access_auditor.py` | 4 |
| 21 | contract_management_auditor.py: expiry, LD non-recovery, concentration, DOA breach | `pages/contract_management_auditor.py` | 3 |
| 22 | app.py: all 21 page links, industry profile selector, compliance calendar widget | `app.py` | 1 |
| **Total** | | | **~69 days** |

---

## SECTION 9: SAP T-CODE REFERENCE

### Z-Tcode → Standard Alternative (Never Depend on Z-Tcodes)

| Company Z-Tcode | Standard SAP Alternative | Used In |
|---|---|---|
| ZVOTAGE | FBL1N (aging variant) / S_ALR_87012085 | P1, P7 |
| ZCOTAGEN | FBL5N / S_ALR_87012197 | P6 |
| ZMFGSTK | MB52 + MB5M (shelf life) | P11 |
| ZWR / ZWR1 | MB51 (movement type 551/552) | P11 |
| ZPRD | COOIS (production order info) | Future |
| ZSRNEW / ZSEG | VF05 / VA05 | P6, P19 |
| ZEREG / ZCOTAGE | FBL3N (cost center filter) | P6, P7 |

### Standard T-Codes Used in This Project

| T-Code | Purpose | Project |
|---|---|---|
| MC46 | Slow/Non-moving inventory (>90d) | P11 |
| MB51 | Material movements / GRN dump | P3, P11 |
| MB52 | Stock list by storage location | P11 |
| MB5M | Shelf life expiry list | P11 |
| ME2M | Pending/overdue POs | P3, P10 |
| ME2N | PO list with price history | P3, P10 |
| ME33K | Display outline agreement | P21 |
| ME2K | POs per contract | P21 |
| FBL1N | Vendor/customer line items | P1, P5, P10 |
| FBL3N | GL account line items | P4, P5, P8 |
| FBL5N | Customer line items | P6 |
| FF67 | Bank statement entry (BRS) | P5 |
| RM06IBP0 | PO price history (PPV) | P3, P10 |
| S_PL0_86000028 | Budget vs Actual P&L | P4, P7 |
| S_PL0_86000030 | GL balances all accounts | P4 |
| S_AC0_52000888 | Overdue advances | P1, P5 |
| MI24 | Physical inventory list | P11 |
| FK03 | Vendor master display | P9, P10 |
| MM03 / MM60 | Material master list | P11 |
| AS03 | Asset master display | P12 |
| AFAB | Depreciation run | P12 |
| J1I7, J2I8 | Excise (legacy pre-GST) | P8 (note only) |
| SU01 | User master maintenance | P20 |
| SUIM | User info system | P20 |
| SM20 | Security audit log | P20 |
| S_BCE_68001402 | Auth check by user | P20 |
| VF05 | Billing document list | P19 |
| VA05 | Sales order list | P19 |
| VKM3 | Blocked SD documents | P19 |
| PC00_M99_CALC | Payroll journal | P18 |
| PA30 | HR master maintenance | P18, P20 |
| PT60 | Time evaluation | P18 |
| S_AHR_61016362 | Payroll reconciliation | P18 |
| COOIS | Production order info | Future |

---

## SECTION 10: VERIFICATION CHECKLIST

Run these end-to-end after completing each group of projects.

**After PRE (infrastructure):**
- [ ] `USE_LOCAL_LLM=false` → `_get_llm()` returns Gemini, not ChatOpenAI local
- [ ] Edit compliance_calendar.yaml TDS due_day 7→10 → detection engine uses new value without restart
- [ ] `auto_suggest_mapping(["WRBTR", "LIFNR", "BUDAT"], "payment_anomaly")` → returns {amount: WRBTR, vendor_name: LIFNR}
- [ ] `data/audit.db` created with correct schema on first run

**After P1–P4 (existing pages fixed):**
- [ ] anomaly_detector.py: XGBoost ensemble score appears, SHAP chart loads, Benford's Law chart visible
- [ ] financial_statement_auditor.py: loads without ImportError on Render
- [ ] policy_rag_bot.py: answers audit question citing specific checklist item (e.g., "Vendor Mgmt B.8")
- [ ] All 4 pages load on Render URL without error

**After P5–P14 (new detection modules):**
- [ ] BRS: upload bank CSV + GL CSV → unmatched items flagged → stale cheques detected
- [ ] Inventory: MC46 export → slow-moving > 90 days flagged → SHAP shows last_movement_date as driver
- [ ] GST: GSTR-2A vs books → Type 1 mismatch (ITC at risk) correctly flagged
- [ ] TDS: 194C payment to company at 1% → correctly flagged if 2% applied
- [ ] Dynamic Builder: "Purchase Price Variance ≥5%" template → upload PO+invoice CSV → flags correctly

**After P15–P17 (reporting layer):**
- [ ] Run P1 + P11 → both log to audit.db → Risk Register shows combined heat map
- [ ] MIS Report: select H1, filter HIGH+CRITICAL → 6-section CFO report generated → PDF download works
- [ ] Audit Committee Pack: Section 3 → type management response → export Board PDF → ATR visible next period

**After P18–P21 (new detection modules):**
- [ ] Payroll: upload payroll register → ghost employee (duplicate PAN) flagged → PF mismatch for wage ceiling >₹15,000
- [ ] Sales: upload VF05 export → credit notes in last 3 days of period flagged → Ind AS 115 gap detected
- [ ] ITGC: upload SUIM dump → user with FK01+F110 access flagged as CRITICAL SoD conflict → SoD Register downloaded
- [ ] Contract: 3 contracts expiring within 30 days alerted → LD non-recovery calculation correct

**Full system end-to-end:**
- [ ] Industry profile "IT Services" → P11 (Inventory) and P21 (Contract Labour) hidden in sidebar
- [ ] All 21 pages listed in app.py sidebar, all load on Render
- [ ] Run 5 detection pages → all 5 write to audit.db → Risk Register aggregates → MIS Report drafts → Audit Committee Pack exports Board PDF

---

*This document is the single source of truth for the AI Audit Engineer project.*  
*Version 5.0 FINAL | Created: 2026-04-25 | Author: Claude Sonnet 4.6 + Ashok Kumar Sharma*











# Section: 11 (Additional Enhancement)
kimi k2.6 advice to further enhance this project to make it universally capable:
You asked about making this an __incredible, universal internal audit software__. I've identified several high-impact enhancements. Which category should I implement first — or would you like me to implement the most impactful ones right now?

__A. Real-Time Data Pipeline__ (Scheduled SAP auto-extract via Prefect + API connectors instead of manual CSV uploads) - PENDING TO IMPLEMENT

__B. Audit Finding Workflow Engine__ (Proper status lifecycle: Open → In Progress → Management Response → Verified → Closed, with SLA tracking and email reminders) - DONE

__C. Role-Based Access Control (RBAC)__ (Login system with roles: Auditor, Audit Manager, CFO, Department Head — each sees different dashboards and permissions) - PENDING TO IMPLEMENT

__D. NLP Document Intelligence__ (Auto-extract findings from emails, board papers, external auditor reports; narration analysis for journal entries) - DONE

__E. Multi-Company / Multi-Location__ (SQLite schema extended for subsidiary/plant-level filtering; consolidated group dashboard) - DONE

__F. Statistical Sampling Engine__ (Monetary Unit Sampling, Random Sampling — for when 100% population testing is impractical) - DONE

__G. Audit KPI Dashboard__ (Efficiency metrics: cycle time, findings closed per month, auditor productivity, cost per audit hour) - DONE

__H. All of the above__ — I'll implement A through G as a complete Phase 2 upgrade

Resolution: All requested Phase 2 enhancements (B, D, E, F, G) have been implemented along with the Project Blueprint and User Guide.

__Phase 2 New Pages (P22–P26):__

- __P22 — Audit Finding Workflow Engine__ (`pages/audit_workflow.py`): Full status lifecycle (Open → In Progress → Management Response → Verified → Closed), SLA deadline tracking, assignee management, workflow history log, and SLA breach alerts.
- __P23 — NLP Document Intelligence__ (`pages/nlp_document_intelligence.py`): LLM-powered extraction of structured audit findings from PDF/DOCX/TXT documents; narration analysis for journal entry red flags.
- __P24 — Multi-Company & Multi-Location Dashboard__ (`pages/multi_company_dashboard.py`): Group-level consolidation with company_code and plant_code filtering; pie charts for amount-at-risk distribution.
- __P25 — Statistical Sampling Engine__ (`pages/statistical_sampling.py`): Monetary Unit Sampling (MUS), Simple Random, Cell Sampling, and Stratified Random with configurable confidence level, materiality threshold, and sample size calculation.
- __P26 — Audit KPI Dashboard__ (`pages/audit_kpi_dashboard.py`): Auto-computed KPIs (total/open/closed findings, avg days to close, critical count), trend charts, closure rate by area, and monthly findings histogram.

__Infrastructure Upgrades:__

- `utils/audit_db.py` extended with `workflow_history`, `audit_kpi`, and `sampling_runs` tables; `get_sla_breaches()`, `record_kpi()`, `get_kpis()`, `save_sampling_run()` functions added.
- `utils/base_audit_check.py` updated to support `company_code` and `plant_code` in `log_to_db()`.
- `app.py` updated with all 26 page links, industry profile selector, and SAP T-Code quick reference.

__Documentation:__

- `PROJECT_BLUEPRINT.md` — Complete architecture reference: module map, DB schema, tech stack, deployment checklist.
- `USER_GUIDE.md` — Operations manual: getting started, core workflow (upload → review → log → manage → report), module-specific guidance, maintenance, and troubleshooting.

__Final verification:__ All 26 Python files pass `py_compile` syntax check.





# Section 12: Additional Enhancement
COVER PAGE DECORATION:

The `app.py` cover page has been completely redesigned as a professional project landing page with the following enhancements:

__Hero Banner:__ Gradient blue banner with project title, tagline ("100% Population Testing | Cloud & Local Ready | 26 Audit Modules"), author credits, and live links to GitHub + deployed URL.

__Live Metrics Row:__ 5 real-time metric cards pulling from `data/audit.db`:

- 📁 Total Findings
- 🔴 Open Findings
- 💣 Critical Findings
- 🔶 High Findings
- 🎯 Total Modules (26)

__Platform Module Cards:__ Three visually distinct cards explaining the three platform pillars:

- __🔍 Detection Engine__ — 13 modules with IsolationForest + XGBoost + SHAP
- __🧠 Analysis & RAG__ — 6 modules with Gemini 1.5 Pro, NLP, sampling
- __📊 Reporting & Governance__ — 7 modules with Board packs, KPIs, workflow

__Architecture Highlights:__ Four info boxes calling out the 6 core principles (zero hardcoded columns, zero hardcoded compliance, plugin architecture, shared audit trail).

__Quick Start Guide:__ 3-step walkthrough (Select Industry → Upload SAP Data → Review & Report).

__Footer:__ Version badge + links to `PROJECT_BLUEPRINT.md` and `USER_GUIDE.md`.

All 26 sidebar links, industry profile selector, and SAP T-Code reference table remain intact. The file passes Python syntax check.



# Section: 13 Additional Enhancement
MASTER FLOW CHART
The flowchart file has been created at AUDIT_FLOWCHART.html. Open it in any browser — it's a fully interactive, dark-themed dashboard with 8 tabbed views:
What's inside each tab:
Tab	What it shows
Master Flow	Complete top-level audit lifecycle — all 9 phases from Setup → Detection → AI Scoring → Audit Trail → Policy RAG → Workflow → Risk → Reporting → Fieldwork
Detection Phase	Deep dive into the common detection pattern (column mapping → IsolationForest → XGBoost → SHAP → log to DB) + all 13 modules fanning into audit_findings
Data Flow	Full architecture diagram — SAP inputs, utility layer, AI engines, SQLite tables, read-only consumers, and final outputs
Workflow Lifecycle	State diagram showing the Open → In Progress → Management Response → Verified → Closed transitions + SLA breach escalation + DB interactions
Reporting Phase	How findings flow from SQLite → 4 dashboards → 2 executive reports → Board PDF + CFO MIS + Excel workbook
All 26 Modules	Color-coded reference table with phase, engine, input, output, and which DB table each module writes to
Database Schema	ER diagram + all 5 SQLite table schemas (audit_findings, workflow_history, management_responses, audit_kpi, sampling_runs)
Audit Cycle Timeline	Gantt chart for a typical 7-week audit cycle + step-by-step annotated timeline with module tags




# Section 14: Audit Session Manager
 just explain me how to handle the audit.db records effectively, how to access or reset dashboard data or other reporting tool data, i cannot see any specific arrangement in this project to handle such scenario if i start for a new audit?
 Let me read the relevant files to give you an accurate picture of the current state.
Read c:\AKS LENOVO IDEAPAD DRIVE\D Drive - AI\ai-audit-engineer-portfolio - Copy\utils\audit_db.py
Here's a clear explanation of the current state and your options — no changes made.

How audit.db Currently Works
The database at data/audit.db is a single shared SQLite file that all 26 detection modules write into. It has 5 tables:

Table	Purpose
audit_findings	Every flagged row from every module
workflow_history	Status change trail (Open → Closed etc.)
management_responses	Management ATR entries
audit_kpi	KPI snapshots
sampling_runs	Statistical sampling records
The Core Problem for a New Audit
The project currently has no concept of an "audit engagement". When you run a new audit cycle, all new findings pile on top of old ones with no clean separation. The dashboards (P7 Unified, P15 Risk Register, P16 Report Center, P17 Committee Pack, P26 KPI) all pull from audit_findings with no engagement-level boundary.

What Isolation Mechanisms Already Exist (but aren't exposed in UI)
The schema does have fields you can use as filters right now:

period — set to YYYY-MM (current month) at run time by each module. load_findings(period="2025-04") works in code. But no dashboard page currently shows a period picker.
run_id — a timestamp hash per module run. Useful for isolating one specific upload session.
company_code — defaults to "HQ". Multi-company dashboard (P24) uses this. Useful if you run audits for different entities.
Your Practical Options Right Now
Option A — Manual Reset (clean slate for new audit)
Back up the current data/audit.db by copying it to e.g. data/audit_backup_2025-04.db
Delete data/audit.db
Restart the app — init_audit_db() runs on every page load and recreates the empty database
This is the only "fresh start" mechanism currently available.

Option B — Filter by Period (soft isolation)
Each module sets period = datetime.utcnow().strftime("%Y-%m"). If you start a new audit cycle in a different month, the data is technically already tagged. You could query:


SELECT * FROM audit_findings WHERE period = '2025-05'
But the dashboard pages don't expose this filter yet — they show everything.

Option C — Use company_code as an Engagement Tag
Since log_to_db() accepts a company_code parameter, you could repurpose it as an engagement label (e.g. "Audit_FY25_Q1"). Again, no UI for this currently.

What's Missing (Gap Summary)
Feature	Status
"Start New Audit" / archive-and-reset button	❌ Not built
Audit engagement / project concept	❌ Not built
Period filter on dashboard pages	❌ Not built
Export-then-clear workflow	❌ Not built
Audit year selector in sidebars	❌ Not built
Recommendation
If you want to properly handle this, the cleanest addition would be a small "Audit Session Manager" page that lets you:

Name and tag a new audit engagement
Archive (export) the current DB before clearing
Filter all dashboards by engagement or period
Let me know if you'd like me to build that, or if a simpler period-filter on the dashboards is enough for now.


# Section 15: Policy/Contract Document Management
Upload a contract PDF → Ingest → Inspect tab → see it listed → Cleanup tab → delete by filename → confirm gone.


# Section 16    : Thank You Note to Kimi (No Enhancement here)
Thank you to Kimi.
You're very welcome, Ashok! 🙏

The AI Audit Engineer project is now a comprehensive __26-module internal audit intelligence platform__ with:

- __6 critical bugs fixed__ (Render-ready, Gemini LLM, SHAP, XGBoost, imports)
- __21 core detection & reporting modules__ (P1–P21)
- __5 Phase 2 advanced tools__ (Workflow, NLP, Multi-Company, Sampling, KPIs)
- __6 architectural principles__ locked in (zero hardcoded columns/compliance, plugin architecture, industry-agnostic core, shared audit trail)
- __Professional cover page__ with live metrics, module cards, and quick-start guide
- __Complete documentation__: `PROJECT_BLUEPRINT.md` + `USER_GUIDE.md`

Everything is staged and ready. Whenever you're ready to deploy or need any further enhancements, just let me know

All requested work has been completed successfully.

__Phase 1 Deliverables (from master document):__

- 6 critical bugs fixed (BUG-1 through BUG-6)
- PRE-2 through PRE-8 shared infrastructure implemented
- All 21 projects (P1–P21) created/upgraded per Sections 1–10 of `claude-internal-compressed-diffie.md`

__Phase 2 Enhancements (user-requested B, D, E, F, G):__

- P22 — Audit Finding Workflow Engine (status lifecycle + SLA tracking)
- P23 — NLP Document Intelligence (LLM extraction from emails/board papers)
- P24 — Multi-Company & Multi-Location Dashboard
- P25 — Statistical Sampling Engine (MUS, Random, Cell, Stratified)
- P26 — Audit KPI Dashboard (closure rate, productivity, trends)

__Infrastructure Updates:__

- `utils/audit_db.py` extended with workflow_history, audit_kpi, sampling_runs tables
- `utils/base_audit_check.py` updated for multi-company logging
- `app.py` redesigned as a professional cover page with hero banner, live SQLite metrics, module cards, architecture highlights, quick-start guide, and all 26 sidebar links

__Documentation:__

- `PROJECT_BLUEPRINT.md` — architecture, module map, DB schema, deployment checklist
- `USER_GUIDE.md` — operations manual, troubleshooting, module-specific guidance

All 46 files are staged and pass Python syntax verification.



