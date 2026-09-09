"""
Structured intake data. This is the contract between excel_reader.py (which populates
it from the workbook) and calc/engine.py (which consumes it) — neither side should
reach around this dataclass to read the workbook or write results directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class MissingIntakeDataError(ValueError):
    """Raised when a required field could not be found in the intake workbook."""


@dataclass
class Intake:
    # --- Entity Setup ---
    entity_name: str
    province: str
    tax_year: int
    is_associated: bool

    # --- Income Statement ---
    net_active_business_income: float
    aggregate_investment_income: float
    net_income_before_tax: float

    # --- Balance Sheet / Associated Corporations ---
    group_taxable_capital: float
    schedule_23_allocation: float | None  # None if not associated

    # --- Prior-Year Tax Attributes ---
    non_eligible_rdtoh_opening: float
    eligible_rdtoh_opening: float
    grip_opening: float
    cda_opening: float

    # --- Payroll Register ---
    total_salaries: float
    employee_cpp_total: float
    employee_cpp2_total: float
    employee_ei_total: float
    wcb_assessable_payroll: float
    wcb_premium_rate_per_100: float

    # --- GST-HST ---
    taxable_supplies: float
    total_itcs: float

    # --- Instalments & Compliance ---
    instalments_paid: float

    # --- Credits & Incentives ---
    sred_itc: float
    provincial_credit: float

    # --- Shareholders & TOSI ---
    tosi_risk_shareholders: list[str] = field(default_factory=list)

    # --- Optional override for the passive-income grind's known simplification ---
    # (see skills/intake-collection/SKILL.md) — if the real prior-year AAII is known,
    # set it here; otherwise the engine uses the current year's AAII as a proxy.
    prior_year_aaii_override: float | None = None
