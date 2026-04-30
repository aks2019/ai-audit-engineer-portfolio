"""Compliance Calendar Loader — reads config/compliance_calendar.yaml.

Principle 2: Zero Hardcoded Compliance Dates. All GST due dates, TDS rates,
PF/ESI percentages, LD rates live in the YAML. Edit the YAML when government
changes law — no code change needed.
"""
from pathlib import Path
import yaml

_CONFIG_PATH = Path("config/compliance_calendar.yaml")


def load_compliance_calendar() -> dict:
    """Load the full compliance calendar YAML into a dict."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Compliance calendar not found at {_CONFIG_PATH}")
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))


def get_tds_rate(section: str, payee_type: str = "individual") -> float:
    """Return TDS rate % for a given section and payee type."""
    cal = load_compliance_calendar()
    sec = cal.get("tds", {}).get("sections", {}).get(section, {})
    if payee_type == "company" and "rate_company" in sec:
        return sec["rate_company"]
    return sec.get("rate", sec.get("rate_individual", 0.0))


def get_tds_threshold(section: str) -> float:
    """Return TDS single-payment threshold for a section."""
    cal = load_compliance_calendar()
    sec = cal.get("tds", {}).get("sections", {}).get(section, {})
    return sec.get("threshold", sec.get("single_threshold", 0.0))


def get_pf_esi_rates() -> dict:
    """Return PF and ESI employee/employer rates and ceilings."""
    cal = load_compliance_calendar()
    return {
        "pf_employee_rate": cal["pf"]["employee_rate"],
        "pf_employer_rate": cal["pf"]["employer_rate"],
        "pf_wage_ceiling": cal["pf"]["wage_ceiling"],
        "esi_employee_rate": cal["esi"]["employee_rate"],
        "esi_employer_rate": cal["esi"]["employer_rate"],
        "esi_wage_ceiling": cal["esi"]["wage_ceiling"],
    }


def get_gst_due_day(return_type: str) -> int:
    """Return due day of following month for a GST return type."""
    cal = load_compliance_calendar()
    entry = cal.get("gst", {}).get(return_type, {})
    return entry.get("due_day_of_following_month", 0)


def get_depreciation_rate(asset_class: str) -> float:
    """Return Companies Act depreciation rate % for an asset class."""
    cal = load_compliance_calendar()
    rates = cal.get("fixed_assets", {}).get("depreciation_rates", {})
    return rates.get(asset_class, 0.0)


def get_expense_policy() -> dict:
    """Return expense policy limits from compliance calendar."""
    cal = load_compliance_calendar()
    return cal.get("expense_policy", {})


def get_industry_profile(profile_name: str = "manufacturing_fmcg") -> dict:
    """Load an industry profile YAML from config/industry_profiles/."""
    p = Path(f"config/industry_profiles/{profile_name}.yaml")
    if not p.exists():
        raise FileNotFoundError(f"Industry profile not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))
