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
