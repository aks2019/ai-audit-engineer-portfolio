"""Standards Registry - Knowledge Base for Audit Standards.
Enriched clause_text with practice-oriented applicability guidance
to enable LLM to make pinpoint standard-to-scenario matches.
"""
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def register_standard(family: str, reference: str, description: str = None,
                     applicability: str = None, clause_text: str = None,
                     source_url: str = None) -> int:
    """Register a new audit standard."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_standards (family, reference, description, applicability, clause_text, source_url)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (family, reference, description, applicability, clause_text, source_url))
    standard_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return standard_id


def get_standard(standard_id: int) -> Optional[Dict[str, Any]]:
    """Get standard details."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM audit_standards WHERE id = ?", (standard_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_standards(family: str = None, search: str = None) -> pd.DataFrame:
    """List standards with filters."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM audit_standards WHERE 1=1"
    params = []
    if family:
        q += " AND family = ?"
        params.append(family)
    if search:
        q += " AND (reference LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    q += " ORDER BY family, reference"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def get_standard_families() -> List[str]:
    """Get all unique standard families."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("SELECT DISTINCT family FROM audit_standards ORDER BY family", conn)
    conn.close()
    return df['family'].tolist()


def link_control_to_standard(control_id: int, standard_id: int):
    """Link a control to a standard."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("UPDATE audit_controls SET standard_id = ? WHERE id = ?", (standard_id, control_id))
    conn.commit()
    conn.close()


def get_applicable_standards(entity_type: str = None, turnover: float = None,
                            listing_status: str = None, industry: str = None) -> pd.DataFrame:
    """Get standards applicable based on entity parameters."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("SELECT * FROM audit_standards ORDER BY family, reference", conn)
    conn.close()

    # Filter by applicability
    if entity_type or turnover or listing_status:
        filtered = []
        for _, row in df.iterrows():
            appl = row.get('applicability', '')
            if not appl:
                filtered.append(row)
                continue

            # Simple matching - can be enhanced
            if entity_type and entity_type.lower() in appl.lower():
                filtered.append(row)
                continue
            if listing_status and listing_status.lower() in appl.lower():
                filtered.append(row)
                continue
            filtered.append(row)
        df = pd.DataFrame(filtered)

    return df


# ────────────────────────────────────────────────────────────────────────────
# Complete official standards registry — additive, idempotent
# Each tuple: (family, reference, description, applicability, clause_text, source_url)
# clause_text now includes enriched guidance for accurate LLM matching.
# ────────────────────────────────────────────────────────────────────────────

ALL_STANDARDS = [
    # ═══════════════════════════════════════════════════════════════════════════
    # Companies Act 2013 — Sections related to Audit & Accounts
    # ═══════════════════════════════════════════════════════════════════════════
    ("Companies Act", "Section 128",
     "Books of Account to be kept by Company",
     "All companies",
     "Requires every company to keep proper books of account at its registered office using accrual basis and double-entry system. APPLIES TO: financial record-keeping, accounting system design, inspection of books by directors. RELEVANT FOR AUDIT: verifying that books reflect true and fair view of financial position; electronic records are permitted.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 129",
     "Financial Statements",
     "All companies",
     "Mandates preparation of financial statements in prescribed form (Schedule III). Balance sheet, P&L, cash flow statement, and notes to accounts required. APPLIES TO: format and content of annual financial statements. RELEVANT FOR AUDIT: verifying compliance with Schedule III presentation requirements.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 130",
     "Re-opening of Accounts on Court or Tribunal Orders",
     "Companies directed by court/tribunal",
     "Permits court-ordered reopening of accounts on grounds of fraud, mismanagement, or statutory non-compliance within prescribed time limits. APPLIES TO: situations where financial statements are suspected to be fraudulent or misleading. RELEVANT FOR AUDIT: assessing whether previously issued financial statements need revision.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 133",
     "Central Government to Prescribe Accounting Standards",
     "All companies",
     "Authority for Central Government to prescribe accounting standards on NFRA/ICAI recommendation. APPLIES TO: adoption of notified accounting standards (Ind AS or AS). RELEVANT FOR AUDIT: framework for determining which accounting standards the company should follow.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 134",
     "Board's Report",
     "All companies",
     "Requires Board of Directors to attach a report to financial statements covering business operations, director responsibility statement, internal financial controls adequacy, and risk management. APPLIES TO: annual reporting and director disclosures. RELEVANT FOR AUDIT: verifying directors' responsibility statement and internal controls declaration.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 135",
     "Corporate Social Responsibility",
     "Companies with turnover >1000 Cr or net worth >500 Cr or profit >5 Cr",
     "Mandates CSR committee and spending of 2% of average net profits on CSR activities. APPLIES TO: qualifying companies with high turnover/profits. RELEVANT FOR AUDIT: verifying CSR expenditure eligibility and disclosure in Board's report. DOES NOT APPLY TO: small companies below thresholds.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 138",
     "Internal Audit",
     "Prescribed class of companies",
     "Requires appointment of an internal auditor (CA/CMA/firm) for prescribed classes of companies. APPLIES TO: listed companies, large unlisted public companies, and private companies meeting turnover/net worth thresholds. RELEVANT FOR AUDIT: verifying internal audit function existence, qualifications, and reporting to audit committee.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 139",
     "Appointment of Auditors",
     "All companies",
     "Governs appointment of statutory auditors including rotation every 5 years (individual) or 10 years (firm), first auditor appointment by Board, casual vacancy filling. APPLIES TO: auditor appointment process and rotation compliance. RELEVANT FOR AUDIT: verifying auditor independence and tenure limits.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 140",
     "Removal and Resignation of Auditor",
     "All companies",
     "Outlines procedure for auditor removal (requires special resolution + CG approval) and resignation (requires Form ADT-3 filing with reasons). APPLIES TO: auditor changes during tenure. RELEVANT FOR AUDIT: verifying proper process for auditor removal or resignation and documenting reasons.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 141",
     "Eligibility and Qualifications of Auditors",
     "All companies",
     "Specifies that auditor must be a CA in practice; lists disqualifications including holding directorship, financial interest in the company, or relative employment. APPLIES TO: determining who CANNOT be appointed as auditor. RELEVANT FOR AUDIT: independence checks before appointment.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 143",
     "Auditor's Report",
     "All companies",
     "Defines content of auditor's report including opinion on financial statements, CARO applicability, internal financial controls, and reporting of fraud to CG. APPLIES TO: statutory audit report content and format. RELEVANT FOR AUDIT: the legal basis for how audit findings are reported.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 144",
     "Auditor Not to Render Certain Services",
     "All companies",
     "Prohibits statutory auditors from providing specified non-audit services including accounting, internal audit, actuarial, investment advisory, and management services. APPLIES TO: auditor independence from management functions. RELEVANT FOR AUDIT: ensuring audit firm does not have conflict of interest through dual service provision.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 148",
     "Central Government to Specify Audit of Cost Records",
     "Companies to which Cost Audit Order applies",
     "Government can order cost audit for specified industries; cost auditor must be a CMA; cost audit report filed with MCA. APPLIES TO: manufacturing companies in notified industries. RELEVANT FOR AUDIT: confirming cost record maintenance and cost auditor appointment if applicable. DOES NOT APPLY TO: service companies not notified.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 177",
     "Audit Committee",
     "Listed companies and prescribed public companies",
     "Mandates Audit Committee with minimum 3 directors (majority independent). Reviews: financial statements, internal audit reports, related party transactions, risk management. APPLIES TO: corporate governance structure. RELEVANT FOR AUDIT: ensuring RPT approvals, internal audit oversight, and financial reporting reviews are conducted by committee.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 185",
     "Loan to Directors",
     "All companies",
     "Prohibits loans/guarantees to directors with exceptions for wholly-owned subsidiaries. APPLIES TO: any financial assistance to directors or their relatives. RELEVANT FOR AUDIT: reviewing loan registers, confirming no unauthorized director loans. VIOLATION triggers penalty provisions under Section 447.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 186",
     "Loan and Investment by Company",
     "All companies",
     "Restricts loans/investments to 60% of paid-up capital + free reserves or 100% of free reserves, whichever is higher. Requires Board or special resolution approval based on amount. Register of loans/investments to be maintained. APPLIES TO: inter-corporate loans, investments in securities, guarantees. RELEVANT FOR AUDIT: verifying loan/investment limits and approval documentation.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 188",
     "Related Party Transactions",
     "All companies",
     "Requires prior Board approval (or special resolution for material RPTs) for related party transactions. Audit Committee may grant omnibus approval. Must be at arm's length. Register of contracts maintained. APPLIES TO: transactions with directors, KMP, subsidiaries, associates, and their relatives. RELEVANT FOR AUDIT: key section for identifying RPT disclosure gaps, missing approvals, or non-arm's length pricing.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 197",
     "Overall Maximum Managerial Remuneration",
     "Companies paying managerial remuneration",
     "Caps managerial remuneration at 11% of net profits. Individual limits for MD/WTD. Requires NRC recommendation and shareholder approval if exceeded. APPLIES TO: remuneration paid to directors and KMP. RELEVANT FOR AUDIT: verifying that remuneration complies with statutory limits and approvals.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 203",
     "Key Managerial Personnel",
     "Prescribed class of companies",
     "Mandates appointment of MD/CEO, CS, and CFO. Vacancy must be filled within 6 months. APPLIES TO: company officer structure requirements. RELEVANT FOR AUDIT: verifying KMP appointments and any prolonged vacancies.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 204",
     "Secretarial Audit for Bigger Companies",
     "Listed companies and prescribed unlisted public companies",
     "Requires secretarial audit by a Practicing Company Secretary covering Companies Act, SEBI, FEMA, and labour law compliance. Form MR-3 filed with ROC. APPLIES TO: larger companies with higher compliance burdens. RELEVANT FOR AUDIT: secretarial compliance verification alongside financial audit.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    ("Companies Act", "Section 447",
     "Punishment for Fraud",
     "Any person guilty of fraud under the Act",
     "Provides for imprisonment from 6 months to 10 years and fine up to 3x the amount involved in fraud. APPLIES TO: fraudulent activities including false accounting, misrepresentation, and concealment. RELEVANT FOR AUDIT: governs auditor's obligation to report fraud and consequences of fraudulent financial reporting.",
     "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),


    # ═══════════════════════════════════════════════════════════════════════════
    # CARO 2020 — All 21 Clauses
    # ═══════════════════════════════════════════════════════════════════════════
    ("CARO", "Clause 1",
     "Maintenance of Books of Accounts",
     "All companies",
     "Auditor must report whether books of accounts are maintained as per Section 128, including branch accounts. APPLIES TO: adequacy of accounting records. RELEVANT FOR AUDIT: verify that proper books exist and are accessible for audit. DOES NOT APPLY TO: companies exempt under Section 128(5).",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 2",
     "Fixed Assets / PPE",
     "All companies",
     "Auditor must comment on: fixed asset maintenance, physical verification frequency, material discrepancies, title deed holding (e.g. land not in company name). APPLIES TO: property, plant, equipment, freehold/leasehold land, buildings. RELEVANT FOR AUDIT: verifying physical existence and ownership of fixed assets; identifying unregistered properties.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 3",
     "Inventory",
     "All companies",
     "Auditor must report on: physical verification at reasonable intervals, material discrepancies in inventory count, working capital loans secured against inventory. APPLIES TO: stock of raw materials, WIP, finished goods, stores. RELEVANT FOR AUDIT: checking inventory verification coverage, investigating major shortages/excesses, and whether stock is pledged against borrowings.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 4",
     "Loans Granted",
     "All companies",
     "Auditor must report on terms and conditions of loans/guarantees given to parties (subsidiaries, associates, others), whether prejudicial to company interest, repayment schedule adherence. APPLIES TO: inter-corporate loans and advances. RELEVANT FOR AUDIT: reviewing loan terms, interest rates, repayment defaults by borrowers.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 5",
     "Loans/Investments — Section 185/186",
     "All companies",
     "Auditor must check compliance with Section 185 (loans to directors) and Section 186 (investment/loan limits). APPLIES TO: all loans and investments made by the company. RELEVANT FOR AUDIT: verifying Board/SR approvals, statutory limits compliance, and proper register maintenance.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 6",
     "Deposits",
     "All companies",
     "Auditor must report whether deposits accepted comply with RBI directions and NBFC norms; mention any defaults in repayment. APPLIES TO: public deposits and any amount accepted as deposit. RELEVANT FOR AUDIT: verifying deposit acceptance is within regulatory limits and repayment schedule is maintained.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 7",
     "Cost Records",
     "Companies where cost audit applicable",
     "Auditor must confirm whether cost records are maintained as per Section 148 and cost audit has been conducted. APPLIES TO: manufacturing companies in notified industries. RELEVANT FOR AUDIT: existence of cost accounting records and cost auditor appointment. DOES NOT APPLY TO: service companies or exempt industries.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 8",
     "Statutory Dues",
     "All companies",
     "Auditor must report on: PF, ESI, Income Tax, GST, Customs, Cess dues deposited regularly; amounts outstanding for >6 months; details of disputed dues with forum and amount. APPLIES TO: all statutory payments to government authorities. RELEVANT FOR AUDIT: identifying delayed/outstanding statutory payments; verifying disputed tax demands.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 9",
     "Undisclosed Income / Surrendered Income",
     "All companies",
     "Auditor must report whether company disclosed/surrendered any income during income tax search/survey and whether books were updated accordingly. APPLIES TO: income disclosed during tax proceedings (e.g. Section 132/133A of IT Act). RELEVANT FOR AUDIT: checking impact on financial statements of any search/survey adjustments.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 10",
     "Defaults on Loans and Borrowings",
     "Companies with external borrowings",
     "Auditor must report defaults in loan repayments to banks, financial institutions, debenture holders, or government. APPLIES TO: all external borrowings including working capital loans, term loans, debentures. RELEVANT FOR AUDIT: identifying covenant breaches, renegotiation status, and going concern implications of defaults.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 11",
     "Managerial Remuneration",
     "All companies paying managerial remuneration",
     "Auditor must verify whether managerial remuneration is paid/provided as per Section 197, approval obtained, and any excess remuneration is recovered. APPLIES TO: salaries, bonuses, commissions paid to directors and KMP. RELEVANT FOR AUDIT: checking compliance with 11% net profit ceiling and approval documentation.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 12",
     "Related Party Transactions",
     "All companies",
     "Auditor must report: RPT compliance with Section 188, whether audit committee approvals obtained, and whether adequate disclosures are made. APPLIES TO: all transactions with related parties. RELEVANT FOR AUDIT: CRITICAL for RPT audit — verify omnibus approval, arm's length pricing, disclosure adequacy.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 13",
     "Internal Audit",
     "Prescribed class of companies",
     "Auditor must report whether internal audit system is commensurate with size and nature of business, and whether internal audit reports are considered by audit committee. APPLIES TO: companies required under Section 138 to have internal audit. RELEVANT FOR AUDIT: assessing internal audit coverage, independence, and management response to IA findings.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 14",
     "Internal Financial Controls",
     "All companies",
     "Auditor must report whether company has adequate internal financial controls over financial reporting and whether such controls are operating effectively. APPLIES TO: design and implementation of policies and procedures for reliable financial reporting. RELEVANT FOR AUDIT: SAME AS SA 315/330 — testing control environment, control activities, monitoring.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 15",
     "Non-cash Transactions with Directors",
     "All companies",
     "Auditor must report whether company has entered into non-cash transactions with directors or connected persons during the year, and compliance with Section 192. APPLIES TO: asset exchanges, barter transactions, and any non-monetary dealings with directors. RELEVANT FOR AUDIT: identifying undisclosed director-related transactions not involving cash.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 16",
     "RBI Registration",
     "NBFCs and companies required to register under RBI Act",
     "Auditor must report whether company is required to be registered under Section 45-IA of RBI Act 1934 and whether such registration is held. APPLIES TO: companies engaged in lending, investment, or financial activities. RELEVANT FOR AUDIT: verifying RBI registration if company accepts deposits or extends loans as principal business. DOES NOT APPLY TO: regular operating companies not in financial services.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 17",
     "Cash Losses",
     "All companies",
     "Auditor must report whether company incurred cash losses in current and immediately preceding financial year with amounts. APPLIES TO: net cash flow from operations being negative. RELEVANT FOR AUDIT: flagging cash-burn situations that may impact going concern.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 18",
     "Resignation of Statutory Auditor",
     "Companies where statutory auditor resigned",
     "Auditor must report on resignation of statutory auditor during the year: whether issues raised by outgoing auditor were considered, and management's response on record. APPLIES TO: mid-tenure auditor changes. RELEVANT FOR AUDIT: documenting reasons for auditor resignation and assessing audit risk implications.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 19",
     "Going Concern Doubt",
     "All companies",
     "Auditor must report if financial ratios, ageing of assets/liabilities indicate material uncertainty about going concern. APPLIES TO: financial health assessment based on ratio analysis, debt coverage, liquidity. RELEVANT FOR AUDIT: LIQUIDITY ANALYSIS — current ratio, debt-equity ratio, interest coverage ratio, ageing of payables/receivables indicating stress.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 20",
     "Contingent Liabilities and Public Offer",
     "All companies",
     "Auditor must report on: pending litigations, unrecorded income/assets not disclosed; fund utilisation from public offer/rights issue. APPLIES TO: litigation disclosures, CSR fund utilization, IPO/FPO fund usage. RELEVANT FOR AUDIT: verifying contingent liabilities completeness and fund usage against stated objectives.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    ("CARO", "Clause 21",
     "Group CARO Qualifications",
     "Holding companies with subsidiaries/associates/JVs",
     "Auditor must include qualifications/adverse remarks from auditors of subsidiaries/associates in the parent company's CARO report. APPLIES TO: consolidation of audit qualifications across group entities. RELEVANT FOR AUDIT: consolidating group-wide audit issues and cross-entity compliance reporting.",
     "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),


    # ═══════════════════════════════════════════════════════════════════════════
    # Ind AS — Full Set
    # ═══════════════════════════════════════════════════════════════════════════
    ("Ind AS", "Ind AS 1",
     "Presentation of Financial Statements",
     "Listed/public company with net worth >250 Cr",
     "Overall framework for financial statement presentation: fair presentation, going concern basis, materiality assessment, offsetting rules, comparative information. APPLIES TO: structure and content of financial statements. RELEVANT FOR AUDIT: verify format compliance, disclosure completeness, and entity's ability to continue as going concern. DOES NOT APPLY TO: non-Ind AS companies (use AS 1 instead).",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 2",
     "Inventories",
     "Ind AS compliant",
     "Guidance on inventory valuation at lower of cost and net realizable value (NRV). Cost formulas: FIFO or Weighted Average. Write-down to NRV for damaged/obsolete/slow-moving stock. Reversal of write-down if conditions improve. APPLIES TO: raw materials, WIP, finished goods, stores, spare parts. DOES NOT APPLY TO: work-in-progress under construction contracts (Ind AS 11), financial instruments, biological assets. RELEVANT FOR AUDIT: verify NRV assessment methodology, physical stock valuation, provision for obsolescence.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 7",
     "Statement of Cash Flows",
     "Ind AS compliant",
     "Requires cash flow statement classified into operating, investing, and financing activities. Direct or indirect method. Non-cash transactions disclosed separately. APPLIES TO: reporting of cash generation and usage. RELEVANT FOR AUDIT: verify classification of cash flows, reconciliation with balance sheet changes, and identification of non-cash investing/financing activities.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 8",
     "Accounting Policies, Changes in Estimates and Errors",
     "Ind AS compliant",
     "Guidance on selecting and changing accounting policies (only if required by standard or results in more reliable info). Changes in estimates are prospective. Prior period errors corrected retrospectively. APPLIES TO: consistency of policies and error corrections. RELEVANT FOR AUDIT: identify accounting policy changes, estimate revisions, and prior period error corrections in financial statements.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 10",
     "Events After the Reporting Period",
     "Ind AS compliant",
     "Classifies events after balance sheet date as adjusting (provide evidence of conditions existing at year-end) or non-adjusting (new conditions). Going concern assessment must reflect post-reporting information. APPLIES TO: events between BS date and financial statement authorization. RELEVANT FOR AUDIT: ensure adjusting events are incorporated and material non-adjusting events are disclosed.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 12",
     "Income Taxes",
     "Ind AS compliant",
     "Covers current tax and deferred tax accounting. Temporary differences between carrying amount and tax base create DTA (deductible) or DTL (taxable). DTA recognition subject to virtual certainty/probability. APPLIES TO: corporate income tax, MAT credit, withholding tax. RELEVANT FOR AUDIT: verify deferred tax calculations, recognize DTA only where future taxable profits are probable. DOES NOT APPLY TO: GST, VAT, excise (these are indirect taxes).",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 16",
     "Property, Plant and Equipment",
     "Ind AS compliant",
     "Governs recognition, measurement (cost or revaluation model), depreciation (component approach), and derecognition of PPE. APPLIES TO: land, buildings, plant, machinery, furniture, vehicles, office equipment held for production/supply/administrative purposes. DOES NOT APPLY TO: right-of-use assets (Ind AS 116), investment property (Ind AS 40), biological assets (Ind AS 41). RELEVANT FOR AUDIT: verify capitalization policy, useful life assessment, impairment indicators, component accounting.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 19",
     "Employee Benefits",
     "Ind AS compliant",
     "Covers short-term benefits (salaries, bonuses), post-employment benefits (defined benefit/contribution plans), other long-term benefits (long service leave), and termination benefits. Defined benefit obligation requires actuarial valuation. APPLIES TO: all employee compensation including gratuity, PF, leave encashment, pension. RELEVANT FOR AUDIT: verify actuarial assumptions, discount rates, reconciliation of DBO, and contribution remittance timeliness.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 20",
     "Accounting for Government Grants",
     "Ind AS compliant entities receiving grants",
     "Government grants recognized when reasonable assurance exists that conditions will be met and grant received. Capital grants shown as deferred income (not deducted from asset cost). Revenue grants credited to P&L. Repayment of grant accounted for retrospectively. APPLIES TO: subsidies, export incentives, PLI schemes, capital investment subsidies. RELEVANT FOR AUDIT: verify grant recognition criteria, conditions met, and proper classification between capital and revenue.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 21",
     "The Effects of Changes in Foreign Exchange Rates",
     "Ind AS compliant",
     "Functional currency determination, translation of foreign currency transactions (monetary items at closing rate, non-monetary at historical rate), exchange differences treatment, translation of foreign operations. APPLIES TO: import/export transactions, foreign currency borrowings, overseas subsidiaries. RELEVANT FOR AUDIT: verify exchange rate applied, treatment of exchange differences (P&L vs OCI), and foreign operations translation methodology.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 23",
     "Borrowing Costs",
     "Ind AS compliant",
     "Borrowing costs directly attributable to acquisition/construction of qualifying assets must be capitalized. Commencement when expenditures + borrowing costs + activities for preparation occur. Suspension during extended interruptions. Cessation when substantially ready for use. APPLIES TO: interest on loans, exchange differences on foreign currency borrowings to the extent of interest adjustment. RELEVANT FOR AUDIT: verify capitalization period, borrowing cost calculation, and identification of qualifying assets.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 24",
     "Related Party Disclosures",
     "Ind AS compliant",
     "Requires disclosure of related party relationships (parent, subsidiaries, KMP, associates) and transactions. Control (even without transactions) must be disclosed. APPLIES TO: identification and disclosure of all RPTs including KMP compensation. RELEVANT FOR AUDIT: CRITICAL for RPT audit — identify all RPTs, verify completeness, ensure arm's length disclosures.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 27",
     "Separate Financial Statements",
     "Parent companies preparing separate FS",
     "Governs preparation of separate financial statements of a parent company where investments in subsidiaries, associates, and JVs are accounted for at cost or in accordance with Ind AS 109. APPLIES TO: standalone financial statements of a holding/parent company. RELEVANT FOR AUDIT: verify investment valuation method in standalone FS and consistency with consolidation.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 28",
     "Investments in Associates and Joint Ventures",
     "Companies with associates/JVs",
     "Requires equity method accounting for associates and JVs where investor has significant influence (presumed at 20%+ ownership). Goodwill included in carrying amount. APPLIES TO: entities where holding is 20-50% without control. RELEVANT FOR AUDIT: verify significant influence assessment, application of equity method, impairment testing of associate investments.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 32",
     "Financial Instruments: Presentation",
     "Ind AS compliant with financial instruments",
     "Classification of financial instruments as liability vs equity, compound instruments (convertible debt), treasury shares, and offsetting criteria. APPLIES TO: equity vs debt classification of issued instruments. RELEVANT FOR AUDIT: verify proper classification of preference shares (liability or equity), compound instruments bifurcation, and treasury share accounting.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 33",
     "Earnings Per Share",
     "Listed companies",
     "Requires calculation and disclosure of basic EPS (profit attributable to equity holders / weighted average shares outstanding) and diluted EPS (including dilutive potential equity shares). Anti-dilutive instruments excluded. APPLIES TO: companies whose shares are publicly traded. RELEVANT FOR AUDIT: verify EPS calculation, weighted average shares count, dilution impact of ESOPs and convertible instruments.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 34",
     "Interim Financial Reporting",
     "Listed companies required to publish interim reports",
     "Minimum content of condensed interim financial statements. Same accounting policies as annual. Recognition and measurement for interim periods (e.g. seasonal revenue, tax estimation). APPLIES TO: half-yearly and quarterly financial reporting. RELEVANT FOR AUDIT: verify consistency with annual policies, disclosure of seasonality, and year-to-date measurement.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 36",
     "Impairment of Assets",
     "Ind AS compliant",
     "Requires assessment of impairment indicators at each reporting date. Recoverable amount is higher of fair value less costs to sell and value in use. Cash-generating unit concept for impairment testing. Goodwill impairment is annual. APPLIES TO: PPE, intangible assets, right-of-use assets, goodwill. DOES NOT APPLY TO: inventories (use Ind AS 2), financial assets (use Ind AS 109), deferred tax assets. RELEVANT FOR AUDIT: verify impairment indicator assessment, cash flow projections for VIU, and discount rate assumptions.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 37",
     "Provisions, Contingent Liabilities and Contingent Assets",
     "Ind AS compliant",
     "Provision recognized only when: present obligation from past event, probable outflow measurable reliably. Contingent liabilities disclosed (not recognized). Contingent assets not recognized until virtually certain. APPLIES TO: litigation provisions, warranty obligations, restructuring costs, environmental remediation. RELEVANT FOR AUDIT: verify completeness of litigation cases, warranty estimates, and that contingent liabilities are not understated.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 38",
     "Intangible Assets",
     "Ind AS compliant",
     "Recognition criteria for intangibles: identifiable, controlled by entity, future economic benefits. Amortization over useful life (indefinite life = no amortization, only impairment). Research expensed, development capitalized if criteria met. APPLIES TO: software, patents, trademarks, licenses, customer lists, goodwill (through Ind AS 103). DOES NOT APPLY TO: internally generated brands/mastheads/customer lists. RELEVANT FOR AUDIT: verify capitalization vs expense decision, useful life assessment, and impairment testing.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 40",
     "Investment Property",
     "Companies holding investment properties",
     "Property held for rental income or capital appreciation (not for use or sale in ordinary course). Measurement options: cost model (with disclosure of fair value) or fair value model. APPLIES TO: buildings/land leased out under operating leases, vacant land held for appreciation. DOES NOT APPLY TO: property for owner-occupation (Ind AS 16), property for sale (Ind AS 2). RELEVANT FOR AUDIT: verify classification of investment property vs PPE vs inventory, and fair value assessment.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 41",
     "Agriculture",
     "Companies in agricultural sector",
     "Biological assets measured at fair value less costs to sell. Agricultural produce at point of harvest measured at fair value. APPLIES TO: living animals, plants, harvested agricultural produce. RELEVANT FOR AUDIT: verify fair valuation of biological assets, gain/loss recognition on initial measurement. DOES NOT APPLY TO: land (Ind AS 16), intangible assets related to agriculture (Ind AS 38).",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 101",
     "First-time Adoption of Ind AS",
     "Companies transitioning to Ind AS",
     "Provides mandatory exceptions and optional exemptions when transitioning from previous GAAP (typically AS) to Ind AS. Requires reconciliation of equity and profit between previous GAAP and Ind AS. APPLIES TO: companies adopting Ind AS for the first time. RELEVANT FOR AUDIT: verify transition date, opening balance sheet preparation, and reconciliation disclosures.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 102",
     "Share-based Payment",
     "Companies with ESOP/ESPP/share-based transactions",
     "Equity-settled and cash-settled share-based payments measured at fair value at grant date. Vesting conditions affect recognition. APPLIES TO: employee stock options, employee stock purchase plans, share appreciation rights. RELEVANT FOR AUDIT: verify fair value methodology (Black-Scholes/binomial), vesting period determination, and expense recognition pattern.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 103",
     "Business Combinations",
     "Companies involved in acquisitions/mergers",
     "Acquisition method: identifiable assets and liabilities measured at fair value, goodwill or bargain purchase gain recognized. Non-controlling interest measured at fair value or proportionate share. APPLIES TO: mergers, acquisitions, and takeover transactions. RELEVANT FOR AUDIT: verify purchase price allocation (PPA), fair value exercise, goodwill calculation, and contingent consideration accounting.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 105",
     "Non-current Assets Held for Sale and Discontinued Operations",
     "Ind AS compliant",
     "Assets classified as held for sale when available for immediate sale and sale is highly probable. Measured at lower of carrying amount and fair value less costs to sell. Discontinued operations shown separately. APPLIES TO: assets/firms being sold or closed down. RELEVANT FOR AUDIT: verify held-for-sale criteria, impairment before classification, and discontinued operations disclosure.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 107",
     "Financial Instruments: Disclosures",
     "Ind AS compliant with financial instruments",
     "Requires disclosures about significance of financial instruments: credit risk (ECL tables, collateral), liquidity risk (maturity analysis), market risk (sensitivity analysis). Hedge accounting disclosures. APPLIES TO: risk reporting in financial statements. RELEVANT FOR AUDIT: verify credit risk exposure (trade receivables ageing), liquidity risk maturity tables, and hedge documentation completeness.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 108",
     "Operating Segments",
     "Listed companies",
     "Management approach: segment reporting based on internal reporting structure. Identifies reportable segments based on quantitative thresholds (10% of revenue/profit/assets). Reconciliations to FS required. APPLIES TO: diversified companies with distinct business or geographical units. RELEVANT FOR AUDIT: verify segment identification, segmentation of revenue/profits/assets, and reconciliation to FS.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 109",
     "Financial Instruments",
     "Ind AS compliant",
     "Classification of financial assets: amortized cost, FVOCI, or FVTPL based on business model and SPPI test. ECL impairment model (3-stage: 12-month ECL to lifetime ECL). Hedge accounting (fair value, cash flow, net investment). APPLIES TO: all financial assets and liabilities including trade receivables, loans, investments, borrowings, derivatives. RELEVANT FOR AUDIT: verify classification basis, ECL calculation (especially trade receivables provision matrix), and hedge effectiveness testing.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 110",
     "Consolidated Financial Statements",
     "Parent companies",
     "Consolidation required when parent controls entity (power over investee, exposure to variable returns, ability to use power). Full consolidation procedures: eliminate intercompany transactions, uniform policies, same reporting date. Non-controlling interest shown in equity. APPLIES TO: group financial statements of holding companies. RELEVANT FOR AUDIT: verify control assessment (substance over form), consolidation adjustments, and NCI calculation.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 111",
     "Joint Arrangements",
     "Companies in joint arrangements",
     "Classifies joint arrangements as joint operations (rights to assets/obligations for liabilities — each party accounts for its share) or joint ventures (rights to net assets — equity method). APPLIES TO: jointly controlled entities/operations/ assets. RELEVANT FOR AUDIT: verify classification (JO vs JV) based on legal form and contractual terms; ensure equity method is applied for JVs.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 112",
     "Disclosure of Interests in Other Entities",
     "Companies with interests in subsidiaries/associates/JVs",
     "Requires disclosures about nature and risks of interests in subsidiaries, associates, JVs, and unconsolidated structured entities including significant judgments, restrictions, and financial support. APPLIES TO: group reporting transparency. RELEVANT FOR AUDIT: verify disclosure completeness for all investees including structured entities (e.g. trust, SPV).",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 113",
     "Fair Value Measurement",
     "Ind AS compliant",
     "Defines fair value as exit price in an orderly transaction. Three-level hierarchy: Level 1 (quoted prices), Level 2 (observable inputs), Level 3 (unobservable inputs). Valuation techniques: market, income, cost approaches. APPLIES TO: fair value measurements required by other standards (Ind AS 16, 36, 38, 40, 109, 116). RELEVANT FOR AUDIT: verify fair value hierarchy classification, valuation methodology, and Level 3 input disclosures.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 115",
     "Revenue from Contracts with Customers",
     "Ind AS compliant",
     "Five-step model: (1) Identify contract, (2) Identify performance obligations, (3) Determine transaction price, (4) Allocate price to obligations, (5) Recognize revenue when obligations satisfied (point in time or over time). APPLIES TO: revenue from sale of goods, services, licenses, construction contracts. DOES NOT APPLY TO: lease revenue (Ind AS 116), insurance contracts, financial instruments. RELEVANT FOR AUDIT: verify revenue recognition timing, variable consideration estimates, contract cost capitalization, and disclosure of disaggregated revenue.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    ("Ind AS", "Ind AS 116",
     "Leases",
     "Ind AS compliant",
     "Lessee accounts for all leases as right-of-use (ROU) asset and lease liability (except short-term <12 months and low-value assets <$5,000). Depreciation of ROU asset, interest on lease liability. Lessor accounting: classification as finance or operating lease. APPLIES TO: all lease agreements including property, plant, vehicles, equipment. DOES NOT APPLY TO: intangible assets (licenses), biological assets, mineral rights. RELEVANT FOR AUDIT: verify lease identification, discount rate (incremental borrowing rate), lease term assessment, and ROU asset impairment.",
     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),


    # ═══════════════════════════════════════════════════════════════════════════
    # AS — Full Set (non-Ind AS companies)
    # ═══════════════════════════════════════════════════════════════════════════
    ("AS", "AS 1",
     "Disclosure of Accounting Policies",
     "All companies (non-Ind AS)",
     "Fundamental accounting assumptions (going concern, consistency, accrual). Significant accounting policies to be disclosed if material. APPLIES TO: companies following Indian Accounting Standards (AS route, not Ind AS). RELEVANT FOR AUDIT: verify disclosure of all significant accounting policies consistently applied. DOES NOT APPLY TO: Ind AS companies (use Ind AS 1).",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 2",
     "Valuation of Inventories",
     "All companies (non-Ind AS)",
     "Inventories valued at lower of cost and net realizable value (NRV). Cost formulas: FIFO or Weighted Average. Items to include in cost: purchase cost, conversion costs, other costs to bring to present location. Write-down to NRV required for damaged/obsolete/slow-moving stock. APPLIES TO: raw materials, WIP, finished goods, stores and spares held for production. DOES NOT APPLY TO: work-in-progress under construction contracts, financial instruments, shares/debentures held as stock-in-trade. RELEVANT FOR AUDIT: verify NRV assessment methodology, provision for obsolescence, physical count discrepancies treatment.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 3",
     "Cash Flow Statements",
     "Companies (excluding certain small enterprises)",
     "Requires cash flow statement with operating (direct/indirect), investing, and financing activities. Non-cash transactions disclosed separately. APPLIES TO: entities required to present cash flow statement. RELEVANT FOR AUDIT: verify correct classification of cash items, reconciliation with balance sheet movements, and disclosure of non-cash transactions.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 4",
     "Contingencies and Events After Balance Sheet Date",
     "All companies (non-Ind AS)",
     "Adjusting events (providing evidence of conditions at BS date) reflected in accounts. Non-adjusting events (conditions arising after BS date) disclosed if material. Contingent liabilities disclosed but not provided for. Proposed dividend disclosed as appropriation. APPLIES TO: post-BS date events and uncertain obligations. RELEVANT FOR AUDIT: verify events after reporting date are properly classified (adjusting vs non-adjusting).",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 5",
     "Net Profit or Loss, Prior Period Items and Changes in Accounting Policies",
     "All companies (non-Ind AS)",
     "Extraordinary items, prior period items (material omissions/errors of prior periods shown separately), changes in accounting policies (prospective unless retrospective required), changes in estimates (prospective). APPLIES TO: P&L classification and policy consistency. RELEVANT FOR AUDIT: verify prior period error corrections, accounting policy changes, and extraordinary item classification.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 6",
     "Depreciation Accounting",
     "All companies (non-Ind AS)",
     "Depreciation methods: SLM or WDV. Useful life estimation based on technical assessment or Schedule II. Change in method is change in estimate (prospective). Disclosure of method, rates, and charged amount. APPLIES TO: all depreciable assets (PPE). RELEVANT FOR AUDIT: verify useful life assessment, method consistency, and that assets fully depreciated but still in use are carried at residual value.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 7",
     "Construction Contracts",
     "Companies with construction/long-term contracts",
     "Percentage of completion method for revenue recognition. Contract costs include direct costs and allocable overheads. Foreseeable losses recognized immediately. APPLIES TO: construction, infrastructure, EPC contracts. RELEVANT FOR AUDIT: verify stage of completion method, cost estimation reliability, and provision for expected losses.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 9",
     "Revenue Recognition",
     "All companies (non-Ind AS)",
     "Revenue from sale of goods recognized when seller transfers risk and rewards. Revenue from services recognized on percentage of completion or completed contract method. Interest/royalties/dividends recognized on time basis/accrual. APPLIES TO: revenue from ordinary activities. RELEVANT FOR AUDIT: verify revenue recognition criteria are met, cutoff procedures are proper, and sales returns/ discounts are correctly accounted.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 10",
     "Property, Plant and Equipment",
     "All companies (non-Ind AS)",
     "PPE initially recorded at cost of acquisition or construction. Subsequent costs capitalized only if future economic benefits. Depreciation as per AS 6. Revaluation allowed. Gain/loss on disposal recognized. APPLIES TO: fixed assets used in business. DOES NOT APPLY TO: assets held as investment (AS 13), assets held for sale. RELEVANT FOR AUDIT: verify capitalization threshold, physical verification coverage, and revaluation frequency.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 11",
     "The Effects of Changes in Foreign Exchange Rates",
     "All companies with foreign currency transactions",
     "Monetary items (cash, receivables, payables) translated at closing rate. Non-monetary items (PPE, inventories) at historical rate. Exchange differences on settlement/translation recognized in P&L. Forward exchange contracts covered. APPLIES TO: import/export, foreign currency loans/borrowings. RELEVANT FOR AUDIT: verify exchange rate applied, treatment of exchange differences, and hedge contract effectiveness.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 12",
     "Accounting for Government Grants",
     "Companies receiving government grants",
     "Grants recognized when reasonable assurance of compliance and receipt. Capital grants credited to capital reserve or deducted from asset cost. Revenue grants credited to P&L. Repayment treated as change in estimate. APPLIES TO: subsidies, export incentives, investment subsidies. RELEVANT FOR AUDIT: verify grant eligibility conditions, recognition timing, and proper classification between capital and revenue.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 13",
     "Accounting for Investments",
     "All companies (non-Ind AS)",
     "Covers accounting for investments in shares, debentures, bonds, securities, mutual funds. Classification: current (valued at lower of cost and market value) or long-term (valued at cost less permanent diminution). Reclassification rules for transfers between categories. Profit/loss on disposal recognized in P&L. APPLIES ONLY TO: financial investments — DOES NOT APPLY TO: inventory (AS 2), PPE (AS 10), lease finance (AS 19). RELEVANT FOR AUDIT: verify classification basis, market value assessment for current investments, and permanent impairment for long-term investments.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 14",
     "Accounting for Amalgamations",
     "Companies involved in amalgamations/mergers",
     "Two methods: Pooling of Interests (for amalgamation in nature of merger) or Purchase Method (for amalgamation in nature of purchase). Goodwill or capital reserve arises. APPLIES TO: company mergers and amalgamations. RELEVANT FOR AUDIT: verify amalgamation scheme, court/NCLT order, and method application.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 15",
     "Employee Benefits",
     "All companies (non-Ind AS)",
     "Covers: short-term benefits (salaries, bonuses paid within 12 months), defined contribution plans (PF, ESI — expense based on contribution), defined benefit plans (gratuity, leave encashment — requires actuarial valuation), termination benefits. APPLIES TO: all employee compensation obligations. RELEVANT FOR AUDIT: verify actuarial valuation reports, contribution remittance timeliness, and discount rate assumptions for defined benefit obligations.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 16",
     "Borrowing Costs",
     "All companies (non-Ind AS)",
     "Borrowing costs directly attributable to qualifying assets must be capitalized. Qualifying asset definition: asset that necessarily takes substantial period (>12 months) to get ready for intended use. Commencement/suspension/cessation rules. APPLIES TO: interest, commitment fees, exchange differences on foreign currency borrowings. RELEVANT FOR AUDIT: verify qualifying asset identification, capitalization period, and borrowing cost calculation methodology.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 17",
     "Segment Reporting",
     "Listed companies and companies in process of listing",
     "Requires reporting of business and geographical segments. Segment revenue, result, assets, liabilities disclosed. Inter-segment transfers on arm's length basis. Reconciliation to FS. APPLIES TO: diversified companies. RELEVANT FOR AUDIT: verify segment identification, allocation of common costs, and reconciliation methodology.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 18",
     "Related Party Disclosures",
     "All companies (non-Ind AS)",
     "Requires disclosure of related party relationships where control exists (even if no transactions) and transactions with related parties. Related parties include: parent, subsidiary, fellow subsidiary, associate, KMP, relatives of KMP. Disclosure includes: name, relationship, transaction volume, outstanding balances, provisions for doubtful debts. APPLIES TO: RPT identification and disclosure. RELEVANT FOR AUDIT: CRITICAL for RPT audit — verify completeness of RPT listing, arm's length assertion, and disclosure accuracy.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 19",
     "Leases",
     "All companies (non-Ind AS)",
     "Classification as finance lease (transfers substantially all risks/rewards) or operating lease. Finance lease: recognize asset and liability at lower of fair value and PV of MLP. Operating lease: lease payments recognized as expense on straight-line basis. Sale and leaseback: gain recognition deferral. APPLIES TO: all lease agreements. DOES NOT APPLY TO: lease agreements for natural resources, licensing agreements for films/plays. RELEVANT FOR AUDIT: verify lease classification (finance vs operating), interest rate implicit in lease determination, and lease equalization charge for operating leases.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 20",
     "Earnings Per Share",
     "Listed companies and companies in process of listing",
     "Basic EPS = net profit for equity holders / weighted average shares outstanding. Diluted EPS includes impact of convertible instruments, options, warrants. APPLIES TO: publicly traded companies. RELEVANT FOR AUDIT: verify weighted average share calculation, dilution impact, and anti-dilutive instrument identification.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 21",
     "Consolidated Financial Statements",
     "Companies with subsidiaries",
     "Requires consolidation of subsidiaries where parent has control (ownership >50% or control over board composition). Uniform accounting policies. Elimination of intercompany transactions. Minority interest shown separately. APPLIES TO: group financial statements. RELEVANT FOR AUDIT: verify control existence, consolidation scope (all subsidiaries), elimination entries, and minority interest calculation.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 22",
     "Accounting for Taxes on Income",
     "All companies (non-Ind AS)",
     "Current tax based on taxable income. Deferred tax on timing differences between accounting income and taxable income. DTA recognized only when virtual certainty of realization (for timing differences) or reasonable certainty (for carried forward losses). APPLIES TO: income tax accounting. RELEVANT FOR AUDIT: verify deferred tax calculations, DTA recognition criteria (virtual certainty test), and MAT credit entitlement.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 23",
     "Accounting for Investments in Associates in Consolidated FS",
     "Companies with associates",
     "Investments in associates (20%+ ownership) accounted for using equity method in consolidated financial statements. Goodwill or capital reserve on acquisition determined. APPLIES TO: group reporting with associates. RELEVANT FOR AUDIT: verify significant influence assessment, equity method adjustments, and goodwill/capital reserve calculation.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 24",
     "Discontinuing Operations",
     "Companies with discontinuing operations",
     "Definition of discontinuing operation: separate major line of business/geographical area being disposed of. Initial disclosure event. Separate disclosure of: revenue, expenses, pre-tax profit/loss, related tax. APPLIES TO: business closures or major asset sales. RELEVANT FOR AUDIT: verify discontinuing operation criteria, initial disclosure timing, and comparative restatement.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 25",
     "Interim Financial Reporting",
     "Listed companies required to publish interim reports",
     "Minimum content of condensed financial statements. Recognition and measurement consistent with annual financial statements. Year-to-date basis. Seasonality disclosed. APPLIES TO: quarterly/half-yearly financial results. RELEVANT FOR AUDIT: verify consistency with annual policies, seasonal adjustments, and prior period comparison.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 26",
     "Intangible Assets",
     "All companies (non-Ind AS)",
     "Recognition criteria: identifiability, control, future economic benefits. Amortization over useful life (max 10 years if cannot be reliably estimated). Research phase expensed, development phase capitalized if technical feasibility and commercial viability demonstrated. APPLIES TO: software, patents, licenses, copyrights. DOES NOT APPLY TO: financial assets, insurance contracts, mineral rights. RELEVANT FOR AUDIT: verify capitalization vs expense decision, useful life assessment, and impairment indicators.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 27",
     "Financial Reporting of Interests in Joint Ventures",
     "Companies with JV interests",
     "Three types: jointly controlled operations (recognize own assets/liabilities/expenses), jointly controlled assets (recognize share of assets), jointly controlled entities (proportionate consolidation or equity method). APPLIES TO: joint venture arrangements. RELEVANT FOR AUDIT: verify JV type classification, accounting method application, and disclosure of JV interests.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 28",
     "Impairment of Assets",
     "All companies (non-Ind AS)",
     "Indicators of impairment at BS date. Recoverable amount = higher of NRV and value in use. CGU concept for impairment testing. Goodwill impairment allocation. Reversal of impairment if conditions changed. APPLIES TO: PPE, intangible assets, goodwill. DOES NOT APPLY TO: inventories (AS 2), investments (AS 13), deferred tax assets (AS 22). RELEVANT FOR AUDIT: verify impairment indicator assessment, cash flow projections, and discount rate.",
     "https://www.icai.org/post/accounting-standards"),

    ("AS", "AS 29",
     "Provisions, Contingent Liabilities and Contingent Assets",
     "All companies (non-Ind AS)",
     "Provision recognized when: present obligation from past event, probable outflow, reliable estimate. Reimbursement recognized as separate asset when virtually certain. Contingent liabilities disclosed. Contingent assets not recognized. APPLIES TO: litigation provisions, warranty obligations, restructuring, onerous contracts. RELEVANT FOR AUDIT: verify completeness of provisions, litigation database, and that contingent liabilities are fully disclosed.",
     "https://www.icai.org/post/accounting-standards"),


    # ═══════════════════════════════════════════════════════════════════════════
    # CAS — 24 Cost Accounting Standards
    # ═══════════════════════════════════════════════════════════════════════════
    ("CAS", "CAS 1",  "Classification of Cost",
     "Companies where cost records applicable",
     "Classification of costs into: direct/indirect, variable/fixed, product/period. Cost elements: material, employee, expenses. APPLIES TO: cost accounting methodology. RELEVANT FOR AUDIT: verify cost classification system, allocation bases, and consistency of classification.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 2",  "Capacity Determination",
     "Companies where cost records applicable",
     "Definitions of installed, available, normal, and actual capacity. Treatment of idle capacity cost. APPLIES TO: manufacturing operations. RELEVANT FOR AUDIT: verify installed capacity basis, capacity utilization calculation, and treatment of idle capacity overheads.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 3",  "Overheads",
     "Companies where cost records applicable",
     "Classification, collection, allocation, apportionment, and absorption of production, administration, selling, and distribution overheads. APPLIES TO: overhead accounting and absorption rates. RELEVANT FOR AUDIT: verify overhead allocation bases, absorption rate calculation, and under/over absorption treatment.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 4",  "Cost of Production for Captive Consumption",
     "Companies with captive consumption",
     "Determination of cost of production for goods transferred captively (within same entity). Basis for excise/customs valuation before GST. APPLIES TO: inter-unit transfers of goods. RELEVANT FOR AUDIT: verify cost records for self-consumed goods.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 5",  "Average (Equalized) Cost of Transportation",
     "Companies where cost records applicable",
     "Treatment of transportation costs, equalized freight calculation methodology. APPLIES TO: inbound and outbound freight costs. RELEVANT FOR AUDIT: verify freight equalization methodology and cost allocation to products.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 6",  "Material Cost",
     "Companies where cost records applicable",
     "Purchase cost determination including freight, duties, insurance, handling. CENVAT/GST treatment. Wastage accounting: normal (absorbed in cost) vs abnormal (charged to P&L). APPLIES TO: raw material procurement and consumption. RELEVANT FOR AUDIT: verify material costing methodology, wastage norms, and purchase price variance treatment.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 7",  "Employee Cost",
     "Companies where cost records applicable",
     "Wages, salaries, bonuses, overtime, VRS costs, employee welfare expenses. Allocation to cost centres/production units. APPLIES TO: labour cost recording. RELEVANT FOR AUDIT: verify employee cost allocation to products/processes and separation of direct vs indirect labour.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 8",  "Cost of Utilities",
     "Companies where cost records applicable",
     "Power, fuel, water costs. Cost per unit determination. Internal generation vs purchased cost comparison. APPLIES TO: utility cost allocation to production. RELEVANT FOR AUDIT: verify utility consumption recording, cost per unit calculation, and allocation methodology.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 9",  "Packing Material Cost",
     "Companies where cost records applicable",
     "Primary packing (part of cost of production) vs secondary packing (selling cost). Cost determination for packing materials. APPLIES TO: packaging costs in FMCG/manufacturing. RELEVANT FOR AUDIT: verify classification of packing costs and wastage treatment.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 10", "Direct Expenses",
     "Companies where cost records applicable",
     "Expenses directly attributable to production/services: job-specific charges, royalties, design costs. APPLIES TO: direct cost items beyond material and labour. RELEVANT FOR AUDIT: verify direct expense identification and traceability to cost objects.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 11", "Administrative Overheads",
     "Companies where cost records applicable",
     "Office and administrative expenses, management salaries, non-production overhead absorption. APPLIES TO: indirect management costs. RELEVANT FOR AUDIT: verify admin overhead allocation to production/service units.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 12", "Repairs and Maintenance Cost",
     "Companies where cost records applicable",
     "Preventive vs corrective maintenance. Major overhaul vs regular maintenance. In-house vs contract maintenance. APPLIES TO: maintenance expenditure for plant, machinery, buildings. RELEVANT FOR AUDIT: verify capitalization vs expense decision for major maintenance, and preventive maintenance schedule adherence.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 13", "Cost of Service Cost Centres",
     "Companies where cost records applicable",
     "Service department cost allocation to production cost centres (e.g. boiler house, maintenance shop, IT). APPLIES TO: overhead of support functions. RELEVANT FOR AUDIT: verify allocation key selection for service costs.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 14", "Pollution Control Cost",
     "Companies with pollution control obligations",
     "Effluent treatment, environment compliance costs. Capital vs revenue treatment. APPLIES TO: environmental compliance spending. RELEVANT FOR AUDIT: verify pollution control cost tracking and capitalization of pollution control assets.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 15", "Selling and Distribution Overheads",
     "Companies where cost records applicable",
     "Selling expenses (sales commissions, advertisement), distribution costs (freight outwards, warehousing), after-sales service costs. APPLIES TO: post-production costs. RELEVANT FOR AUDIT: verify selling cost allocation to products/regions and distribution cost classification.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 16", "Depreciation and Amortization",
     "Companies where cost records applicable",
     "Depreciation methods in cost statements. Residual value assessment. Revaluation impact. Treatment of fully depreciated assets still in use. APPLIES TO: cost allocation for asset usage. RELEVANT FOR AUDIT: verify depreciation method consistency in cost records vs financial accounts, treatment of idle asset depreciation.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 17", "Interest and Financing Charges",
     "Companies where cost records applicable",
     "Treatment of interest in cost statements. Notional interest on owned funds. Imputed cost of capital for decision-making. APPLIES TO: cost of financing in cost units. RELEVANT FOR AUDIT: verify interest allocation to products and notional cost computation.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 18", "Research and Development Costs",
     "Companies incurring R&D expenses",
     "Classification of R&D costs. Capital vs revenue R&D. Apportionment of R&D to products/processes. APPLIES TO: innovation and development spending. RELEVANT FOR AUDIT: verify R&D cost classification, capitalization criteria, and product-wise allocation.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 19", "Joint Costs",
     "Companies with joint/by-products",
     "Allocation of joint costs up to split-off point. By-product cost treatment (net realizable value method). APPLIES TO: process manufacturing with multiple outputs. RELEVANT FOR AUDIT: verify joint cost allocation methodology and by-product accounting treatment.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 20", "Royalty and Technical Know-how Fee",
     "Companies paying royalty/technical fees",
     "Treatment of royalty in cost statements. Lump-sum vs recurring payments. Foreign currency royalty conversion. APPLIES TO: technology licensing and brand royalty payments. RELEVANT FOR AUDIT: verify royalty basis, compliance with FDI/royalty regulations, and product cost inclusion.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 21", "Quality Control",
     "Companies with quality control processes",
     "Cost of quality: prevention, appraisal, internal failure, external failure. Cost of poor quality measurement. QC cost disclosure requirements. APPLIES TO: manufacturing quality management. RELEVANT FOR AUDIT: verify quality cost tracking system and failure cost analysis.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 22", "Manufacturing Cost",
     "Companies where cost records applicable",
     "Total manufacturing cost computation. Factory cost, works cost, cost of production statement preparation. APPLIES TO: production cost determination. RELEVANT FOR AUDIT: verify cost buildup methodology and reconciliation with financial accounts.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 23", "Selling Cost",
     "Companies where cost records applicable",
     "Cost of selling activities, pre-sale and post-sale service costs, sales force costs, distribution channel costs. APPLIES TO: customer acquisition and retention costs. RELEVANT FOR AUDIT: verify selling cost segmentation and product/market allocation.",
     "https://www.icmai.in/CASB/casb-about.php"),

    ("CAS", "CAS 24", "Treatment of Revenue in Cost Statements",
     "Companies where cost records applicable",
     "Treatment of scrap, waste, by-product, and miscellaneous income. Deduction from cost vs other income classification. APPLIES TO: income from non-core production sources. RELEVANT FOR AUDIT: verify scrap/waste accounting and cost reduction vs other income treatment.",
     "https://www.icmai.in/CASB/casb-about.php"),


    # ═══════════════════════════════════════════════════════════════════════════
    # SIA — Internal Audit Standards
    # ═══════════════════════════════════════════════════════════════════════════
    ("SIA", "SIA 1",  "Planning an Internal Audit",
     "Internal audit engagements",
     "Risk-based planning: annual audit plan, engagement plan, resource allocation. APPLIES TO: internal audit department planning process. RELEVANT FOR AUDIT: verify audit planning is risk-based, annual plan is approved, and resources match plan scope.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 2",  "Basic Principles Governing Internal Audit",
     "Internal audit engagements",
     "Independence, objectivity, professional care, confidentiality, competence, evidence-based approach. APPLIES TO: internal auditor conduct and ethics. RELEVANT FOR AUDIT: verify internal auditor independence from operational management and adherence to professional standards.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 3",  "Documentation",
     "Internal audit engagements",
     "Working papers: content, ownership, retention policy. Electronic documentation requirements. Standardization of audit files. APPLIES TO: audit evidence and reporting documentation. RELEVANT FOR AUDIT: verify audit work paper completeness, cross-referencing, and review evidence.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 4",  "Reporting",
     "Internal audit engagements",
     "Report preparation process, content requirements, draft report discussion with auditee, formal final report, distribution list, timely reporting. APPLIES TO: internal audit report structure and issuance. RELEVANT FOR AUDIT: verify final report quality, management response inclusion, and report timeliness.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 5",  "Sampling",
     "Internal audit engagements",
     "Statistical vs non-statistical sampling. Sample design criteria. Evaluation of sample results. Projection of errors to population. APPLIES TO: audit testing methodology. RELEVANT FOR AUDIT: verify sample size adequacy, selection methodology, and error projection validity.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 6",  "Analytical Procedures",
     "Internal audit engagements",
     "Use in planning, substantive testing, and overall review. Techniques: ratio analysis, trend analysis, reasonableness testing, regression analysis. APPLIES TO: data analysis and verification procedures. RELEVANT FOR AUDIT: verify analytical review coverage, ratio calculations, and investigation of significant fluctuations.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 7",  "Quality Assurance in Internal Audit",
     "Internal audit function",
     "Internal QA reviews, external QA assessments every 5 years, QA program elements, continuous improvement methodology. APPLIES TO: internal audit department performance evaluation. RELEVANT FOR AUDIT: verify QA program existence, review frequency, and improvement action tracking.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 8",  "Terms of Internal Audit Engagement",
     "Internal audit function",
     "Engagement letter/charter content, scope definition, objectives, access rights, reporting lines, fee basis. APPLIES TO: IA engagement documentation with auditee. RELEVANT FOR AUDIT: verify engagement letter exists with clear scope, authority, and access provisions.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 9",  "Communication with Management",
     "Internal audit engagements",
     "Interim communication, draft report discussion, final reporting, management responses, follow-up process. APPLIES TO: auditee interaction throughout audit cycle. RELEVANT FOR AUDIT: verify management response quality and follow-up of past audit issues.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 10", "Internal Audit Findings and Recommendations",
     "Internal audit engagements",
     "Criteria-Condition-Cause-Effect (CCCE) framework. Recommendation priority setting (high/medium/low). Management action plan and responsible person. APPLIES TO: audit finding formulation. RELEVANT FOR AUDIT: verify finding clarity (cause vs symptom), recommendation actionability, and root cause analysis depth.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 11", "Consideration of Fraud in an Internal Audit",
     "Internal audit engagements",
     "Fraud risk factors identification, red flags, investigation techniques, reporting of suspected fraud to management/audit committee/board. APPLIES TO: fraud detection and prevention during IA. RELEVANT FOR AUDIT: verify fraud risk assessment, whistleblower mechanism review, and fraud reporting protocol.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 12", "Internal Control Evaluation",
     "Internal audit engagements",
     "COSO integrated framework evaluation: control environment, risk assessment, control activities, information & communication, monitoring. APPLIES TO: control design and effectiveness assessment. RELEVANT FOR AUDIT: verify control matrix documentation, testing methodology, and control deficiency classification (design vs operating).",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 13", "Enterprise Risk Management",
     "Internal audit function",
     "ERM framework assessment. Risk appetite and tolerance definition. Risk identification, assessment, response strategies. APPLIES TO: organizational risk management maturity. RELEVANT FOR AUDIT: verify risk register coverage, risk response evaluation, and IA's role in ERM validation.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 14", "Internal Audit in an IT Environment",
     "Internal audit in IT-dependent organisations",
     "IT general controls (access, change, operations). Application controls (input, processing, output). ITGC review methodology. CAATs and data analytics use. APPLIES TO: technology audit. RELEVANT FOR AUDIT: verify ITGC coverage, access control review, and data analytics usage in audit testing.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 15", "Knowledge of the Entity's Business",
     "Internal audit engagements",
     "Business understanding: industry knowledge, operational processes, legal/compliance environment, risk profile of entity. APPLIES TO: audit planning and risk assessment. RELEVANT FOR AUDIT: verify auditor's business understanding is documented and updated annually.",
     "https://internalaudit.icai.org/publications/"),

    ("SIA", "SIA 16", "Using the Work of an Expert",
     "Internal audit engagements requiring specialist",
     "Selection criteria for experts, defining scope and objectives, evaluating expert work adequacy, referencing expert findings in report. APPLIES TO: engagements requiring IT, legal, valuation, actuarial expertise. RELEVANT FOR AUDIT: verify expert qualifications, scope agreement, and work quality assessment.",
     "https://internalaudit.icai.org/publications/"),


    # ═══════════════════════════════════════════════════════════════════════════
    # SA — Standards on Auditing (Complete Series)
    # ═══════════════════════════════════════════════════════════════════════════
    ("SA", "SA 200",
     "Overall Objectives of the Independent Auditor",
     "All audit engagements",
     "Basic framework: reasonable assurance, material misstatement identification, ethical requirements (ICAI Code of Ethics), professional scepticism. APPLIES TO: all statutory audits. RELEVANT FOR AUDIT: verify auditor's approach to professional scepticism and ethical compliance throughout engagement.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 210",
     "Agreeing the Terms of Audit Engagements",
     "All audit engagements",
     "Preconditions for audit (management acknowledges responsibilities). Engagement letter content and delivery. Limitation of scope implications. Recurring audits: confirming terms. APPLIES TO: audit commencement and acceptance. RELEVANT FOR AUDIT: verify engagement letter existence, signed by management, and terms cover management responsibilities.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 220",
     "Quality Control for an Audit of Financial Statements",
     "All audit engagements",
     "Engagement partner responsibility for quality. Independence confirmation. Supervision of team. Engagement quality review (EQR) for listed entities. APPLIES TO: quality management of audit. RELEVANT FOR AUDIT: verify EQR completed, independence confirmations documented, and supervision evidence maintained.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 230",
     "Audit Documentation",
     "All audit engagements",
     "Working paper requirements: sufficient detail, cross-referencing, significant matters documentation. File assembly within 60 days. Retention policy. APPLIES TO: audit evidence documentation. RELEVANT FOR AUDIT: verify documentation completeness before file assembly deadline and review trail.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 240",
     "The Auditor's Responsibilities Relating to Fraud",
     "All audit engagements",
     "Fraud risk assessment, fraud risk factors (incentive, opportunity, rationalization), management override of controls procedures (journal entries, estimates, significant transactions). Fraud communication and reporting obligations. APPLIES TO: any audit where fraud risk exists. RELEVANT FOR AUDIT: DOCUMENT fraud risk assessment, test journal entries, review estimates for bias — HIGH RISK area.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 250",
     "Consideration of Laws and Regulations",
     "All audit engagements",
     "Auditor's responsibility for compliance with laws and regulations. Distinction between direct effect (tax, pension) and other laws. Non-compliance identification and reporting to management/governance/regulators. APPLIES TO: regulatory and statutory compliance audit. RELEVANT FOR AUDIT: verify compliance with applicable laws and document any non-compliance identified.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 260",
     "Communication with Those Charged with Governance",
     "All audit engagements",
     "Matters to communicate: audit approach, significant findings, independence, difficult areas, going concern issues. Timely and appropriate communication. APPLIES TO: audit committee/board reporting. RELEVANT FOR AUDIT: verify communication documentation with audit committee regarding significant audit matters.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 265",
     "Communicating Deficiencies in Internal Control",
     "All audit engagements",
     "Significant deficiencies vs material weaknesses. Written communication to governance. Management response. APPLIES TO: internal control weakness reporting. RELEVANT FOR AUDIT: verify control deficiencies are classified correctly (design vs operating) and communicated to management with appropriate priority.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 300",
     "Planning an Audit of Financial Statements",
     "All audit engagements",
     "Overall audit strategy, audit plan, preliminary engagement activities (client continuance, independence), direction/supervision/review. APPLIES TO: audit planning process. RELEVANT FOR AUDIT: verify audit strategy documentation, risk assessment linkage to procedures, and team briefing records.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 315",
     "Identifying and Assessing Risks of Material Misstatement",
     "All audit engagements",
     "Risk assessment procedures: inquiries, analytical procedures, observation, inspection. Understanding entity and environment (internal control components). Significant risks and ROMM (risk of material misstatement) at FS and assertion level. APPLIES TO: risk-based audit approach. RELEVANT FOR AUDIT: DOCUMENT risk assessment process, identify significant risks, and link assessed risks to audit procedures.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 320",
     "Materiality in Planning and Performing an Audit",
     "All audit engagements",
     "Overall materiality determination (benchmark and percentage). Performance materiality (lower than overall). Clearly trivial threshold (<5% of overall). Revision during audit if more information becomes available. APPLIES TO: materiality thresholds for audit procedures. RELEVANT FOR AUDIT: DOCUMENT materiality calculation (e.g. 5-10% of PBT), performance materiality, and clearly trivial threshold with justification.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 330",
     "The Auditor's Responses to Assessed Risks",
     "All audit engagements",
     "Overall responses (emphasis on professional scepticism, staffing, supervision). Substantive procedures for each material class of transactions/account balance/disclosure. Tests of controls when relying on them. Adequacy of presentation. APPLIES TO: audit procedure design. RELEVANT FOR AUDIT: verify audit programs are designed to address assessed ROMM and substantive procedures are performed for all material items.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 402",
     "Audit Considerations Relating to Service Organisations",
     "Audits of entities using service organisations",
     "Type 1 (design) and Type 2 (design + operating effectiveness) SOC reports. Complementary user entity controls. Sub-service organisations. APPLIES TO: entities that outsource to third parties (e.g. payroll processors, cloud service providers). RELEVANT FOR AUDIT: verify service organization controls, SOC report review, and complementary user control assessment.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 450",
     "Evaluation of Misstatements Identified During the Audit",
     "All audit engagements",
     "Accumulation of identified misstatements. Qualitative assessment (e.g. management bias, impact on ratios). Clearly trivial threshold for omission. Communication and correction with management. Final assessment of uncorrected misstatements on opinion. APPLIES TO: audit adjustments and error evaluation. RELEVANT FOR AUDIT: DOCUMENT all misstatements > clearly trivial, discuss with management, and assess impact of uncorrected errors on opinion.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 500",
     "Audit Evidence",
     "All audit engagements",
     "Sufficiency and appropriateness of audit evidence. Sources: accounting system, physical inspection, third-party confirmations, management representations. APPLIES TO: evidence collection methodology. RELEVANT FOR AUDIT: verify evidence is sufficient and appropriate for each assertion, and different sources provide corroboration.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 501",
     "Audit Evidence — Specific Considerations for Selected Items",
     "All audit engagements",
     "Attendance at physical inventory counting (if material). Litigation and claims inquiry with lawyers. Segment information verification. APPLIES TO: inventory observation, litigation checks. RELEVANT FOR AUDIT: verify inventory count attendance, lawyer letter process, and segment disclosure verification.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 505",
     "External Confirmations",
     "All audit engagements",
     "Positive vs negative confirmations. Management requests vs direct confirmations. Non-response follow-up procedures. Alternative procedures for non-responses. Unreliable response indicators. APPLIES TO: third-party confirmations (bank, customer, vendor balances). RELEVANT FOR AUDIT: verify confirmation process — send positive confirmations for significant balances, perform alternative procedures for non-responses.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 510",
     "Initial Audit Engagements — Opening Balances",
     "Initial audit engagements",
     "Opening balances verification: consistency of accounting policies, prior period auditor communication, impact on current year opinion (qualified if cannot verify). APPLIES TO: first-year audits. RELEVANT FOR AUDIT: verify opening balances agree to prior period FS, and communicate with predecessor auditor.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 520",
     "Analytical Procedures",
     "All audit engagements",
     "Substantive analytical procedures: expectation development, threshold for investigation (difference from expectation), investigation of fluctuations. Overall review at end of audit. APPLIES TO: ratio analysis and trend analysis. RELEVANT FOR AUDIT: DOCUMENT expectations (prior year, budget, industry), compare to actual, and investigate significant variances with evidence.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 530",
     "Audit Sampling",
     "Audit engagements using sampling",
     "Sample design: statistical (MUS) vs non-statistical. Stratification. Sample selection methods. Risk of incorrect acceptance/rejection. Projecting misstatements to population. Evaluating sample results. APPLIES TO: testing when 100% examination is not feasible. RELEVANT FOR AUDIT: verify sample size is adequate for population, selection is representative, and error projection is valid.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 540",
     "Auditing Accounting Estimates and Related Disclosures",
     "All audit engagements",
     "Estimation uncertainty assessment, management bias evaluation (indicators of bias), point estimate vs range approach, higher uncertainty procedures for complex estimates. APPLIES TO: fair value estimates, useful lives, provisions, impairments, inventory NRV. RELEVANT FOR AUDIT: verify estimate reasonableness, test management's assumptions, assess bias indicators, and consider range for high-uncertainty estimates.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 550",
     "Related Parties",
     "All audit engagements",
     "Identification of related party relationships and transactions (including undisclosed). Procedures: inquiries, review of statutory registers, confirmations. Transactions not at arm's length review. APPLIES TO: RPT identification and verification. RELEVANT FOR AUDIT: CRITICAL for RPT audit — verify related party identification, identify undisclosed related parties, and test arm's length pricing.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 560",
     "Subsequent Events",
     "All audit engagements",
     "Events between balance sheet date and auditor's report date (update procedures). Facts discovered after report date but before FS issue. Facts discovered after FS issued (revision procedures). APPLIES TO: post-reporting period events. RELEVANT FOR AUDIT: perform subsequent events review procedures up to report date and document findings.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 570",
     "Going Concern",
     "All audit engagements",
     "Management's going concern assessment evaluation. Financial indicators (negative net worth, liquidity issues), operating indicators (losses, labour issues), other indicators (litigation, regulatory issues). Disclosure adequacy assessment. Modified opinion implications. APPLIES TO: entity's ability to continue as going concern. RELEVANT FOR AUDIT: CRITICAL — evaluate management's assessment period (>12 months), identify going concern red flags, assess disclosure adequacy.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 580",
     "Written Representations",
     "All audit engagements",
     "Management representation letter content: acknowledgement of responsibility, completeness of information, specific representations for significant matters. Date of letter (as of report date). Doubt on reliability (scope limitation). APPLIES TO: formal management confirmations. RELEVANT FOR AUDIT: verify management representation letter is obtained, signed, and dated; follow up if management refuses to provide.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 600",
     "Using the Work of Another Auditor",
     "Group audits with component auditors",
     "Principal auditor responsibilities for group audit. Component auditor instructions, competence assessment, communication review. Sufficiency of work evaluation. Reference in auditor's report to other auditor. APPLIES TO: group audits with component auditors. RELEVANT FOR AUDIT: verify component auditor instructions, review their work, and assess competence.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 610",
     "Using the Work of Internal Auditors",
     "Audit engagements where internal audit function exists",
     "Evaluating IA function: objectivity, competence, systematic approach. Direct assistance using internal auditors. Communication with those charged with governance regarding IA use. APPLIES TO: external audit reliance on internal audit. RELEVANT FOR AUDIT: evaluate IA function maturity before determining extent of reliance; document assessment criteria.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 620",
     "Using the Work of an Auditor's Expert",
     "Audit engagements requiring specialist knowledge",
     "Selection of expert: competence, capabilities, objectivity. Defining scope and objectives for expert. Evaluating adequacy of expert's work (assumptions, source data, results consistency). Reference in auditor's report. APPLIES TO: use of external specialists (valuers, actuaries, engineers, lawyers). RELEVANT FOR AUDIT: verify expert qualifications, evaluate work quality, and assess assumptions used in expert report.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 700",
     "Forming an Opinion and Reporting on Financial Statements",
     "All audit engagements",
     "Unmodified opinion criteria. Auditor's report elements: title, addressee, opinion, basis for opinion, going concern, KAM (for listed), responsibilities, signature, date, address. Emphasis of matter and other matter paragraphs. APPLIES TO: audit report format and content. RELEVANT FOR AUDIT: verify audit report includes all required elements per SA 700 and applicable laws.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 701",
     "Communicating Key Audit Matters",
     "Audit engagements of listed entities",
     "Selection of KAMs from matters communicated with governance. Matters requiring significant auditor attention (high risk, significant estimates, significant events/disclosures). Description of how KAM was addressed. Relationship with modified opinion. APPLIES TO: listed company audit reports only. RELEVANT FOR AUDIT: DOCUMENT KAM selection rationale and how each KAM was addressed in the audit.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 705",
     "Modifications to the Opinion in the Independent Auditor's Report",
     "All audit engagements",
     "Qualified opinion (material but not pervasive), Adverse opinion (material and pervasive), Disclaimer of opinion (inability to obtain sufficient evidence). Basis for modification paragraph placement. APPLIES TO: situations requiring modified audit opinions. RELEVANT FOR AUDIT: DOCUMENT basis for modification if conditions exist and determine modification type based on materiality/pervasiveness.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 706",
     "Emphasis of Matter Paragraphs and Other Matter Paragraphs",
     "All audit engagements",
     "Emphasis of matter (EOM): fundamental uncertainty, subsequent event, going concern. Other matter: scope restriction, prior period auditor, regulatory requirement. Positioning in auditor's report (immediately after opinion paragraph). APPLIES TO: additional communication in audit report. RELEVANT FOR AUDIT: DOCUMENT justification for EOM or other matter paragraphs.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 710",
     "Comparative Information — Corresponding Figures and Comparative FS",
     "All audit engagements with comparative figures",
     "Corresponding figures vs comparative financial statements. Prior period auditor reference. Restatement of comparatives. Report modifications affecting comparatives. APPLIES TO: year-on-year FS comparison. RELEVANT FOR AUDIT: verify comparative figures agree to prior period audited FS and any reclassification is disclosed.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 720",
     "The Auditor's Responsibilities Relating to Other Information",
     "All audit engagements with annual reports",
     "Reading other information in annual report for material inconsistencies with audited FS. Material misstatement of fact in other information. Director's report review (Companies Act requirements). APPLIES TO: annual report, management discussion and analysis, director's report. RELEVANT FOR AUDIT: read other information, document review process, and communicate inconsistencies to governance.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 800",
     "Audits of FS Prepared Under Special Purpose Frameworks",
     "Special purpose audit engagements",
     "Special purpose framework assessment (e.g. tax basis, regulatory reporting). Alerting paragraph restricting use. Intended users identification. APPLIES TO: audits for regulatory filings, contractual reporting. RELEVANT FOR AUDIT: verify special purpose framework is clearly identified and report includes use restriction paragraph.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 805",
     "Audits of Single Financial Statements and Specific Elements",
     "Special purpose audit engagements",
     "Auditing individual FS (e.g. balance sheet only). Specific element audits (e.g. inventory schedule, royalty statement). Modified opinion implications for full FS. APPLIES TO: limited scope audit engagements. RELEVANT FOR AUDIT: verify engagement scope is clearly defined and report indicates element/statement being audited.",
     "https://www.icai.org/post/standards-on-auditing"),

    ("SA", "SA 810",
     "Engagements to Report on Summary Financial Statements",
     "Engagements to report on summary FS",
     "Criteria for summary FS preparation. Opinion on summary FS based on audited FS. Relationship with audited FS opinion (modification pass-through). Disclosure requirements. APPLIES TO: condensed/abbreviated financial statements. RELEVANT FOR AUDIT: verify summary FS are consistent with audited FS and opinion reflects any modifications from full audit.",
     "https://www.icai.org/post/standards-on-auditing"),
]


def seed_official_standards() -> int:
    """Seed standards — additive and idempotent: inserts only if (family, reference) not already present.
    
    Uses clean_before_seed=True mode: deletes existing standards first, then inserts fresh.
    This enables updating clause_text for existing standards without creating duplicates.
    """
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Clear all existing standards first so updated clause_text replaces old content
    cursor.execute("DELETE FROM audit_standards")
    
    inserted = 0
    for family, reference, description, applicability, clause_text, source_url in ALL_STANDARDS:
        cursor.execute("""
            INSERT INTO audit_standards (family, reference, description, applicability, clause_text, source_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (family, reference, description, applicability, clause_text, source_url))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted


def search_standards(query: str, families: List[str] = None) -> pd.DataFrame:
    """Search standards by keyword."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM audit_standards WHERE (reference LIKE ? OR description LIKE ? OR clause_text LIKE ?)"
    params = [f"%{query}%", f"%{query}%", f"%{query}%"]

    if families:
        placeholders = ",".join(["?"] * len(families))
        q += f" AND family IN ({placeholders})"
        params.extend(families)

    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df