"""RDTOH / GRIP / CDA calculations. See skills/tax-calculation/SKILL.md."""
from __future__ import annotations

from dataclasses import dataclass

from .rates import RateTable


@dataclass(frozen=True)
class TaxPoolsResult:
    non_eligible_rdtoh_addition: float
    non_eligible_rdtoh_closing: float
    eligible_rdtoh_closing: float
    grip_available: float
    cda_available: float
    dividend_needed_to_recover_non_eligible_rdtoh: float
    dividend_needed_to_recover_eligible_rdtoh: float


def compute_tax_pools(
    *,
    aaii: float,
    non_eligible_rdtoh_opening: float,
    eligible_rdtoh_opening: float,
    grip_opening: float,
    cda_opening: float,
    rates: RateTable,
) -> TaxPoolsResult:
    """
    v1 does not calculate a current-year addition to GRIP or CDA (e.g., the
    non-taxable half of a capital gain flowing into CDA) — both are passed through
    as opening balances only. See skills/tax-calculation/SKILL.md before adding that;
    it should be a new function, not a patch here.
    """
    federal = rates.federal
    addition = aaii * federal["rdtoh_addition_rate"]
    non_eligible_closing = non_eligible_rdtoh_opening + addition
    refund_rate = federal["dividend_refund_rate"]

    return TaxPoolsResult(
        non_eligible_rdtoh_addition=addition,
        non_eligible_rdtoh_closing=non_eligible_closing,
        eligible_rdtoh_closing=eligible_rdtoh_opening,
        grip_available=grip_opening,
        cda_available=cda_opening,
        dividend_needed_to_recover_non_eligible_rdtoh=non_eligible_closing / refund_rate,
        dividend_needed_to_recover_eligible_rdtoh=eligible_rdtoh_opening / refund_rate,
    )
