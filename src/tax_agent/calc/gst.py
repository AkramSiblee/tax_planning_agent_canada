"""GST/HST calculations. See skills/tax-calculation/SKILL.md."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GstResult:
    gst_collected: float
    total_itcs: float
    net_tax: float
    instalments_likely_required: bool


def compute_gst(
    *,
    taxable_supplies: float,
    gst_hst_rate: float,
    total_itcs: float,
    instalment_threshold: float = 3000,
) -> GstResult:
    """
    Net tax = GST/HST collected on taxable supplies minus total input tax credits.
    ITC restrictions (e.g., the 50% cap on meals & entertainment, the passenger-vehicle
    ITC cap) are applied by the caller when building `total_itcs` from the intake —
    this function does not re-derive them.
    """
    collected = taxable_supplies * gst_hst_rate
    net_tax = collected - total_itcs
    return GstResult(
        gst_collected=collected,
        total_itcs=total_itcs,
        net_tax=net_tax,
        instalments_likely_required=net_tax > instalment_threshold,
    )
