# 🚨 How to Read the AI Vendor Payment Anomaly Detector

**Live App:** https://aiauditengineer.streamlit.app

This short guide helps any user (auditor, finance manager, or recruiter) quickly understand the dashboard and **catch real anomalies** from any uploaded SAP / Caseware IDEA file.

---

### 1. Start – Upload Your File
- Drag & drop your **vendor payments CSV or Excel** file.
- The app instantly loads all transactions (example: 10,000 rows).
- You will see 3 big metric cards at the top.

**Tip:** Always upload the **processed file** (`vendor_payments_processed.csv`) if you ran training locally — it gives the most accurate risk numbers.

---

### 2. Understand the 3 Key Metrics (Top of Dashboard)
| Metric              | What it means                                      | How to use it                              |
|---------------------|----------------------------------------------------|--------------------------------------------|
| Total Transactions  | All payments in your file                          | Baseline number                            |
| High-Risk Flagged   | How many payments the AI marked as suspicious      | **Focus your audit here** (usually 5%)     |
| Risk %              | Percentage of risky payments                       | If >5% → immediate attention needed        |

**Red flag rule:** If High-Risk Flagged > 5% or Risk % > 5%, start reviewing the table immediately.

---

### 3. Chart 1: "Top 20 Highest Payments" (Bar Chart)
- **X-axis:** Vendor names
- **Y-axis:** Payment Amount (₹)
- **Colour intensity:** Higher payments are darker blue

**How to catch anomalies here:**
- Look for **very tall bars** — these are unusually large payments.
- Hover on a bar → see the exact amount.
- **Action:** Any bar > ₹1 Cr or much taller than others = potential anomaly (especially if the vendor appears multiple times).

---

### 4. Chart 2: "Payment Scatter Plot"
- **X-axis:** Payment Amount (₹)
- **Y-axis:** Anomaly Probability (0.0 to 1.0)
- Dots = individual transactions
- Colour = vendor (different vendors get different colours)

**How to catch anomalies here:**
- Dots **high up** (close to 1.0) = high probability of anomaly
- Dots **far right + high up** = very large + very suspicious → **highest priority**
- Cluster of dots in top-right corner = systematic issue with certain vendors

**Quick rule:** Any dot above 0.9 anomaly probability = investigate immediately.

---

### 5. Transactions Table (Bottom)
This is your **audit working list**.

**Key columns to focus on:**
- `amount` → actual payment value
- `anomaly_score` → 1 = flagged by AI
- `anomaly_probability` → 0.0–1.0 (higher = more risky)
- `risk_explanation` → plain English reason (e.g., "amount is 341.5× historical average")
- `related_party` / `overdue_risk_score` → extra red flags

**How to use the table:**
1. Sort by `anomaly_probability` (highest first)
2. Read the `risk_explanation` column — this is exactly what you write in audit reports
3. Filter in Excel after download for related-party or high overdue

---

### 6. Practical Audit Tips – How to Catch Real Anomalies
- **Related-party + high amount** → classic fraud/red-flag
- **Amount 3× or more than historical average** → sudden spike
- **Payments just below approval limit** → splitting trick
- **High overdue + high amount** → cash flow risk
- Download the filtered CSV and share with your team/manager

---

### 7. Next Steps After Analysis
- Download the filtered file using the button
- Add your own comments in Excel
- Present the 3 metrics + top 5 flagged items to your manager
- Share the live link with colleagues: https://aiauditengineer.streamlit.app

---

**Made by Ashok Sharma**  
SAP FICO Auditor (17+ years)  
GitHub: AI-Audit-Engineer-Portfolio

---

**You can now add this file to your repo** and link it from LinkedIn or your slides.  
It makes your tool even more professional and easy for anyone to use.

Would you like me to:
- Add this as a new page inside the Streamlit app itself?
- Write a shorter 1-page version for your 5-slide deck?
- Give you the Week 5 prompt (FastAPI backend + email alerts)?

Just say the word and we continue! 🚀