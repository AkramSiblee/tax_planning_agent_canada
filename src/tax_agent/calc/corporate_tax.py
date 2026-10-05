"""Corporate income tax calculation. See skills/tax-calculation/SKILL.md."""
from __future__ import annotations

from dataclasses import dataclass

from .rates import ProvinceRates, RateTable
from .sbd import SBDResult


@dataclass(frozen=True)
class CorporateTaxResult:
    tax_on_sbd_income: float
    tax_on_general_income: float
    tax_on_investment_income: float
    total_tax_before_credits: float
    investment_income_rate_used: float


@dataclass(frozen=True)
class CreditsResult:
    credits_claimed: float  # SR&ED ITC + provincial credit, as entered
    credits_applied: float  # amount that actually reduced Part I tax
    unused_credits: float  # excess over Part I tax — refundable or carried forward, not modelled
    part_i_tax_after_credits: float


def apply_credits_to_part_i(*, part_i_tax: float, sred_itc: float, provincial_credit: float) -> CreditsResult:
    """
    Investment tax credits (s.127(5)) and provincial tax credits reduce Part I tax only —
    never Part IV, Part III.1 or Part III tax — and cannot take Part I tax below zero.

    Simplifications:
    - Part I tax here is the combined federal + provincial figure, so the SR&ED ITC
      (federal only) and the provincial credit (provincial only) are both applied against
      the combined amount rather than each against its own government's tax.
    - Credits in excess of Part I tax are reported as `unused_credits` and do NOT improve
      the year-end position. Part may be refundable (e.g., the 35% enhanced SR&ED ITC for
      a CCPC under s.127.1, or a refundable provincial credit) and the rest carries forward;
      the intake does not split refundable from non-refundable amounts.
    """
    claimed = sred_itc + provincial_credit
    applied = min(claimed, max(0.0, part_i_tax))
    return CreditsResult(
        credits_claimed=claimed,
        credits_applied=applied,
        unused_credits=claimed - applied,
        part_i_tax_after_credits=part_i_tax - applied,
    )


def compute_corporate_tax(
    *,
    sbd: SBDResult,
    aaii: float,
    province: ProvinceRates,
    rates: RateTable,
) -> CorporateTaxResult:
    """
    Applies three rates to three income streams. The investment-income rate is an
    approximation (general rate + a fixed federal add-on) — see
    skills/tax-calculation/SKILL.md before treating it as exact.
    """
    investment_rate = province.general_rate_combined + rates.federal["investment_income_addon"]

    tax_sbd = sbd.abi_at_sbd_rate * province.small_business_rate_combined
    tax_general = sbd.abi_at_general_rate * province.general_rate_combined
    tax_investment = aaii * investment_rate

    return CorporateTaxResult(
        tax_on_sbd_income=tax_sbd,
        tax_on_general_income=tax_general,
        tax_on_investment_income=tax_investment,
        total_tax_before_credits=tax_sbd + tax_general + tax_investment,
        investment_income_rate_used=investment_rate,
    )
