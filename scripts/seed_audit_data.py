import sqlite3
from utils.audit_db import init_audit_db, add_engagement, add_entity, add_standard

def seed_database():
    print("Initializing database...")
    init_audit_db()
    
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    
    # 1. Create a Default Engagement
    print("Seeding default engagement...")
    eng_id = add_engagement(
        "Annual Statutory Audit 2024-25", 
        "Comprehensive audit of financial and operational controls for the fiscal year."
    )
    
    # 2. Create Entities within that Engagement
    print("Seeding default entities...")
    add_entity(eng_id, "Emami Agrotech Limited (HQ)", "Kolkata", "HQ01")
    add_entity(eng_id, "Manufacturing Plant - Unit 1", "Guwahati", "PLT01")

    # 3. Seed Standards Registry
    print("Seeding standards registry...")
    standards = [
        ("Ind AS", "Ind AS 115", "Revenue from Contracts with Customers", "All listed companies"),
        ("Companies Act", "Section 135", "Corporate Social Responsibility compliance", "Company size thresholds"),
        ("Companies Act", "CARO 2020", "Companies (Auditor's Report) Order guidance", "Applicable to specific company types"),
        ("Internal Audit Standards", "SIA - Standard 1", "Planning and Risk Assessment", "All internal audits"),
        ("GST", "CGST Act", "Goods and Services Tax compliance", "Registered taxpayers"),
    ]
    
    for family, ref, desc, app in standards:
        add_standard(family, ref, desc, app)

    print("✅ Database seeding completed successfully!")
    conn.close()

if __name__ == "__main__":
    seed_database()