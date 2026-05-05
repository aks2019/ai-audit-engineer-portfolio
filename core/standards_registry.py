"""Standards Registry - Knowledge Base for Audit Standards."""
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


# Complete official standards registry — additive, idempotent (checks per family+reference)
ALL_STANDARDS = [
    # ── Companies Act 2013 ─────────────────────────────────────────────────────
    ("Companies Act", "Section 128", "Books of Account to be kept by Company", "All companies", "Books of account to be kept at registered office, Electronic records allowed, Branch inspection rights", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 129", "Financial Statements", "All companies", "Balance sheet, P&L, Cash flow statement, Notes to accounts; Schedule III compliance mandatory", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 130", "Re-opening of Accounts on Court or Tribunal Orders", "Companies directed by court/tribunal", "Grounds for reopening: fraud, mismanagement, statutory non-compliance", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 133", "Central Government to Prescribe Accounting Standards", "All companies", "Accounting standards notified by MCA on NFRA/ICAI recommendation; mandatory compliance", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 134", "Board's Report", "All companies", "Board's report content: financial statements, directors' responsibility statement, internal financial controls, risk management", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 135", "Corporate Social Responsibility", "Companies with turnover >1000 Cr or net worth >500 Cr or profit >5 Cr", "CSR spending of 2% of avg net profit; CSR committee; disclosure in Board's report", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 138", "Internal Audit", "Prescribed class of companies", "Appointment of internal auditor (CA/CMA/any other professional); report to audit committee", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 139", "Appointment of Auditors", "All companies", "Rotation of auditors every 5/10 years, Casual vacancy, First auditor appointment by Board", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 140", "Removal and Resignation of Auditor", "All companies", "Removal requires special resolution and CG approval; Resignation requires filing Form ADT-3", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 141", "Eligibility and Qualifications of Auditors", "All companies", "CA in practice required; disqualifications include directorship, financial interest, relative employment", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 143", "Auditor's Report", "All companies", "Auditor to report on financial statements, CARO applicability, internal financial controls", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 144", "Auditor Not to Render Certain Services", "All companies", "Non-audit services prohibited: accounting, internal audit, actuarial, investment advisory, management services", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 148", "Central Government to Specify Audit of Cost Records", "Companies to which Cost Audit Order applies", "Cost audit applicability, Cost auditor appointment (CMA), Cost audit report filing with MCA", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 177", "Audit Committee", "Listed companies and prescribed public companies", "Minimum 3 directors with majority independent; reviews internal audit, financial reporting, RPTs", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 185", "Loan to Directors", "All companies", "Prohibition on loans/guarantees to directors; exceptions for wholly-owned subsidiaries; penalty for contravention", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 186", "Loan and Investment by Company", "All companies", "60% of paid-up capital+free reserves or 100% of free reserves limit; Board/SR approval; register maintenance", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 188", "Related Party Transactions", "All companies", "Prior Board/SR approval; omnibus approval by audit committee; arm's length test; register of contracts", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 197", "Overall Maximum Managerial Remuneration", "Companies paying managerial remuneration", "11% of net profits ceiling; individual limits for MD/WTD; NRC approval; shareholder approval if exceeded", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 203", "Key Managerial Personnel", "Prescribed class of companies", "Appointment of MD/CEO, CS, CFO mandatory; vacancy to be filled within 6 months", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 204", "Secretarial Audit for Bigger Companies", "Listed companies and prescribed unlisted public companies", "Secretarial audit by PCS; Form MR-3; covers Companies Act, SEBI, FEMA, labour law compliance", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),
    ("Companies Act", "Section 447", "Punishment for Fraud", "Any person guilty of fraud under the Act", "Imprisonment 6 months to 10 years; fine 3x to 3x amount involved; wilful default provisions", "https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf"),

    # ── CARO 2020 — All 21 Clauses ─────────────────────────────────────────────
    ("CARO", "Clause 1", "Maintenance of Books of Accounts", "All companies", "Whether books of accounts maintained as required under Section 128; branch books", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 2", "Fixed Assets / PPE", "All companies", "Whether fixed assets properly maintained; physical verification done; discrepancies material; title deeds held", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 3", "Inventory", "All companies", "Physical verification at reasonable intervals; material discrepancies in inventory count; working capital loans", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 4", "Loans Granted", "All companies", "Terms and conditions of loans/guarantees to parties; prima facie not prejudicial to company interest", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 5", "Loans/Investments — Section 185/186", "All companies", "Compliance with Section 185 (loans to directors) and Section 186 (investments/loans limits)", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 6", "Deposits", "All companies", "Whether deposits accepted comply with RBI directions/NBFC norms; repayment defaults", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 7", "Cost Records", "Companies where cost audit applicable", "Cost records maintained as per Section 148; cost audit conducted", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 8", "Statutory Dues", "All companies", "Provident Fund, ESI, Income Tax, GST, Customs, Cess deposited regularly; disputed dues details", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 9", "Undisclosed Income / Surrendered Income", "All companies", "Whether company has disclosed/surrendered income during any income tax search; books updated", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 10", "Defaults on Loans and Borrowings", "Companies with external borrowings", "Default in repayment of loans/borrowings to banks, financial institutions, debenture holders, government", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 11", "Managerial Remuneration", "All companies paying managerial remuneration", "Whether remuneration paid/provided as per Section 197; approval obtained; excess remuneration recovery", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 12", "Related Party Transactions", "All companies", "Whether transactions with related parties comply with Section 188; audit committee approval; disclosures", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 13", "Internal Audit", "Prescribed class of companies", "Whether internal audit system commensurate with size and nature; reports considered by audit committee", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 14", "Internal Financial Controls", "All companies", "Whether company has adequate internal financial controls over financial reporting; such controls operating effectively", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 15", "Non-cash Transactions with Directors", "All companies", "Non-cash transactions with directors or persons connected with them; compliance with Section 192", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 16", "RBI Registration", "NBFCs and companies required to register under RBI Act", "Whether company required to be registered under Section 45-IA of RBI Act 1934 and if so registered", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 17", "Cash Losses", "All companies", "Whether company incurred cash losses in current and immediately preceding financial year; amounts", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 18", "Resignation of Statutory Auditor", "Companies where statutory auditor resigned", "Resignation of statutory auditors during the year; issues raised by outgoing auditor; management response", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 19", "Going Concern Doubt", "All companies", "Financial ratios, ageing/expected realisation of assets and liabilities indicate material uncertainty on going concern", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 20", "Contingent Liabilities and Public Offer", "All companies", "Pending litigations, unrecorded income/assets not disclosed; public offer/rights issue fund utilisation", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),
    ("CARO", "Clause 21", "Group CARO Qualifications", "Holding companies with subsidiaries/associates/JVs", "Qualifications or adverse remarks by respective auditors of subsidiaries/associates in their CARO reports", "https://kb.icai.org/pdfs/PDFFile66599b36998f85.21053334.pdf"),

    # ── Ind AS — Full Set ──────────────────────────────────────────────────────
    ("Ind AS", "Ind AS 1",   "Presentation of Financial Statements",                 "Listed/public company with net worth >250 Cr",             "Overall presentation, Fair presentation, Going concern, Materiality, Offsetting",                                  "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 2",   "Inventories",                                          "Ind AS compliant",                                         "Cost of inventories, NRV, FIFO/Weighted average, Write-down to NRV, Reversal",                                      "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 7",   "Statement of Cash Flows",                              "Ind AS compliant",                                         "Operating/Investing/Financing activities, Direct/Indirect method, Non-cash transactions",                            "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 8",   "Accounting Policies, Changes in Estimates and Errors", "Ind AS compliant",                                         "Selection of accounting policies, Changes in estimates, Correction of prior period errors",                         "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 10",  "Events After the Reporting Period",                    "Ind AS compliant",                                         "Adjusting and non-adjusting events, Going concern assessment, Dividends declared after reporting date",               "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 12",  "Income Taxes",                                         "Ind AS compliant",                                         "Current tax, Deferred tax, Temporary differences, DTA/DTL recognition, Uncertain tax positions",                    "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 16",  "Property, Plant and Equipment",                        "Ind AS compliant",                                         "Recognition, Cost/Revaluation model, Depreciation, Component approach, Derecognition",                              "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 19",  "Employee Benefits",                                    "Ind AS compliant",                                         "Short-term benefits, Post-employment (defined benefit/contribution), Other long-term, Termination benefits",         "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 20",  "Accounting for Government Grants",                     "Ind AS compliant entities receiving grants",               "Recognition conditions, Capital vs revenue grants, Non-monetary grants at fair value, Repayment",                   "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 21",  "The Effects of Changes in Foreign Exchange Rates",     "Ind AS compliant",                                         "Functional currency, Monetary/non-monetary items, Translation of foreign operations",                               "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 23",  "Borrowing Costs",                                      "Ind AS compliant",                                         "Capitalisation of borrowing costs on qualifying assets, Commencement/suspension/cessation",                         "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 24",  "Related Party Disclosures",                            "Ind AS compliant",                                         "Related party definition, Control/significant influence, KMP, Disclosure of transactions and balances",               "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 27",  "Separate Financial Statements",                        "Parent companies preparing separate FS",                   "Investments in subsidiaries, associates, JVs in separate FS; cost/equity/FVTPL options",                            "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 28",  "Investments in Associates and Joint Ventures",         "Companies with associates/JVs",                            "Equity method of accounting, Significant influence (20%+), Goodwill in associates, Impairment",                    "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 32",  "Financial Instruments: Presentation",                  "Ind AS compliant with financial instruments",              "Liability vs equity classification, Compound instruments, Treasury shares, Offsetting criteria",                    "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 33",  "Earnings Per Share",                                   "Listed companies",                                         "Basic EPS, Diluted EPS, Weighted average shares, Anti-dilutive instruments",                                        "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 34",  "Interim Financial Reporting",                          "Listed companies required to publish interim reports",     "Minimum content of condensed FS, Recognition/measurement in interim periods, Seasonality",                         "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 36",  "Impairment of Assets",                                 "Ind AS compliant",                                         "Indicators of impairment, Recoverable amount (VIU/FVLCS), CGU, Goodwill impairment, Reversal",                    "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 37",  "Provisions, Contingent Liabilities and Contingent Assets", "Ind AS compliant",                                    "Recognition criteria for provisions, Contingent liabilities disclosure, Contingent assets",                         "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 38",  "Intangible Assets",                                    "Ind AS compliant",                                         "Recognition criteria, Amortisation, Indefinite useful life, Internally generated intangibles (R&D split)",           "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 40",  "Investment Property",                                  "Companies holding investment properties",                   "Recognition, Cost model measurement, Fair value disclosure, Transfer to/from investment property",                  "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 41",  "Agriculture",                                          "Companies in agricultural sector",                         "Biological assets at fair value less costs to sell, Agricultural produce at point of harvest",                      "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 101", "First-time Adoption of Ind AS",                        "Companies transitioning to Ind AS",                        "Deemed cost elections, Retrospective application, Reconciliation disclosures",                                      "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 102", "Share-based Payment",                                  "Companies with ESOP/ESPP/share-based transactions",        "Equity-settled and cash-settled share-based payments, Fair value at grant date, Vesting conditions",                 "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 103", "Business Combinations",                                "Companies involved in acquisitions/mergers",               "Acquisition method, Goodwill/bargain purchase, Identifiable assets and liabilities at fair value",                  "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 105", "Non-current Assets Held for Sale and Discontinued Operations", "Ind AS compliant",                                "Classification as held for sale, Measurement at lower of carrying amount/FVLCTS, Discontinued operations",          "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 107", "Financial Instruments: Disclosures",                   "Ind AS compliant with financial instruments",              "Significance of financial instruments, Credit/liquidity/market risk disclosures, Hedge accounting disclosures",     "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 108", "Operating Segments",                                   "Listed companies",                                         "Management approach, Reportable segments, Aggregation criteria, Reconciliations",                                   "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 109", "Financial Instruments",                                "Ind AS compliant",                                         "Classification (amortised cost/FVOCI/FVTPL), ECL impairment model (3-stage), Hedge accounting",                    "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 110", "Consolidated Financial Statements",                    "Parent companies",                                         "Control definition (power+returns+link), Consolidation procedures, Non-controlling interest",                      "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 111", "Joint Arrangements",                                   "Companies in joint arrangements",                          "Joint operations vs joint ventures, Accounting: share of assets/liabilities vs equity method",                      "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 112", "Disclosure of Interests in Other Entities",            "Companies with interests in subsidiaries/associates/JVs", "Disclosures about subsidiaries, associates, JVs, unconsolidated structured entities",                               "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 113", "Fair Value Measurement",                               "Ind AS compliant",                                         "Fair value definition, Hierarchy (Level 1/2/3), Valuation techniques (market/income/cost), Disclosures",            "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 115", "Revenue from Contracts with Customers",                "Ind AS compliant",                                         "5-step model: Identify contract, Performance obligations, Transaction price, Allocate, Recognise",                  "https://www.icai.org/post/compendium-of-indian-accounting-standards"),
    ("Ind AS", "Ind AS 116", "Leases",                                               "Ind AS compliant",                                         "Right-of-use asset, Lease liability, Short-term/low-value exemptions, Variable lease payments, Lessor accounting",   "https://www.icai.org/post/compendium-of-indian-accounting-standards"),

    # ── AS — Full Set (non-Ind AS companies) ──────────────────────────────────
    ("AS", "AS 1",  "Disclosure of Accounting Policies",                              "All companies",                                            "Fundamental accounting assumptions, Significant accounting policies, Disclosure requirements",                      "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 2",  "Valuation of Inventories",                                       "All companies",                                            "Cost formulas (FIFO/Weighted average), NRV, Items to include in cost, Write-down",                                  "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 3",  "Cash Flow Statements",                                           "Companies (excluding certain small enterprises)",          "Operating/Investing/Financing activities, Direct/Indirect method, Non-cash transactions",                            "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 4",  "Contingencies and Events After Balance Sheet Date",              "All companies",                                            "Adjusting and non-adjusting events, Provisions for contingencies, Proposed dividend",                               "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 5",  "Net Profit or Loss, Prior Period Items and Changes in Accounting Policies", "All companies",                                 "Extraordinary items, Prior period adjustments, Change in accounting policy/estimate, Disclosure",                   "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 6",  "Depreciation Accounting",                                        "All companies",                                            "Useful life, Depreciation methods (SLM/WDV), Change in method, Disclosure",                                        "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 7",  "Construction Contracts",                                         "Companies with construction/long-term contracts",          "Percentage of completion method, Contract costs, Revenue recognition, Foreseeable losses",                          "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 9",  "Revenue Recognition",                                            "All companies",                                            "Revenue from sale of goods, Rendering of services, Interest/royalties/dividends recognition",                       "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 10", "Property, Plant and Equipment",                                  "All companies",                                            "Initial measurement, Subsequent costs, Depreciation, Revaluation, Derecognition",                                   "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 11", "The Effects of Changes in Foreign Exchange Rates",               "All companies with foreign currency transactions",         "Monetary/non-monetary items, Translation of foreign operations, Exchange differences",                               "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 12", "Accounting for Government Grants",                               "Companies receiving government grants",                    "Recognition conditions, Capital/revenue grants, Repayment of grants, Non-monetary grants",                          "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 13", "Accounting for Investments",                                     "All companies",                                            "Classification (current/long-term), Cost/market value, Reclassification, Disposal",                                 "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 14", "Accounting for Amalgamations",                                   "Companies involved in amalgamations/mergers",              "Pooling of interests vs Purchase method, Goodwill/capital reserve, Disclosures",                                   "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 15", "Employee Benefits",                                              "All companies",                                            "Gratuity, Leave encashment, PF/ESI, Defined benefit obligation, Actuarial valuations",                              "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 16", "Borrowing Costs",                                                "All companies",                                            "Capitalisation on qualifying assets, Commencement/suspension/cessation of capitalisation",                          "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 17", "Segment Reporting",                                              "Listed companies and companies in process of listing",     "Business/Geographic segments, Inter-segment transfers, Reconciliation to financial statements",                     "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 18", "Related Party Disclosures",                                      "All companies",                                            "Related party definition, Control/significant influence, Disclosure of transactions and balances",                   "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 19", "Leases",                                                         "All companies",                                            "Finance lease vs operating lease, Lessee/lessor accounting, Sale and leaseback transactions",                        "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 20", "Earnings Per Share",                                             "Listed companies and companies in process of listing",     "Basic EPS, Diluted EPS, Weighted average shares, Dilutive instruments",                                            "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 21", "Consolidated Financial Statements",                              "Companies with subsidiaries",                              "Control definition, Consolidation procedures, Goodwill, Minority interest, Uniform policies",                      "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 22", "Accounting for Taxes on Income",                                 "All companies",                                            "Current tax, Deferred tax, Timing differences, DTA/DTL recognition, Virtual certainty test",                        "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 23", "Accounting for Investments in Associates in Consolidated FS",    "Companies with associates",                                "Equity method, Significant influence (20%+), Goodwill in associates, Losses exceeding investment",                  "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 24", "Discontinuing Operations",                                       "Companies with discontinuing operations",                  "Definition, Initial disclosure event, Disclosure in FS, Measurement at lower of carrying amount/NRV",                "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 25", "Interim Financial Reporting",                                    "Listed companies required to publish interim reports",     "Minimum content, Condensed FS, Recognition/measurement consistent with annual FS",                                  "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 26", "Intangible Assets",                                              "All companies",                                            "Recognition criteria, Amortisation over useful life (max 10 years), Research vs development phase",                  "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 27", "Financial Reporting of Interests in Joint Ventures",             "Companies with JV interests",                              "Jointly controlled operations/assets/entities, Proportionate consolidation, Equity method option",                  "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 28", "Impairment of Assets",                                           "All companies",                                            "Indicators of impairment, Recoverable amount (NRV/VIU), CGU, Goodwill allocation, Reversal",                       "https://www.icai.org/post/accounting-standards"),
    ("AS", "AS 29", "Provisions, Contingent Liabilities and Contingent Assets",       "All companies",                                            "Recognition criteria, Best estimate, Reimbursements, Contingent liabilities/assets disclosure",                    "https://www.icai.org/post/accounting-standards"),

    # ── CAS — All 24 Cost Accounting Standards ─────────────────────────────────
    ("CAS", "CAS 1",  "Classification of Cost",                     "Companies where cost records applicable",  "Prime cost, Factory cost, Cost of production, Cost of goods sold, Cost of sales",                            "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 2",  "Capacity Determination",                     "Companies where cost records applicable",  "Installed/available/normal/actual capacity, Idle capacity cost treatment",                                  "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 3",  "Overheads",                                  "Companies where cost records applicable",  "Classification, Collection, Allocation, Apportionment and Absorption of overheads",                         "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 4",  "Cost of Production for Captive Consumption", "Companies with captive consumption",       "Determination of cost of captive consumption for customs/excise duty valuation",                            "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 5",  "Average (Equalized) Cost of Transportation", "Companies where cost records applicable",  "Treatment of transportation cost in cost statements, Equalized freight calculation",                         "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 6",  "Material Cost",                              "Companies where cost records applicable",  "Purchase cost, Freight, Duties, Insurance, Handling; CENVAT/GST treatment, Wastage",                        "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 7",  "Employee Cost",                              "Companies where cost records applicable",  "Wages, Salaries, Benefits, Overtime, VRS, Employee welfare; allocation to cost centres",                    "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 8",  "Cost of Utilities",                          "Companies where cost records applicable",  "Power, Fuel, Water and other utilities; cost per unit determination, Internal generation vs purchase",        "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 9",  "Packing Material Cost",                      "Companies where cost records applicable",  "Primary and secondary packing; packing cost treatment in cost of production vs selling cost",                 "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 10", "Direct Expenses",                            "Companies where cost records applicable",  "Expenses directly attributable to production/service, Job/process/contract specific charges",                 "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 11", "Administrative Overheads",                   "Companies where cost records applicable",  "Office and administrative expenses, Management salaries, Non-production overhead absorption",                "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 12", "Repairs and Maintenance Cost",               "Companies where cost records applicable",  "Preventive and corrective maintenance; major overhaul treatment; in-house vs contract maintenance",           "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 13", "Cost of Service Cost Centres",               "Companies where cost records applicable",  "Service department costs, Allocation/apportionment/absorption to production cost centres",                   "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 14", "Pollution Control Cost",                     "Companies with pollution control obligations", "Effluent treatment, Environment compliance costs; capital vs revenue treatment",                          "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 15", "Selling and Distribution Overheads",         "Companies where cost records applicable",  "Selling expenses, Distribution costs, Advertisement, Market development, After-sales service",              "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 16", "Depreciation and Amortization",              "Companies where cost records applicable",  "Methods in cost statements (SLM/WDV), Residual value, Revaluation impact, Fully depreciated assets",        "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 17", "Interest and Financing Charges",             "Companies where cost records applicable",  "Treatment of interest in cost statements, Notional interest on owned funds, Imputed cost of capital",       "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 18", "Research and Development Costs",             "Companies incurring R&D expenses",         "R&D costs in cost statements, Capital vs revenue R&D, Apportionment of R&D to products",                   "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 19", "Joint Costs",                                "Companies with joint/by-products",         "Allocation of joint costs to joint products; by-product cost treatment; basis of apportionment",            "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 20", "Royalty and Technical Know-how Fee",         "Companies paying royalty/technical fees",  "Treatment in cost statements, Lump-sum vs recurring payments, Foreign currency royalties",                   "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 21", "Quality Control",                            "Companies with quality control processes", "Prevention, Appraisal, Internal/external failure costs; Cost of poor quality; QC cost disclosure",          "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 22", "Manufacturing Cost",                         "Companies where cost records applicable",  "Total manufacturing cost; factory cost; works cost; cost of production statements",                        "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 23", "Selling Cost",                               "Companies where cost records applicable",  "Cost of selling activities, Pre-sale and post-sale service costs, Sales force costs",                       "https://www.icmai.in/CASB/casb-about.php"),
    ("CAS", "CAS 24", "Treatment of Revenue in Cost Statements",    "Companies where cost records applicable",  "Scrap, waste, by-product, miscellaneous income treatment; deduction from cost vs other income",             "https://www.icmai.in/CASB/casb-about.php"),

    # ── SIA — All 16 Standards on Internal Audit ──────────────────────────────
    ("SIA", "SIA 1",  "Planning an Internal Audit",              "Internal audit engagements",                         "Risk-based planning, Annual plan, Engagement plan, Resource allocation",                                      "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 2",  "Basic Principles Governing Internal Audit", "Internal audit engagements",                       "Independence, Objectivity, Professional care, Confidentiality, Competence",                                    "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 3",  "Documentation",                           "Internal audit engagements",                         "Working papers, Electronic documentation, Retention policy, Ownership of working papers",                      "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 4",  "Reporting",                               "Internal audit engagements",                         "Reporting process, Content of report, Draft report, Distribution, Timely reporting",                          "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 5",  "Sampling",                                "Internal audit engagements",                         "Statistical/non-statistical sampling, Sample design, Evaluation of results, Projection of errors",            "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 6",  "Analytical Procedures",                   "Internal audit engagements",                         "Use in planning, Substantive testing, Overall review; ratio analysis, trend analysis, reasonableness tests",  "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 7",  "Quality Assurance in Internal Audit",     "Internal audit function",                            "Internal QA reviews, External QA assessments, Quality assurance programme, Continuous improvement",          "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 8",  "Terms of Internal Audit Engagement",      "Internal audit function",                            "Engagement letter/charter, Scope, Objectives, Access rights, Reporting lines, Fees",                         "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 9",  "Communication with Management",           "Internal audit engagements",                         "Interim communication, Draft report discussion, Final report, Management responses, Follow-up",               "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 10", "Internal Audit Findings and Recommendations", "Internal audit engagements",                     "Criteria-Condition-Cause-Effect framework, Recommendations, Priority, Management action plan",               "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 11", "Consideration of Fraud in an Internal Audit", "Internal audit engagements",                     "Fraud risk factors, Red flags, Detection procedures, Reporting of suspected fraud to management/board",       "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 12", "Internal Control Evaluation",             "Internal audit engagements",                         "COSO framework, Control environment, Risk assessment, Control activities, Monitoring",                       "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 13", "Enterprise Risk Management",              "Internal audit function",                            "ERM framework, Risk appetite and tolerance, Risk identification/assessment/response strategies",             "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 14", "Internal Audit in an IT Environment",     "Internal audit in IT-dependent organisations",       "IT general controls, Application controls, ITGC review, CAAT, Data analytics",                               "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 15", "Knowledge of the Entity's Business",      "Internal audit engagements",                         "Business understanding, Industry knowledge, Operational environment, Risk profile of entity",                 "https://internalaudit.icai.org/publications/"),
    ("SIA", "SIA 16", "Using the Work of an Expert",             "Internal audit engagements requiring specialist",    "Selection of expert, Defining scope/objectives for expert, Evaluating adequacy of expert's work",            "https://internalaudit.icai.org/publications/"),

    # ── SA — Full Series ───────────────────────────────────────────────────────
    # SA 200 series — General Principles and Responsibilities
    ("SA", "SA 200", "Overall Objectives of the Independent Auditor",                  "All audit engagements",                                    "Reasonable assurance, Material misstatement, Ethical requirements, Professional scepticism",                      "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 210", "Agreeing the Terms of Audit Engagements",                        "All audit engagements",                                    "Preconditions for audit, Engagement letter content, Limitation of scope, Recurring audits",                       "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 220", "Quality Control for an Audit of Financial Statements",           "All audit engagements",                                    "Engagement partner responsibility, Independence, Supervision, Engagement quality review",                         "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 230", "Audit Documentation",                                            "All audit engagements",                                    "Working papers, Documentation of significant matters, Assembly of final audit file, Retention",                   "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 240", "The Auditor's Responsibilities Relating to Fraud",               "All audit engagements",                                    "Fraud risk assessment, Fraud risk factors, Management override, Fraudulent financial reporting",                   "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 250", "Consideration of Laws and Regulations",                          "All audit engagements",                                    "Compliance with laws/regulations, Non-compliance identification and reporting, Disclosure",                        "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 260", "Communication with Those Charged with Governance",               "All audit engagements",                                    "Significant audit findings, Independence communication, Difficult areas, Going concern",                          "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 265", "Communicating Deficiencies in Internal Control",                 "All audit engagements",                                    "Significant deficiencies vs material weaknesses, Written communication to governance",                            "https://www.icai.org/post/standards-on-auditing"),
    # SA 300 series — Risk Assessment and Response
    ("SA", "SA 300", "Planning an Audit of Financial Statements",                      "All audit engagements",                                    "Audit strategy, Audit plan, Preliminary engagement activities, Direction/supervision/review",                     "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 315", "Identifying and Assessing Risks of Material Misstatement",       "All audit engagements",                                    "Risk assessment procedures, Understanding entity/environment/ICS, Significant risks, ROMM",                       "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 320", "Materiality in Planning and Performing an Audit",                "All audit engagements",                                    "Overall materiality, Performance materiality, Clearly trivial threshold, Revision during audit",                  "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 330", "The Auditor's Responses to Assessed Risks",                      "All audit engagements",                                    "Overall responses, Substantive procedures, Tests of controls, Adequacy of presentation",                          "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 402", "Audit Considerations Relating to Service Organisations",         "Audits of entities using service organisations",           "Type 1/Type 2 SOC reports, Complementary user entity controls, Sub-service organisations",                       "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 450", "Evaluation of Misstatements Identified During the Audit",        "All audit engagements",                                    "Accumulation of misstatements, Qualitative aspects, Clearly trivial, Management adjustments",                     "https://www.icai.org/post/standards-on-auditing"),
    # SA 500 series — Audit Evidence
    ("SA", "SA 500", "Audit Evidence",                                                 "All audit engagements",                                    "Sufficiency and appropriateness, Sources of audit evidence, Management representations",                           "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 501", "Audit Evidence — Specific Considerations for Selected Items",    "All audit engagements",                                    "Physical inventory count attendance, Litigation/claims, Segment information",                                     "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 505", "External Confirmations",                                         "All audit engagements",                                    "Positive/negative confirmations, Non-responses, Unreliable responses, Restrictions by management",                "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 510", "Initial Audit Engagements — Opening Balances",                   "Initial audit engagements",                                "Opening balances, Prior period auditor, Consistency of accounting policies, Qualified opinion",                   "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 520", "Analytical Procedures",                                          "All audit engagements",                                    "Substantive analytical procedures, Expectation development, Threshold for investigation, Overall review",          "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 530", "Audit Sampling",                                                 "Audit engagements using statistical/non-statistical sampling", "Sample design, MUS, Stratification, Risk of incorrect acceptance/rejection, Projecting misstatements",         "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 540", "Auditing Accounting Estimates and Related Disclosures",          "All audit engagements",                                    "Estimation uncertainty, Management bias, Point estimate vs range, Higher uncertainty procedures",                 "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 550", "Related Parties",                                                "All audit engagements",                                    "Related party relationships, Transactions not at arm's length, Undisclosed related parties",                      "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 560", "Subsequent Events",                                              "All audit engagements",                                    "Events between reporting date and auditor's report, Facts discovered after report date",                          "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 570", "Going Concern",                                                  "All audit engagements",                                    "Going concern indicators, Management assessment, Adequacy of disclosures, Implications for auditor's report",    "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 580", "Written Representations",                                        "All audit engagements",                                    "Management representation letter, Specific written representations, Doubt on reliability",                        "https://www.icai.org/post/standards-on-auditing"),
    # SA 600 series — Using Work of Others
    ("SA", "SA 600", "Using the Work of Another Auditor",                              "Group audits with component auditors",                     "Principal auditor responsibilities, Component auditor instructions, Sufficiency of work, Reporting",               "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 610", "Using the Work of Internal Auditors",                            "Audit engagements where internal audit function exists",   "Evaluating internal audit function, Direct assistance, Objectivity and competence assessment",                     "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 620", "Using the Work of an Auditor's Expert",                          "Audit engagements requiring specialist knowledge",         "Selection, Scope and objectives for expert, Evaluating adequacy, Reference in auditor's report",                  "https://www.icai.org/post/standards-on-auditing"),
    # SA 700 series — Audit Conclusions and Reporting
    ("SA", "SA 700", "Forming an Opinion and Reporting on Financial Statements",       "All audit engagements",                                    "Unmodified opinion, Auditor's report elements, Emphasis of matter, Going concern",                                "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 701", "Communicating Key Audit Matters",                                "Audit engagements of listed entities",                     "Selection of KAMs, Description in auditor's report, Relationship with modified opinion",                          "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 705", "Modifications to the Opinion in the Independent Auditor's Report", "All audit engagements",                                  "Qualified opinion, Adverse opinion, Disclaimer of opinion, Basis for modification paragraph",                    "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 706", "Emphasis of Matter Paragraphs and Other Matter Paragraphs",      "All audit engagements",                                    "Emphasis of matter (fundamental uncertainty), Other matter paragraphs, Positioning in report",                   "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 710", "Comparative Information — Corresponding Figures and Comparative FS", "All audit engagements with comparative figures",       "Corresponding figures vs comparative FS, Prior period auditor, Restatements, Report modifications",               "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 720", "The Auditor's Responsibilities Relating to Other Information",   "All audit engagements with annual reports",                "Material inconsistencies with audited FS, Material misstatements of fact, Director's report review",               "https://www.icai.org/post/standards-on-auditing"),
    # SA 800 series — Special Purpose
    ("SA", "SA 800", "Audits of FS Prepared Under Special Purpose Frameworks",         "Special purpose audit engagements",                        "Special purpose framework assessment, Alerting paragraph, Intended users, Restriction on use",                   "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 805", "Audits of Single Financial Statements and Specific Elements",    "Special purpose audit engagements",                        "Single FS audits, Specific elements/accounts/items, Modified opinion on full FS implications",                   "https://www.icai.org/post/standards-on-auditing"),
    ("SA", "SA 810", "Engagements to Report on Summary Financial Statements",          "Engagements to report on summary FS",                      "Criteria for summary FS, Opinion on summary FS, Relationship with audited FS, Disclosures",                     "https://www.icai.org/post/standards-on-auditing"),
]


def seed_official_standards() -> int:
    """Seed standards — additive and idempotent: inserts only if (family, reference) not already present."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    inserted = 0
    for family, reference, description, applicability, clause_text, source_url in ALL_STANDARDS:
        exists = cursor.execute(
            "SELECT COUNT(*) FROM audit_standards WHERE family = ? AND reference = ?",
            (family, reference)
        ).fetchone()[0]
        if exists == 0:
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