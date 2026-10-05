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
class InvestmentIncomeDetail:
    """
    Investment income split by type — needed whenever the corporation receives dividends,
    realizes capital gains, or pays dividends out (typically a holdco). When this is
    supplied, it replaces `Intake.aggregate_investment_income` for every calculation.
    """
    interest_and_rents: float = 0.0  # interest, net passive rents, other property income
    taxable_capital_gains: float = 0.0  # the taxable portion only (net of the inclusion rate)
    eligible_portfolio_dividends: float = 0.0  # from non-connected corporations
    non_eligible_portfolio_dividends: float = 0.0
    connected_eligible_dividends: float = 0.0  # from connected corporations (>10% votes & value, or controlled)
    connected_non_eligible_dividends: float = 0.0
    # Part IV on connected dividends = this corp's share of the payer's dividend refund,
    # split by which of the PAYER's RDTOH pools the refund came from (payer's Schedule 3).
    connected_part_iv_from_payer_eligible_rdtoh: float = 0.0
    connected_part_iv_from_payer_non_eligible_rdtoh: float = 0.0
    life_insurance_cda_credit: float = 0.0  # death benefit in excess of the policy's ACB


@dataclass
class DividendsPaid:
    """Dividends the corporation paid to its own shareholders during the tax year."""
    eligible: float = 0.0
    non_eligible: float = 0.0
    capital: float = 0.0  # paid under a s.83(2) capital dividend election


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

    # --- Investment-income detail and dividends paid (holdco scenarios) ---
    # Both optional: when None, the engine falls back to the single
    # `aggregate_investment_income` figure and assumes no dividends were paid.
    investment_detail: InvestmentIncomeDetail | None = None
    dividends_paid: DividendsPaid | None = None
