"""Industry Filter — control which pages/modules are visible per industry profile.

Principle 5: Industry-Agnostic Core. Only YAML profiles control which modules
are active. The same codebase serves Manufacturing, IT Services, Healthcare,
Retail, and Financial Services.
"""
from pathlib import Path
import yaml

_PROFILE_DIR = Path("config/industry_profiles")
_CURRENT_PROFILE_FILE = Path("data/current_profile.txt")


def _current_profile_path() -> Path:
    return _CURRENT_PROFILE_FILE


def get_current_profile_name() -> str:
    """Return the currently selected industry profile name."""
    if _CURRENT_PROFILE_FILE.exists():
        return _CURRENT_PROFILE_FILE.read_text(encoding="utf-8").strip()
    return "manufacturing_fmcg"


def set_current_profile_name(name: str):
    """Persist the selected industry profile name."""
    _CURRENT_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CURRENT_PROFILE_FILE.write_text(name, encoding="utf-8")


def get_disabled_modules(profile_name: str = None) -> list:
    """Return list of disabled module IDs for a profile."""
    if profile_name is None:
        profile_name = get_current_profile_name()
    p = _PROFILE_DIR / f"{profile_name}.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data.get("modules_disabled", [])


def is_page_enabled(page_module: str, profile_name: str = None) -> bool:
    """Check if a page module is enabled for the current/specified profile.

    page_module should match the modules_disabled values in the YAML,
    e.g. "inventory_anomaly", "contract_management", etc.
    """
    return page_module not in get_disabled_modules(profile_name)


def get_page_module_map() -> dict:
    """Map page filenames to module IDs for filtering."""
    return {
        "inventory_anomaly": "pages/inventory_anomaly.py",
        "contract_management": "pages/contract_management_auditor.py",
        "payroll_audit": "pages/payroll_audit.py",
        "sales_revenue_auditor": "pages/sales_revenue_auditor.py",
    }
