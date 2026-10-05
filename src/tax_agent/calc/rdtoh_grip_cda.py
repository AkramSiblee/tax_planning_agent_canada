"""RDTOH / GRIP / CDA calculations. See skills/tax-calculation/SKILL.md."""
from __future__ import annotations

from dataclasses import dataclass

from .rates import RateTable


@dataclass(frozen=True)
class TaxPoolsResult:
    """Pool balances at year-end, BEFORE any dividends paid in the year (see dividends.py)."""
    non_eligible_rdtoh_addition: float
    non_eligible_rdtoh_closing: float
    eligible_rdtoh_addition: float
    eligible_rdtoh_closing: float
    grip_addition: float
    grip_available: float
    cda_addition: float
    cda_available: float
    dividend_needed_to_recover_non_eligible_rdtoh: float
    dividend_needed_to_recover_eligible_rdtoh: float


def grip_addition(*, general_rate_income: float, eligible_dividends_received: float, rates: RateTable) -> float:
    """
    Current-year GRIP addition, CRA Schedule 53 Part 1 / s.89(1) "general rate income
    pool": the general rate factor (0.72) times income taxed at the full general rate,
    plus eligible dividends received from other corporations.

    Simplification: "income taxed at the general rate" is taken as active business
    income above the SBD limit. The real formula (taxable income less SBD-eligible
    income less AAII) also reflects loss deductions and other adjustments not modelled
    here. Amalgamation / wind-up GRIP additions are not modelled.
    """
    factor = rates.federal["grip_general_rate_factor"]
    return factor * max(0.0, general_rate_income) + eligible_dividends_received


def cda_addition(*, non_taxable_capital_gains: float, life_insurance_cda_credit: float) -> float:
    """
    Current-year CDA addition under s.89(1) "capital dividend account": the non-taxable
    portion of net capital gains plus life insurance proceeds in excess of the policy's
    adjusted cost basis. Capital dividends received from other corporations also credit
    the CDA — not modelled; add them to `life_insurance_cda_credit` with a note if needed.
    """
    return non_taxable_capital_gains + life_insurance_cda_credit


def compute_tax_pools(
    *,
    part_i_investment_income: float,
    non_eligible_rdtoh_opening: float,
    eligible_rdtoh_opening: float,
    grip_opening: float,
    cda_opening: float,
    rates: RateTable,
    part_iv_to_non_eligible_rdtoh: float = 0.0,
    part_iv_to_eligible_rdtoh: float = 0.0,
    grip_current_addition: float = 0.0,
    cda_current_addition: float = 0.0,
) -> TaxPoolsResult:
    """
    Post-2018 two-pool RDTOH regime (s.129(4)):
    - Non-eligible RDTOH += 30 2/3% of Part I investment income + Part IV tax on
      non-eligible dividends received.
    - Eligible RDTOH += Part IV tax on eligible dividends received.
    GRIP and CDA add the current-year amounts from grip_addition() / cda_addition().

    Simplification: the 30 2/3% refundable portion of Part I tax is the first of the
    three "lesser of" limits in s.129(4); the taxable-income and Part I tax limits only
    bind with losses or foreign tax credits and are not modelled.
    """
    federal = rates.federal
    ne_addition = part_i_investment_income * federal["rdtoh_addition_rate"] + part_iv_to_non_eligible_rdtoh
    non_eligible_closing = non_eligible_rdtoh_opening + ne_addition
    eligible_closing = eligible_rdtoh_opening + part_iv_to_eligible_rdtoh
    refund_rate = federal["dividend_refund_rate"]

    return TaxPoolsResult(
        non_eligible_rdtoh_addition=ne_addition,
        non_eligible_rdtoh_closing=non_eligible_closing,
        eligible_rdtoh_addition=part_iv_to_eligible_rdtoh,
        eligible_rdtoh_closing=eligible_closing,
        grip_addition=grip_current_addition,
        grip_available=grip_opening + grip_current_addition,
        cda_addition=cda_current_addition,
        cda_available=cda_opening + cda_current_addition,
        dividend_needed_to_recover_non_eligible_rdtoh=non_eligible_closing / refund_rate,
        dividend_needed_to_recover_eligible_rdtoh=eligible_closing / refund_rate,
    )
