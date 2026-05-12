# AI Audit Engineer — User Guide & Operations Manual
## Version 5.1 | For Internal Auditors in Indian Manufacturing/FMCG

---

## 1. GETTING STARTED

### 1.1 Launch the Application
- **Local:** `streamlit run app.py`
- **Cloud:** Open https://aiauditengineer.onrender.com
- Use the **sidebar** on the left to navigate between all 28 modules.

### 1.2 Select Your Industry Profile
At the top of the sidebar, choose:
- **Manufacturing / FMCG** (default — all 28 modules active)
- **IT Services** (disables Inventory and Contract Labour modules)
- **Healthcare / Pharma** (30-day expiry threshold)
- **Retail** (multi-slab GST focus)
- **Financial Services** (NPA provisioning, RBI limits)

The profile controls which modules appear and which thresholds apply.

---

## 2. CORE WORKFLOW

### Step 1: Upload SAP Data
Every detection page (P1, P5–P14, P18–P21) starts with:
1. **Upload** your CSV/Excel export from SAP (any T-code — FBL1N, MB52, etc.)
2. **Map columns** using the dropdowns (the system auto-suggests based on SAP field synonyms)
3. **Run** the detection engine

> **Tip:** Save your column mapping as a profile using `utils/column_mapper.py` so next time it auto-fills.

### Step 2: Review Findings
- Flagged items appear in tables with **risk bands** (CRITICAL / HIGH / MEDIUM / LOW)
- Click any row to see **SHAP explanations** (why the AI flagged it)
- Expand **Benford's Law** or **Checklist-Grounded Rules** for additional evidence

### Step 3: Log to Audit Trail
All detection modules automatically write findings to `data/audit.db`. No manual action needed.

### Step 4: Manage Findings (P22 Workflow Engine)
Go to **P22: Audit Finding Workflow Engine** to:
- Transition status: Open → In Progress → Management Response → Verified → Closed
- Set **SLA deadlines** (default 15 days)
- Assign **owners**
- View **full workflow history** per finding
- See **SLA breach alerts** in red

### Step 5: Generate Reports
- **P15 Risk Register:** 5×5 heat map + quarterly priority plan
- **P16 Audit Report Center:** Combined executive summary + Excel workbook
- **P17 Audit Committee Pack:** Board-ready PDF with editable management responses
- **P26 KPI Dashboard:** Closure rate, findings per month, critical count trends

---

## 3. MODULE-SPECIFIC GUIDANCE

### P1: Payment Anomaly Detector
- **Required columns:** amount, vendor_name
- **Optional:** days_overdue, related_party, credit_terms_days
- **Outputs:** XGBoost risk score, SHAP drivers, Benford's chart, RAG audit report

### P8: GST/TDS Compliance
- Upload **GSTR-2A** and **Books data** separately
- The engine flags 4 mismatch types automatically
- TDS rates are read live from `config/compliance_calendar.yaml`

### P20: ITGC & SAP Access
- Upload your **SUIM user access dump**
- Built-in SoD conflicts: FK01+F110, ME21N+MIGO, PC00+PA30, etc.
- Checks for SAP_ALL/SAP_NEW privileged roles and generic IDs

### P25: Statistical Sampling
- Upload any population file
- Choose method: MUS (probability ∝ amount), Simple Random, Cell, or Stratified
- Set **materiality** and **confidence level**
- Download sample as CSV for fieldwork

### P23: NLP Document Intelligence
- Upload board papers, external auditor reports, or emails
- LLM extracts structured audit findings in markdown table format
- Use the **Narration Analysis** box for quick journal entry red-flag detection

---

## 4. MAINTENANCE & CONFIGURATION

### 4.1 Updating Compliance Rules
Edit `config/compliance_calendar.yaml`:
- Change GST due dates when government notifies
- Update TDS rates for new budgets
- Modify PF/ESI wage ceilings
- Adjust depreciation rates

**No code restart needed.** All pages read the YAML fresh on each run.

### 4.2 Adding a New Industry
1. Copy `config/industry_profiles/manufacturing_fmcg.yaml`
2. Rename and edit thresholds / modules_disabled
3. It appears in the sidebar selector automatically

### 4.3 Ingesting New Policies
Drop new PDFs into `data/raw/` or new checklists into `Internal Audit Checklist/`, then:
```bash
python ingest_policies.py
```

### 4.4 Backing Up the Audit Database
The SQLite file is at `data/audit.db`. Simply copy it for backup.

---

## 5. TROUBLESHOOTING

| Issue | Solution |
|---|---|
| "Policy database unavailable" on Render | Check `DATABASE_URL` env var; ensure Neon project is active |
| LLM not responding | Verify `GOOGLE_API_KEY`; or set `USE_LOCAL_LLM=true` for local dev |
| ImportError on a page | Ensure `sys.path.insert(0, str(Path(__file__).parent.parent))` is at top |
| SHAP chart fails | Check `shap>=0.45.0` is installed |
| Columns not auto-detected | Manually map in the dropdown; save profile for reuse |

---

## 6. SUPPORT

- **GitHub Issues:** https://github.com/aks2019/ai-audit-engineer-portfolio/issues
- **Email:** kr.ashoksharma@gmail.com
- **Author:** Ashok Kumar Sharma

---

*This guide covers operation of all 28 modules. For architecture decisions, see PROJECT_BLUEPRINT.md.*
