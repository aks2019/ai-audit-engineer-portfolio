I reviewed the project docs and implementation spine. I did not change any files.

Objective Understood
You are building SARVAGYA as a full internal audit automation platform: SAP/process audits, policy review, financial statement review, AS/Indian GAAP, Ind AS, CARO, Companies Act, CAS, SIA/internal audit standards, evidence handling, workflow, reporting, and audit committee output.

The vision is strong. The main gap now is that the project looks like “26 useful audit tools” rather than one governed audit platform with engagement lifecycle, standards library, evidence chain, risk/control universe, and report assurance.

Big Gaps

Engagement lifecycle is still weak
audit_session_manager.py exists, but the database model still treats findings as mostly global records. You need first-class tables for audit_engagements, audit_periods, audit_entities, audit_scope, audit_programs, evidence_files, and workpapers.

Standards review is not truly implemented yet
Financial statement review is currently LLM-drafted, not a structured AS/Ind AS/CARO/Companies Act checker. You need a standards knowledge base with versioned sources, applicability rules, disclosure checklists, assertions, and review procedures.

RAG needs governance
utils/rag_engine.py has an important issue: _get_llm() appears reversed. When USE_LOCAL_LLM=false, it returns the local llama.cpp client; when true, it returns Gemini. That should be fixed before deployment. Also get_vectorstore() uses NEON_CONNECTION_STRING, while docs mention DATABASE_URL.

Policy/document management is basic
policy_management.py can ingest and delete documents, but it does not yet maintain document version, effective date, owner, department, policy type, approval status, superseded status, or mapping to audit controls.

Evidence trail is not audit-grade yet
Findings need linked evidence, reviewer signoff, preparer/reviewer timestamps, immutable hash, source file hash, original row reference, and complete change history.

Controls and checklist mapping are shallow
The project should have a formal control library: process, risk, control objective, control activity, frequency, owner, SAP source, audit procedure, evidence required, assertion, standard reference, and automated test coverage.

SAP automation is not built yet
Current workflow is mostly manual CSV/Excel upload. To become a strong platform, add SAP extract templates first, then later SAP OData/RFC/API connectors. Do not jump directly to live SAP integration before the data model is stable.

Tests do not match the current app
The tests/ folder still looks tied to the older packaged anomaly detector. It does not verify Streamlit pages, audit DB schema, RAG fallback, standards rules, or report generation.

Standards Sources To Build Around
Use official/current sources as the backbone, not random PDFs. I checked these official references:

MCA Companies Act, 2013 PDF: https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf
ICAI Ind AS Compendium 2025-2026: https://www.icai.org/post/compendium-of-indian-accounting-standards
ICAI Internal Audit Standards publications: https://internalaudit.icai.org/publications/
ICAI Compendium of Standards on Internal Audit: https://internalaudit.icai.org/compendium-of-standard/
ICAI CARO 2020 guidance: https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf
ICMAI Cost Accounting Standards Board/CAS reference: https://www.icmai.in/CASB/casb-about.php
What To Build Next
My recommended implementation order:

Foundation Phase: Audit Operating System
Create a proper engagement model:
audit_engagements, entities, locations, periods, processes, risks, controls, audit_programs, workpapers, evidence, findings, review_notes.
This is the platform heart. Everything else should attach to an engagement.

Standards Knowledge Base
Create a structured standards registry:
standard_family: Companies Act, Ind AS, AS, CARO, CAS, SIA, SA, GST, TDS, PF, ESI
standard_ref: section/clause/paragraph
applicability: company type, turnover, listing status, industry, accounting framework
audit_procedure: what to check
evidence_required: what file/data proves compliance
reporting_impact: audit report, CARO clause, financial statement disclosure, internal audit report

Financial Statement Review Engine
Replace pure LLM drafting with deterministic checks:

Trial balance mapping to Schedule III
Ind AS/AS applicability selector
Related party disclosure checks
PPE/CWIP ageing and capitalization checks
Revenue recognition red flags under Ind AS 115
Inventory NRV/slow-moving checks
Borrowings, MSME, statutory dues, contingent liabilities
CARO clause-wise checklist and evidence status
Policy Review Engine
For every policy upload:

classify policy type
extract clauses
map clauses to process/control/risk
detect missing clauses
compare policy vs actual SAP behavior
generate “policy compliance exceptions”
SAP Review Engine
Create standard SAP data packs:

