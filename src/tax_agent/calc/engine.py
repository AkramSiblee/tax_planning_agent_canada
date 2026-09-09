"""
Top-level orchestrator: takes a validated intake and produces the complete
CalculationResults object every other part of the agent (report, JSON export) consumes.

This is the ONLY place that should call every calc submodule in sequence — individual
submodules (sbd.py, corporate_tax.py, etc.) never call each other directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from tax_agent.intake.schema import Intake

from .corporate_tax import CorporateTaxResult, compute_corporate_tax
from .gst import GstResult, compute_gst
from .payroll import PayrollResult, compute_payroll
from .rates import RateTable, load_rates
from .rdtoh_grip_cda import TaxPoolsResult, compute_tax_pools
from .sbd import SBDResult, compute_entity_sbd_limit


@dataclass(frozen=True)
class CalculationResults:
    tax_year: int
    entity_name: str
    province: str
    sbd: SBDResult
    corporate_tax: CorporateTaxResult
    tax_pools: TaxPoolsResult
    payroll: PayrollResult
    gst: GstResult
    net_income_before_tax: float
    net_corporate_tax_after_credits: float
    estimated_year_end_position: float  # positive = refund, negative = balance owing
    instalments_required_next_year: bool
    flags: list[str] = field(default_factory=list)


def run_calculation(intake: Intake, tax_year: int) -> CalculationResults:
    rates: RateTable = load_rates(tax_year)
    province = rates.province(intake.province)

    sbd = compute_entity_sbd_limit(
        active_business_income=intake.net_active_business_income,
        aaii=intake.aggregate_investment_income,
        group_taxable_capital=intake.group_taxable_capital,
        schedule_23_allocation=intake.schedule_23_allocation,
        rates=rates,
    )
    corp_tax = compute_corporate_tax(
        sbd=sbd, aaii=intake.aggregate_investment_income, province=province, rates=rates,
    )
    tax_pools = compute_tax_pools(
        aaii=intake.aggregate_investment_income,
        non_eligible_rdtoh_opening=intake.non_eligible_rdtoh_opening,
        eligible_rdtoh_opening=intake.eligible_rdtoh_opening,
        grip_opening=intake.grip_opening,
        cda_opening=intake.cda_opening,
        rates=rates,
    )
    payroll = compute_payroll(
        total_salaries=intake.total_salaries,
        employee_cpp_total=intake.employee_cpp_total,
        employee_cpp2_total=intake.employee_cpp2_total,
        employee_ei_total=intake.employee_ei_total,
        wcb_assessable_payroll=intake.wcb_assessable_payroll,
        wcb_premium_rate_per_100=intake.wcb_premium_rate_per_100,
        rates=rates,
    )
    gst = compute_gst(
        taxable_supplies=intake.taxable_supplies,
        gst_hst_rate=province.gst_hst_rate,
        total_itcs=intake.total_itcs,
        instalment_threshold=rates.federal["instalment_threshold"],
    )

    net_after_credits = (
        corp_tax.total_tax_before_credits - intake.sred_itc - intake.provincial_credit
    )
    year_end_position = intake.instalments_paid - net_after_credits

    instalments_required_next_year = (
        corp_tax.total_tax_before_credits > rates.federal["instalment_threshold"]
    )

    flags: list[str] = []
    if sbd.is_grinding:
        flags.append(
            f"Passive income is grinding the SBD limit by ${sbd.passive_grind:,.2f}."
        )
    if intake.tosi_risk_shareholders:
        names = ", ".join(intake.tosi_risk_shareholders)
        flags.append(f"TOSI risk flagged for: {names}.")
    if tax_pools.cda_available > 0:
        flags.append(
            f"${tax_pools.cda_available:,.2f} Capital Dividend Account balance is unused."
        )
    if instalments_required_next_year:
        flags.append("Instalments will likely be required again next year.")

    return CalculationResults(
        tax_year=tax_year,
        entity_name=intake.entity_name,
        province=intake.province,
        sbd=sbd,
        corporate_tax=corp_tax,
        tax_pools=tax_pools,
        payroll=payroll,
        gst=gst,
        net_income_before_tax=intake.net_income_before_tax,
        net_corporate_tax_after_credits=net_after_credits,
        estimated_year_end_position=year_end_position,
        instalments_required_next_year=instalments_required_next_year,
        flags=flags,
    )
