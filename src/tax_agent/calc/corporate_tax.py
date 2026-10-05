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
    refundable_itc_refund: float  # refundable SR&ED ITC paid out in cash (s.127.1)
    refundable_provincial_refund: float  # refundable provincial credit paid out in cash
    unused_credits: float  # non-refundable excess over Part I tax — carried forward, not modelled
    part_i_tax_after_credits: float


def apply_credits_to_part_i(
    *,
    part_i_tax: float,
    sred_itc: float,
    sred_itc_refundable: float,
    provincial_credit: float,
    provincial_credit_refundable: float = 0.0,
) -> CreditsResult:
    """
    Investment tax credits (s.127(5)) and provincial tax credits reduce Part I tax only —
    never Part IV, Part III.1 or Part III tax — and cannot take Part I tax below zero.

    Ordering: the non-refundable credits (each credit less its refundable portion) are
    applied first, because any excess only carries forward. The refundable portions then
    reduce what Part I tax remains — SR&ED first, then provincial — and the rest of each
    is paid out in cash (s.127.1 for the SR&ED ITC); cash refunds improve the year-end
    position. The SR&ED-before-provincial order only affects how the cash is labelled,
    not the total.

    Simplifications:
    - Part I tax here is the combined federal + provincial figure, so the SR&ED ITC
      (federal only) and the provincial credit (provincial only) are both applied against
      the combined amount rather than each against its own government's tax.
    - The refundable split of the provincial credit is an intake input; whether a given
      provincial program is refundable is not looked up.
    - Non-refundable excess is reported as `unused_credits` (carried forward, 20 years for
      ITCs) and does NOT improve the year-end position.
    """
    if not 0 <= sred_itc_refundable <= sred_itc:
        raise ValueError(
            f"Refundable SR&ED ITC portion ({sred_itc_refundable:,.2f}) must be between 0 and "
            f"the total SR&ED ITC ({sred_itc:,.2f})."
        )
    if not 0 <= provincial_credit_refundable <= provincial_credit:
        raise ValueError(
            f"Refundable provincial credit portion ({provincial_credit_refundable:,.2f}) must be "
            f"between 0 and the total provincial credit ({provincial_credit:,.2f})."
        )
    tax_room = max(0.0, part_i_tax)
    non_refundable = (sred_itc - sred_itc_refundable) + (provincial_credit - provincial_credit_refundable)
    non_refundable_applied = min(non_refundable, tax_room)
    tax_room -= non_refundable_applied
    sred_refundable_applied = min(sred_itc_refundable, tax_room)
    tax_room -= sred_refundable_applied
    provincial_refundable_applied = min(provincial_credit_refundable, tax_room)
    applied = non_refundable_applied + sred_refundable_applied + provincial_refundable_applied
    return CreditsResult(
        credits_claimed=sred_itc + provincial_credit,
        credits_applied=applied,
        refundable_itc_refund=sred_itc_refundable - sred_refundable_applied,
        refundable_provincial_refund=provincial_credit_refundable - provincial_refundable_applied,
        unused_credits=non_refundable - non_refundable_applied,
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
