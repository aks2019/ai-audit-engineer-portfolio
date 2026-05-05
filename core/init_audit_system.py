"""SARVAGYA Audit OS - System Initialization Script.

Run this once to initialize all database tables and seed standards data.
Usage: python core/init_audit_system.py
"""
import sys
sys.path.insert(0, '.')

from utils.audit_db import init_audit_db
from core.evidence import init_evidence_tables
from core.audit_program import init_audit_program_tables, seed_standard_checklists
from core.standards_registry import seed_official_standards


def initialize_audit_system():
    """Initialize complete audit OS."""
    print("Initializing SARVAGYA Audit Operating System...")

    print("\n[1/5] Initializing core audit database tables...")
    init_audit_db()
    print("[OK] Core tables created")

    print("\n[2/5] Initializing evidence management tables...")
    init_evidence_tables()
    print("[OK] Evidence tables created")

    print("\n[3/5] Initializing audit program tables...")
    init_audit_program_tables()
    print("[OK] Audit program tables created")

    print("\n[4/5] Seeding official audit standards (MCA, ICAI, ICMAI)...")
    count = seed_official_standards()
    print(f"[OK] Seeded {count} official standards")

    print("\n[5/5] Seeding CARO/Ind AS checklists...")
    seed_standard_checklists()
    print("[OK] Standard checklists created")

    print("\n" + "="*50)
    print("SARVAGYA Audit OS initialization complete!")
    print("="*50)
    print("\nNext steps:")
    print("  1. Start Streamlit: streamlit run app.py")
    print("  2. Go to 'Audit Planning Engine' to create an engagement")
    print("  3. Add entities and standards to the engagement")
    print("  4. Use 'Financial Statement Auditor' for deterministic checks")
    print("  5. Use 'SAP Review' if you have SAP data packs")


if __name__ == "__main__":
    initialize_audit_system()