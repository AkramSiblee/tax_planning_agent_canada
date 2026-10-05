"""
Generates the "Planning Recommendations" prose via the configured LLM.

Non-negotiable rule (see CLAUDE.md): the LLM never computes a number. It is given the
already-computed CalculationResults and asked to explain/prioritize them in prose. This
module also sanity-checks the LLM's response for dollar figures that don't trace back to
anything in CalculationResults — a sign the model invented or mis-transcribed a number.
"""
from __future__ import annotations

import logging
import re

from tax_agent.calc.engine import CalculationResults
from tax_agent.llm import complete
from tax_agent.utils import format_currency

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Canadian corporate tax planning assistant writing the \
recommendations section of a client report. You will be given a fixed set of already-\
calculated numbers. Your job is to explain and prioritize them in clear, professional \
prose for a business owner — you must NOT calculate, estimate, or alter any number. \
Use only the dollar figures given to you, exactly as given. Do not invent a number that \
was not provided. Write 4-7 ranked, numbered recommendations. Each should have a short \
bold-style headline (as plain text, no markdown) followed by 1-3 sentences of \
explanation. Do not use markdown formatting of any kind - plain text only."""


def _build_user_prompt(results: CalculationResults) -> str:
    lines = [
        f"Entity: {results.entity_name} ({results.province}, tax year {results.tax_year})",
        f"Net active business income: {format_currency(results.sbd.abi_at_sbd_rate + results.sbd.abi_at_general_rate)}",
        f"Part I investment income: {format_currency(results.investment_income.part_i_investment_income)}",
        f"Total dividends received: {format_currency(results.investment_income.total_dividends_received)}",
        f"Part IV tax: {format_currency(results.investment_income.part_iv_tax)}",
        f"SBD limit for this entity: {format_currency(results.sbd.entity_limit)}",
        f"Passive-income grind: {format_currency(results.sbd.passive_grind)}",
        f"Total corporate tax before credits: {format_currency(results.corporate_tax.total_tax_before_credits)}",
        f"Total tax payable before dividend refund: {format_currency(results.total_tax_payable_before_refund)}",
        f"Dividend refund: {format_currency(results.dividends.dividend_refund)}",
        f"Part III.1 tax (excess eligible designation, no election): {format_currency(results.dividends.part_iii_1_tax)}",
        f"Part III tax (excess capital dividend, no election): {format_currency(results.dividends.part_iii_tax)}",
        f"Net corporate tax after credits: {format_currency(results.net_corporate_tax_after_credits)}",
        f"Estimated year-end position (positive=refund, negative=owing): {format_currency(results.estimated_year_end_position)}",
        f"Non-eligible RDTOH closing balance: {format_currency(results.tax_pools.non_eligible_rdtoh_closing)}",
        f"Eligible RDTOH balance: {format_currency(results.tax_pools.eligible_rdtoh_closing)}",
        f"GRIP balance: {format_currency(results.tax_pools.grip_available)}",
        f"CDA balance: {format_currency(results.tax_pools.cda_available)}",
        f"Instalments likely required next year: {results.instalments_required_next_year}",
        "Flags: " + ("; ".join(results.flags) if results.flags else "none"),
    ]
    return (
        "Write the planning recommendations for this client using ONLY the figures "
        "below. Do not introduce any other dollar amount.\n\n" + "\n".join(lines)
    )


_DOLLAR_RE = re.compile(r"\$[\d,]+\.?\d*")


def _known_dollar_strings(results: CalculationResults) -> set[str]:
    """Every dollar figure that legitimately appears in CalculationResults, normalized."""
    values = [
        results.sbd.entity_limit,
        results.sbd.passive_grind,
        results.corporate_tax.total_tax_before_credits,
        results.net_corporate_tax_after_credits,
        results.estimated_year_end_position,
        results.tax_pools.non_eligible_rdtoh_closing,
        results.tax_pools.eligible_rdtoh_closing,
        results.tax_pools.grip_available,
        results.tax_pools.cda_available,
        results.tax_pools.dividend_needed_to_recover_non_eligible_rdtoh,
        results.tax_pools.dividend_needed_to_recover_eligible_rdtoh,
        results.investment_income.part_i_investment_income,
        results.investment_income.total_dividends_received,
        results.investment_income.part_iv_tax,
        results.total_tax_payable_before_refund,
        results.dividends.dividend_refund,
        results.dividends.part_iii_1_tax,
        results.dividends.part_iii_tax,
        results.dividends.excessive_eligible_designation,
        results.dividends.excessive_capital_dividend,
        results.dividends.non_eligible_rdtoh_carryforward + results.dividends.eligible_rdtoh_carryforward,
        results.dividends.cda_carryforward,
    ]
    return {f"{abs(v):,.2f}" for v in values} | {f"{abs(v):,.0f}" for v in values}


def _sanity_check_narrative(text: str, results: CalculationResults) -> list[str]:
    """
    Returns a list of dollar strings found in `text` that don't match any known figure
    in `results`. An empty list means every number the LLM wrote is traceable. This does
    NOT raise — callers decide whether an unrecognized figure should block report
    generation or just be logged for review.
    """
    known = _known_dollar_strings(results)
    found = {m.group(0).lstrip("$") for m in _DOLLAR_RE.finditer(text)}
    unrecognized = [f"${v}" for v in found if v not in known]
    return unrecognized


def generate_recommendations(results: CalculationResults) -> str:
    user_prompt = _build_user_prompt(results)
    text = complete(SYSTEM_PROMPT, user_prompt, temperature=0.3)

    unrecognized = _sanity_check_narrative(text, results)
    if unrecognized:
        logger.warning(
            "Narrative contains dollar figures not traceable to CalculationResults: %s "
            "— review this report's recommendations section before sending to the client.",
            unrecognized,
        )
    return text
