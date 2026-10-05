"""
Investment-income classification and Part IV tax. See skills/tax-calculation/SKILL.md.

Splits a corporation's investment income into the three streams the Act treats
differently: Part I investment income (interest, rents, taxable capital gains),
portfolio dividends (deductible under s.112, but subject to Part IV tax), and dividends
from connected corporations (Part IV only to the extent of the payer's dividend refund).
"""
from __future__ import annotations

from dataclasses import dataclass

from tax_agent.intake.schema import InvestmentIncomeDetail

from .rates import RateTable


@dataclass(frozen=True)
class InvestmentIncomeResult:
    part_i_investment_income: float  # taxed at the investment-income rate under Part I
    adjusted_aaii_for_grind: float  # current-year adjusted AAII (s.125(7)) for the SBD grind
    part_iv_on_portfolio_dividends: float
    part_iv_on_connected_dividends: float
    part_iv_tax: float
    part_iv_to_eligible_rdtoh: float
    part_iv_to_non_eligible_rdtoh: float
    eligible_dividends_received: float  # portfolio + connected; feeds the GRIP addition
    total_dividends_received: float  # deducted under s.112, so not in Part I income
    non_taxable_capital_gains: float  # credits the CDA
    life_insurance_cda_credit: float
    used_detail: bool  # False = legacy single-figure AAII path


def part_iv_on_portfolio_dividends(dividends: float, rates: RateTable) -> float:
    """
    ITA s.186(1)(a): Part IV tax of 38 1/3% on taxable dividends received from
    non-connected ("portfolio") corporations.

    Simplification: ignores the s.186(1)(c)/(d) reduction for non-capital losses
    applied against Part IV tax.
    """
    return dividends * rates.federal["part_iv_tax_rate"]


def non_taxable_capital_gains(taxable_capital_gains: float, rates: RateTable) -> float:
    """
    The untaxed portion of a net capital gain, derived from the taxable portion:
    with a 1/2 inclusion rate, the non-taxable half equals the taxable half. This is
    what credits the capital dividend account under s.89(1) "capital dividend account" (a).

    Simplification: assumes all gains were realized at the single inclusion rate in the
    rates workbook, and that the gains are net of capital losses realized in the same
    year (a net capital loss reduces the CDA; that reduction is not modelled).
    """
    inclusion = rates.federal["capital_gains_inclusion_rate"]
    return max(0.0, taxable_capital_gains) * (1 - inclusion) / inclusion


def classify_investment_income(
    *,
    aggregate_investment_income: float,
    detail: InvestmentIncomeDetail | None,
    rates: RateTable,
) -> InvestmentIncomeResult:
    """
    With `detail`: Part I investment income is interest/rents + taxable capital gains;
    adjusted AAII for the grind adds portfolio dividends (s.125(7) "adjusted aggregate
    investment income" includes dividends from non-connected corporations); Part IV is
    38 1/3% of portfolio dividends plus the given share of connected payers' refunds.

    Without `detail` (legacy intake): the single AAII figure is treated as Part I
    investment income and as adjusted AAII, with no Part IV, dividends or CDA credits —
    exactly the pre-split behaviour, so existing scenarios reproduce unchanged.

    Simplification: adjusted AAII does not exclude gains on active-business assets or
    carried-forward net capital losses — supply a reduced figure via the intake if those apply.
    """
    if detail is None:
        return InvestmentIncomeResult(
            part_i_investment_income=aggregate_investment_income,
            adjusted_aaii_for_grind=aggregate_investment_income,
            part_iv_on_portfolio_dividends=0.0,
            part_iv_on_connected_dividends=0.0,
            part_iv_tax=0.0,
            part_iv_to_eligible_rdtoh=0.0,
            part_iv_to_non_eligible_rdtoh=0.0,
            eligible_dividends_received=0.0,
            total_dividends_received=0.0,
            non_taxable_capital_gains=0.0,
            life_insurance_cda_credit=0.0,
            used_detail=False,
        )

    portfolio = detail.eligible_portfolio_dividends + detail.non_eligible_portfolio_dividends
    part_i = detail.interest_and_rents + detail.taxable_capital_gains

    part_iv_eligible_portfolio = part_iv_on_portfolio_dividends(detail.eligible_portfolio_dividends, rates)
    part_iv_non_eligible_portfolio = part_iv_on_portfolio_dividends(detail.non_eligible_portfolio_dividends, rates)
    part_iv_connected = (
        detail.connected_part_iv_from_payer_eligible_rdtoh
        + detail.connected_part_iv_from_payer_non_eligible_rdtoh
    )
    part_iv_portfolio = part_iv_eligible_portfolio + part_iv_non_eligible_portfolio

    return InvestmentIncomeResult(
        part_i_investment_income=part_i,
        adjusted_aaii_for_grind=part_i + portfolio,
        part_iv_on_portfolio_dividends=part_iv_portfolio,
        part_iv_on_connected_dividends=part_iv_connected,
        part_iv_tax=part_iv_portfolio + part_iv_connected,
        # s.129(4) "eligible refundable dividend tax on hand": Part IV on eligible
        # portfolio dividends + Part IV on connected dividends to the extent the payer's
        # refund came from its own eligible RDTOH. Everything else goes to non-eligible.
        part_iv_to_eligible_rdtoh=part_iv_eligible_portfolio + detail.connected_part_iv_from_payer_eligible_rdtoh,
        part_iv_to_non_eligible_rdtoh=part_iv_non_eligible_portfolio + detail.connected_part_iv_from_payer_non_eligible_rdtoh,
        eligible_dividends_received=detail.eligible_portfolio_dividends + detail.connected_eligible_dividends,
        total_dividends_received=(
            portfolio + detail.connected_eligible_dividends + detail.connected_non_eligible_dividends
        ),
        non_taxable_capital_gains=non_taxable_capital_gains(detail.taxable_capital_gains, rates),
        life_insurance_cda_credit=detail.life_insurance_cda_credit,
        used_detail=True,
    )
