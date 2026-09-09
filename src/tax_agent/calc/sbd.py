"""
Small Business Deduction calculations. See skills/tax-calculation/SKILL.md for the
real-world rule each function implements and its simplifications.
"""
from __future__ import annotations

from dataclasses import dataclass

from .rates import RateTable


def passive_income_grind(aaii: float, federal: dict) -> float:
    """
    Reduction to the $500K federal SBD limit from aggregate investment income (AAII).
    $5 of reduction for every $1 of AAII over the grind-start threshold, capped at the
    full base limit (i.e., fully eliminated once AAII reaches the grind-end threshold).

    Simplification: AAII here should technically be the *prior* year's figure per CRA
    rules. This function takes whatever AAII value it is given — callers are
    responsible for supplying the correct year (see calc/engine.py).
    """
    start = federal["passive_income_grind_start"]
    base_limit = federal["sbd_base_limit"]
    reduction = max(0.0, (aaii - start) * 5)
    return min(base_limit, reduction)


def taxable_capital_grind(taxable_capital: float, federal: dict) -> float:
    """
    Reduction to the $500K federal SBD limit once the associated group's taxable
    capital employed in Canada exceeds the grind-start threshold ($10M), fully
    eliminated at the grind-end threshold ($50M).
    """
    start = federal["taxable_capital_grind_start"]
    end = federal["taxable_capital_grind_end"]
    base_limit = federal["sbd_base_limit"]
    span = end - start
    reduction = max(0.0, (taxable_capital - start) / span * base_limit)
    return min(base_limit, reduction)


@dataclass(frozen=True)
class SBDResult:
    passive_grind: float
    taxcap_grind: float
    federal_limit_after_grinds: float
    entity_limit: float
    abi_at_sbd_rate: float
    abi_at_general_rate: float
    is_grinding: bool


def compute_entity_sbd_limit(
    *,
    active_business_income: float,
    aaii: float,
    group_taxable_capital: float,
    schedule_23_allocation: float | None,
    rates: RateTable,
) -> SBDResult:
    """
    Full SBD determination for one entity.

    `schedule_23_allocation` is this entity's share of the group's $500K limit under
    an associated-corporation allocation agreement. Pass None if the corporation is not
    associated with any other corporation (the full grind-adjusted federal limit then
    applies with no further reduction).
    """
    federal = rates.federal
    p_grind = passive_income_grind(aaii, federal)
    c_grind = taxable_capital_grind(group_taxable_capital, federal)
    federal_limit_after_grinds = max(0.0, federal["sbd_base_limit"] - max(p_grind, c_grind))

    if schedule_23_allocation is not None:
        entity_limit = min(federal_limit_after_grinds, schedule_23_allocation)
    else:
        entity_limit = federal_limit_after_grinds

    abi_at_sbd_rate = min(active_business_income, entity_limit)
    abi_at_general_rate = max(0.0, active_business_income - entity_limit)

    return SBDResult(
        passive_grind=p_grind,
        taxcap_grind=c_grind,
        federal_limit_after_grinds=federal_limit_after_grinds,
        entity_limit=entity_limit,
        abi_at_sbd_rate=abi_at_sbd_rate,
        abi_at_general_rate=abi_at_general_rate,
        is_grinding=p_grind > 0,
    )