Vendor: FBL1N, FK03, payment runs, PO history
Customer: FBL5N, VF05, credit notes
GL/TB: FBL3N, trial balance, journal entries
Inventory: MB51, MB52, MB5M
Assets: asset register, depreciation run
Access: SUIM, SU01, roles, tcodes, SM20
Each pack should have expected columns, mapper, validation, tests, and audit procedures.

Reporting Layer
Build outputs by audience:
Working paper report
Management exception report
Audit committee pack
CARO readiness report
Financial statement review memo
Policy gap report
Open finding tracker
Entity/location risk dashboard
Governance
Add RBAC, maker-checker review, immutable logs, versioned policies, source file hashing, and AI response audit logs. For serious audit use, this matters as much as the ML.
Better Architecture
Keep Streamlit for UI, but move business logic out of pages. Pages should only handle upload, filters, display, and buttons. Core logic should live in:

core/engagements.py
core/standards_registry.py
core/evidence.py
core/audit_program.py
checks/financial_statement/
checks/sap/
checks/compliance/
reports/
rag/
That will make SARVAGYA feel like a real audit product, not many independent scripts.

My Strong Recommendation
Start with the Audit Engagement + Standards Registry backbone before adding more modules. Once every finding, policy, SAP extract, checklist item, and report is tied to an engagement and a standards reference, the whole platform becomes much more powerful.

The next best concrete build step is: implement audit_engagements, standards_registry, evidence_files, and update dashboards to filter by active engagement. That gives us the base to complete AS/Ind AS/CARO/CAS/Companies Act automation properly.


REPLAN:
My first objective for developing this project was involving AI Online(Claude or GPT) / Local (Qwen or Gemma) models and RAG engine for policy query such as Langchain/Llamaindex (Whichever is best & easy to handle) wherever it is needed in this project to get more advantage of AI driven technology so please revise and confirm your final plan to proceed with the project development aligned with this objective as well.

GPT5.5 ANSWERS:
# SARVAGYA Internal Audit Automation Platform Plan

## Summary
Build SARVAGYA as an AI-first internal audit platform where Online LLMs (GPT/Claude/Gemini) and Local LLMs (Qwen/Gemma via llama.cpp/Ollama) support policy review, SAP review, financial statement review, compliance checks, audit planning, reporting, and workflow. Use the existing LangChain + pgvector foundation for v1 because the repo already uses it; keep the design modular enough to add LlamaIndex later if needed.

## Key Implementation Changes

### 1. AI + RAG Foundation
- Create one central AI service layer for all pages: model selection, fallback, prompt templates, citation handling, token limits, response logging, and error handling.
- Fix current LLM routing so:
  - `USE_LOCAL_LLM=true` uses local Qwen/Gemma.
  - `USE_LOCAL_LLM=false` uses online model provider.
- Standardize env vars:
  - `AI_PROVIDER=openai|anthropic|gemini|local`
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
  - `LOCAL_LLM_BASE_URL`
  - `DATABASE_URL`
- Keep LangChain as the primary RAG framework for now; use pgvector as the policy/standards vector store.
- Add RAG modes:
  - Policy Q&A
  - Clause extraction
  - Compliance checklist mapping
  - Finding explanation
  - Report drafting
  - Standards review support
  - Contract/policy gap review

### 2. Standards + Policy Knowledge Base
- Build a structured standards registry for:
  - Companies Act
  - CARO
  - AS / Indian GAAP
  - Ind AS
  - CAS
  - Standards on Internal Audit
  - Standards on Auditing
  - GST/TDS/PF/ESI
  - Internal company policies and SOPs
- Store each reference with source, clause, paragraph, applicability, effective date, document type, and audit procedure.
- Policy Management should support upload, ingest, inspect, version, retire, delete, and re-index documents.
- RAG answers must always show citations and should clearly say when no reliable source is found.

### 3. Audit Engagement Backbone
- Add first-class audit engagement/session handling:
  - engagement name
  - entity/company
  - plant/location
  - audit period
  - audit scope
  - active/inactive status
- Every finding, policy query, evidence file, SAP upload, workflow action, and report must link to an engagement.
- Dashboards and reports must filter by active engagement by default.

