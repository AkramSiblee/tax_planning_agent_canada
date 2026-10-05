"""
Dividends paid: the dividend refund and the penalty taxes on over-designated
dividends. See skills/tax-calculation/SKILL.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from tax_agent.intake.schema import DividendsPaid

from .rates import RateTable
from .rdtoh_grip_cda import TaxPoolsResult


@dataclass(frozen=True)
class DividendResult:
    eligible_paid: float
    non_eligible_paid: float
    capital_paid: float
    refund_from_eligible_rdtoh: float
    refund_from_non_eligible_rdtoh: float
    dividend_refund: float
    non_eligible_rdtoh_carryforward: float
    eligible_rdtoh_carryforward: float
    excessive_eligible_designation: float
    part_iii_1_tax: float
    grip_carryforward: float
    excessive_capital_dividend: float
    part_iii_tax: float
    cda_carryforward: float


def compute_dividend_refund(
    *,
    eligible_paid: float,
    non_eligible_paid: float,
    eligible_rdtoh: float,
    non_eligible_rdtoh: float,
    rates: RateTable,
) -> tuple[float, float]:
    """
    s.129(1)(a) dividend refund ordering (post-2018 rules), at 38 1/3% of dividends paid:
    - Eligible dividends recover ONLY eligible RDTOH.
    - Non-eligible dividends recover non-eligible RDTOH first, then any eligible RDTOH
      left after the eligible-dividend refund.

    Returns (refund_from_eligible_rdtoh, refund_from_non_eligible_rdtoh).

    Simplification: assumes dividends are paid while the corporation is a CCPC and
    ignores the s.129(1.2) anti-avoidance rule and the late-filing denial of the refund.
    """
    rate = rates.federal["dividend_refund_rate"]
    from_eligible = min(eligible_paid * rate, eligible_rdtoh)
    non_eligible_claim = non_eligible_paid * rate
    from_non_eligible = min(non_eligible_claim, non_eligible_rdtoh)
    shortfall = non_eligible_claim - from_non_eligible
    from_eligible += min(shortfall, eligible_rdtoh - from_eligible)
    return from_eligible, from_non_eligible


def excessive_eligible_designation(*, eligible_paid: float, grip_available: float) -> float:
    """
    s.89(1) "excessive eligible dividend designation" for a CCPC: eligible dividends
    designated in the year in excess of GRIP at the end of the year.

    Simplification: `grip_available` must already include the current-year addition
    (GRIP at year-end, before this year's eligible dividends reduce it next year).
    """
    return max(0.0, eligible_paid - grip_available)


def excessive_capital_dividend(*, capital_paid: float, cda_available: float) -> float:
    """
    s.184(2): the portion of a capital dividend elected under s.83(2) that exceeds the
    CDA immediately before the dividend became payable.

    Simplification: compares against year-end CDA. If a gain was realized AFTER the
    dividend was paid, the real CDA at the payment date was lower — check timing.
    """
    return max(0.0, capital_paid - cda_available)


def compute_dividends(*, paid: DividendsPaid | None, pools: TaxPoolsResult, rates: RateTable) -> DividendResult:
    """
    Applies dividends paid in the year to the year-end pools: dividend refund, Part III.1
    tax on an excessive eligible designation (20%; the extra 10% for the anti-avoidance
    case is not modelled), and Part III tax on an excessive capital dividend (60%). Both
    penalty taxes are usually avoidable by filing the s.185.1(2) / s.184(3) elections to
    treat the excess as an ordinary taxable dividend — this function reports the tax
    that applies if NO election is made, so the report can flag the exposure.
    """
    paid = paid or DividendsPaid()
    from_eligible, from_non_eligible = compute_dividend_refund(
        eligible_paid=paid.eligible,
        non_eligible_paid=paid.non_eligible,
        eligible_rdtoh=pools.eligible_rdtoh_closing,
        non_eligible_rdtoh=pools.non_eligible_rdtoh_closing,
        rates=rates,
    )
    eedd = excessive_eligible_designation(eligible_paid=paid.eligible, grip_available=pools.grip_available)
    excess_cd = excessive_capital_dividend(capital_paid=paid.capital, cda_available=pools.cda_available)

    return DividendResult(
        eligible_paid=paid.eligible,
        non_eligible_paid=paid.non_eligible,
        capital_paid=paid.capital,
        refund_from_eligible_rdtoh=from_eligible,
        refund_from_non_eligible_rdtoh=from_non_eligible,
        dividend_refund=from_eligible + from_non_eligible,
        non_eligible_rdtoh_carryforward=pools.non_eligible_rdtoh_closing - from_non_eligible,
        eligible_rdtoh_carryforward=pools.eligible_rdtoh_closing - from_eligible,
        excessive_eligible_designation=eedd,
        part_iii_1_tax=eedd * rates.federal["part_iii_1_rate"],
        grip_carryforward=max(0.0, pools.grip_available - paid.eligible),
        excessive_capital_dividend=excess_cd,
        part_iii_tax=excess_cd * rates.federal["part_iii_rate"],
        cda_carryforward=max(0.0, pools.cda_available - paid.capital),
    )
