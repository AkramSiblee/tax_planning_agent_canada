"""
Top-level orchestrator: takes a validated intake and produces the complete
CalculationResults object every other part of the agent (report, JSON export) consumes.

This is the ONLY place that should call every calc submodule in sequence — individual
submodules (sbd.py, corporate_tax.py, etc.) never call each other directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from tax_agent.intake.schema import Intake

from .corporate_tax import (
    CorporateTaxResult,
    CreditsResult,
    apply_credits_to_part_i,
    compute_corporate_tax,
)
from .dividends import DividendResult, compute_dividends
from .gst import GstResult, compute_gst
from .investment_income import InvestmentIncomeResult, classify_investment_income
from .payroll import PayrollResult, compute_payroll
from .rates import RateTable, load_rates
from .rdtoh_grip_cda import TaxPoolsResult, cda_addition, compute_tax_pools, grip_addition
from .sbd import SBDResult, compute_entity_sbd_limit


@dataclass(frozen=True)
class CalculationResults:
    tax_year: int
    entity_name: str
    province: str
    sbd: SBDResult
    investment_income: InvestmentIncomeResult
    corporate_tax: CorporateTaxResult
    credits: CreditsResult
    tax_pools: TaxPoolsResult
    dividends: DividendResult
    payroll: PayrollResult
    gst: GstResult
    net_income_before_tax: float
    total_tax_payable_before_refund: float  # Part I + Part IV + Part III.1 + Part III
    net_corporate_tax_after_credits: float  # after the dividend refund and credits
    estimated_year_end_position: float  # positive = refund, negative = balance owing
    instalments_required_next_year: bool
    flags: list[str] = field(default_factory=list)


def run_calculation(intake: Intake, tax_year: int) -> CalculationResults:
    rates: RateTable = load_rates(tax_year)
    province = rates.province(intake.province)

    investment = classify_investment_income(
        aggregate_investment_income=intake.aggregate_investment_income,
        detail=intake.investment_detail,
        rates=rates,
    )
    # The grind is legally based on the PRIOR year's adjusted AAII (s.125(5.1)(b)); the
    # current year's figure is only a proxy when the prior-year figure isn't supplied.
    grind_aaii = (
        intake.prior_year_aaii_override
        if intake.prior_year_aaii_override is not None
        else investment.adjusted_aaii_for_grind
    )

    sbd = compute_entity_sbd_limit(
        active_business_income=intake.net_active_business_income,
        aaii=grind_aaii,
        group_taxable_capital=intake.group_taxable_capital,
        schedule_23_allocation=intake.schedule_23_allocation,
        rates=rates,
    )
    corp_tax = compute_corporate_tax(
        sbd=sbd, aaii=investment.part_i_investment_income, province=province, rates=rates,
    )
    tax_pools = compute_tax_pools(
        part_i_investment_income=investment.part_i_investment_income,
        non_eligible_rdtoh_opening=intake.non_eligible_rdtoh_opening,
        eligible_rdtoh_opening=intake.eligible_rdtoh_opening,
        grip_opening=intake.grip_opening,
        cda_opening=intake.cda_opening,
        rates=rates,
        part_iv_to_non_eligible_rdtoh=investment.part_iv_to_non_eligible_rdtoh,
        part_iv_to_eligible_rdtoh=investment.part_iv_to_eligible_rdtoh,
        grip_current_addition=grip_addition(
            general_rate_income=sbd.abi_at_general_rate,
            eligible_dividends_received=investment.eligible_dividends_received,
            rates=rates,
        ),
        cda_current_addition=cda_addition(
            non_taxable_capital_gains=investment.non_taxable_capital_gains,
            life_insurance_cda_credit=investment.life_insurance_cda_credit,
        ),
    )
    dividends = compute_dividends(paid=intake.dividends_paid, pools=tax_pools, rates=rates)
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

    total_before_refund = (
        corp_tax.total_tax_before_credits
        + investment.part_iv_tax
        + dividends.part_iii_1_tax
        + dividends.part_iii_tax
    )
    credits = apply_credits_to_part_i(
        part_i_tax=corp_tax.total_tax_before_credits,
        sred_itc=intake.sred_itc,
        sred_itc_refundable=intake.sred_itc_refundable,
        provincial_credit=intake.provincial_credit,
    )
    net_after_credits = (
        total_before_refund
        - dividends.dividend_refund
        - credits.credits_applied
        - credits.refundable_itc_refund
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
    if credits.unused_credits > 0:
        flags.append(
            f"${credits.unused_credits:,.2f} of non-refundable credits exceed Part I tax and "
            f"are NOT reflected in the year-end position — they carry forward. Confirm the "
            f"refundable SR&ED portion and whether the provincial credit is refundable."
        )
    if credits.refundable_itc_refund > 0:
        flags.append(
            f"${credits.refundable_itc_refund:,.2f} of refundable SR&ED ITC exceeds Part I tax "
            f"and is included in the year-end position as a cash refund — it is only paid "
            f"once CRA accepts the SR&ED claim (T661/Schedule 31)."
        )
    if dividends.cda_carryforward > 0:
        flags.append(
            f"${dividends.cda_carryforward:,.2f} Capital Dividend Account balance is unused."
        )
    if investment.part_iv_tax > 0 and dividends.dividend_refund < investment.part_iv_tax:
        flags.append(
            f"Part IV tax of ${investment.part_iv_tax:,.2f} exceeds this year's dividend "
            f"refund of ${dividends.dividend_refund:,.2f} — the difference sits in RDTOH "
            f"until taxable dividends are paid out."
        )
    if dividends.excessive_eligible_designation > 0:
        flags.append(
            f"Excessive eligible dividend designation of "
            f"${dividends.excessive_eligible_designation:,.2f} (eligible dividends paid exceed "
            f"GRIP) — Part III.1 tax of ${dividends.part_iii_1_tax:,.2f} unless the "
            f"s.185.1(2) election is filed to treat the excess as non-eligible."
        )
    if dividends.excessive_capital_dividend > 0:
        flags.append(
            f"Capital dividend exceeds the CDA by ${dividends.excessive_capital_dividend:,.2f} "
            f"— Part III tax of ${dividends.part_iii_tax:,.2f} unless the s.184(3) election "
            f"is filed to treat the excess as a separate taxable dividend."
        )
    if dividends.non_eligible_rdtoh_carryforward + dividends.eligible_rdtoh_carryforward > 0 and (
        dividends.eligible_paid + dividends.non_eligible_paid > 0
    ):
        flags.append(
            f"${dividends.non_eligible_rdtoh_carryforward + dividends.eligible_rdtoh_carryforward:,.2f} "
            f"of RDTOH remains unrecovered after this year's dividends."
        )
    if intake.prior_year_aaii_override is None and sbd.passive_grind > 0:
        flags.append(
            "SBD grind uses current-year adjusted AAII as a proxy — supply the prior-year "
            "figure to confirm the grind."
        )
    if instalments_required_next_year:
        flags.append("Instalments will likely be required again next year.")

    return CalculationResults(
        tax_year=tax_year,
        entity_name=intake.entity_name,
        province=intake.province,
        sbd=sbd,
        investment_income=investment,
        corporate_tax=corp_tax,
        credits=credits,
        tax_pools=tax_pools,
        dividends=dividends,
        payroll=payroll,
        gst=gst,
        net_income_before_tax=intake.net_income_before_tax,
        total_tax_payable_before_refund=total_before_refund,
        net_corporate_tax_after_credits=net_after_credits,
        estimated_year_end_position=year_end_position,
        instalments_required_next_year=instalments_required_next_year,
        flags=flags,
    )