### 4. Audit Modules Upgrade
- Refactor pages gradually so business logic moves out of Streamlit pages into reusable audit services/checks.
- Upgrade major modules to use AI/RAG where useful:
  - SAP anomaly modules: RAG-backed policy/context explanation for flagged exceptions.
  - Financial statement auditor: deterministic checks first, AI/RAG explanation second.
  - GST/TDS/CARO/Companies Act review: rule engine first, RAG citation second.
  - Policy review: extract clauses, compare against expected controls, identify gaps.
  - Audit planning: use historical findings + standards registry + RAG to draft annual audit plans.
  - Reporting: AI drafts management-ready summaries with citation-backed evidence.
- Keep AI as assistant/reviewer, not the only decision engine, wherever statutory or financial accuracy matters.

### 5. Evidence, Workflow, and Reporting
- Add evidence management:
  - uploaded file hash
  - source system
  - source row/document reference
  - linked finding/control/procedure
  - preparer/reviewer status
- Strengthen workflow:
  - Open -> In Progress -> Management Response -> Verified -> Closed
  - reviewer comments
  - owner and due date
  - SLA breach
  - audit trail of all status changes
- Generate reports:
  - working paper report
  - policy gap report
  - CARO readiness report
  - financial statement review memo
  - audit committee pack
  - management action tracker
  - engagement closure summary

## Development Order
1. Stabilize AI/RAG engine and model provider abstraction.
2. Implement audit engagement/session model and active engagement filter.
3. Upgrade policy/standards management into a proper knowledge base.
4. Add standards registry and map it to audit procedures.
5. Upgrade financial statement review with AS/Ind AS/CARO/Companies Act checks.
6. Upgrade SAP/process modules to log evidence-linked, engagement-linked findings.
7. Improve dashboards and reports to become engagement-aware and standards-aware.
8. Add tests and deployment hardening.

## Test Plan
- Verify online model path works with selected provider.
- Verify local model path works with Qwen/Gemma endpoint.
- Verify RAG returns cited answers from uploaded policy/standards documents.
- Verify missing vector DB or LLM failure gives graceful offline response.
- Verify new engagement creation, switching, filtering, archive, and reset.
- Verify each finding links to engagement, source file, module, checklist, and standard reference.
- Verify financial statement checks produce deterministic exceptions before AI summary.
- Verify reports include only selected engagement data.
- Run syntax checks for all pages and unit tests for DB, RAG routing, standards registry, and audit findings.

## Assumptions
- Use LangChain + pgvector for v1 because the repo already uses them.
- Keep LlamaIndex as a future option, not an immediate migration.
- AI providers should be configurable, but Gemini/local models can remain the immediate default if keys are available.
- Statutory and financial checks should rely on structured rules plus cited RAG, not free-form AI alone.
- No existing app pages should be deleted; they should be stabilized and progressively refactored.



REPLAN:
Also remeber that the pages reports output as audit findings are getting logged in audit.db so that detailed audit reports, MIS Reports, Audit Committee Reports could be prepared automatically with AI models supports, i am objectively designing this audit project in this way keeping in view of real world audit automation with AI, currently audit findings in the pages reports are getting logged automatically in audit.db rather it should get logged after user confirmation only, review carefully and implement with your best knowledge and as per best practices.

GPT5.5 ANSWERS:
# Confirmed-Finding Audit Trail Plan

## Summary
Change SARVAGYA so page-generated exceptions are treated as **draft/proposed findings**, not official audit findings. Nothing should enter `audit_findings` until the auditor reviews, optionally edits, selects, and confirms it. AI can still help draft explanations, risk summaries, policy references, and report language, but the official audit trail must require human confirmation.

## Key Implementation Changes

### 1. Database Workflow
- Keep `audit_findings` as the official confirmed findings table used by MIS, detailed audit reports, audit committee reports, KPI dashboard, and workflow.
- Add a draft layer in `audit.db`, either as a new table `draft_audit_findings` or as a controlled staging helper. Recommended: create `draft_audit_findings` for persistence.
- Draft records should include:
  - module/page name
  - run_id
  - period
  - company_code / plant_code
  - proposed finding text
  - amount_at_risk
  - vendor/customer/employee/reference name
  - risk_band
  - checklist_ref
  - AI explanation / policy citation summary
  - source row reference
  - source file name/hash if available
  - draft_status: `Draft`, `Confirmed`, `Discarded`
  - generated_at, generated_by
  - confirmed_at, confirmed_by
- Add a deterministic `finding_hash` to prevent duplicate confirmation of the same exception.

### 2. New Audit DB Helper Functions
Create/extend helper functions in the audit DB layer:
- `stage_findings(df, module, run_id, period, metadata)`  
  Saves proposed findings to `draft_audit_findings`, not `audit_findings`.
- `load_draft_findings(run_id=None, module=None, status="Draft")`  
  Loads pending exceptions for auditor review.
- `confirm_draft_findings(draft_ids, confirmed_by, edited_values=None)`  
  Moves selected draft findings into `audit_findings`.
- `discard_draft_findings(draft_ids, discarded_by, reason)`  
  Marks draft exceptions as discarded.
- `is_duplicate_finding(finding_hash)`  
  Prevents repeated commits.

### 3. Page Behavior
- Replace automatic `log_to_db()` behavior in detection pages with a review-and-confirm flow.
- Each page should follow this pattern:
  1. User uploads SAP/policy/financial data.
  2. Page runs detection and shows proposed exceptions.
  3. Page stages proposed findings as draft or keeps them in session until the user clicks “Prepare Draft Findings”.
  4. User reviews findings in an editable table.
  5. User selects rows to confirm.
  6. Only confirmed rows are inserted into `audit_findings`.
- Add clear buttons:
  - `Prepare Draft Findings`
  - `Confirm Selected Findings`
  - `Discard Selected Drafts`
  - `Export Draft Exceptions`
- Use `st.data_editor` where practical so the auditor can adjust:
  - finding text
  - risk band
  - amount at risk
  - checklist reference
  - assigned owner
  - management action due date

### 4. Reporting Behavior
- MIS reports, detailed audit reports, audit committee packs, KPI dashboard, risk register, and workflow pages must read only from confirmed `audit_findings` by default.
- Add optional “include draft findings” toggles only where useful for review dashboards, not formal reports.
- Formal report headers should state:
  - engagement / period
  - confirmed findings count
  - draft findings excluded unless explicitly selected
  - AI-assisted narrative status, if used

### 5. AI Usage Best Practice
- AI should assist before confirmation by:
  - drafting audit finding language
  - identifying likely policy/standard references
  - explaining risk and root cause
  - suggesting management action wording
  - preparing report summaries
- AI should not silently commit official findings.
- Every AI-assisted finding should preserve:
  - prompt/context hash
  - response hash
  - citations used
  - model/provider used
  - timestamp
- Confirmed findings should clearly distinguish:
  - system-detected exception
  - AI-drafted explanation
  - auditor-confirmed finding

### 6. Migration Approach
- Preserve existing `audit_findings`; do not delete or rewrite historical records automatically.
- Add schema creation logic so existing users can open the app without manual migration.
- For current auto-logging pages, update one shared helper first, then gradually replace page-level direct inserts.
- Highest priority pages to update first:
  - Payment Anomaly Detector
  - GST/TDS Compliance
  - BRS Reconciliation
  - Duplicate Invoice Detector
  - Financial Statement Auditor
  - Policy RAG/Policy Management outputs
- After the pattern is stable, apply it to remaining detection pages.

## Test Plan
- Run a detection page and verify no row is inserted into `audit_findings` before confirmation.
- Verify draft findings appear in `draft_audit_findings`.
- Confirm selected rows and verify only selected rows move to `audit_findings`.
- Discard selected rows and verify they never appear in reports.
- Re-run the same upload and verify duplicate confirmed findings are blocked or warned.
- Verify MIS, risk register, audit committee pack, and KPI dashboard show only confirmed findings.
- Verify AI-generated explanations remain available before confirmation and are retained after confirmation.
- Verify syntax checks pass for all changed pages and DB utilities.

## Assumptions
- `audit_findings` remains the official reportable audit trail.
- Draft/proposed findings can live in the same `audit.db` but must be clearly separated from confirmed findings.
- Auditor confirmation is mandatory for official reporting.
- AI can recommend and draft, but the user/auditor owns final audit judgment.
- Existing historical records in `audit_findings` will be preserved unless a separate cleanup/archive task is requested.
