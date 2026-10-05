"""
Keeps the intake workbook's Excel Dashboard tab in sync with the Python calc engine.

The Dashboard is human-facing (the agent never reads it), but a reviewer who opens the
workbook in Excel should see the same numbers the report shows. This test compares the
fixture's cached Dashboard values against run_calculation() on the same workbook — if
you change a calc rule, update the Dashboard formulas too (see
skills/intake-collection/SKILL.md) or this test will fail.
"""
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tax_agent.calc import run_calculation
from tax_agent.intake.excel_reader import read_intake

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "northern_peak_sample.xlsx"
TEMPLATE_PATH = Path(__file__).parents[1] / "clients" / "_template" / "CCPC_Tax_Planning_Intake_Workbook.xlsx"

# Dashboard label prefix (column A) -> the engine figure it must equal.
DASHBOARD_TO_ENGINE = {
    "Passive-Income Grind": lambda r: r.sbd.passive_grind,
    "This Entity's SBD Limit": lambda r: r.sbd.entity_limit,
    "Part I Investment Income (interest": lambda r: r.investment_income.part_i_investment_income,
    "TOTAL PART IV TAX": lambda r: r.investment_income.part_iv_tax,
    "PART I TAX (before credits)": lambda r: r.corporate_tax.total_tax_before_credits,
    "TOTAL TAX PAYABLE BEFORE DIVIDEND REFUND": lambda r: r.total_tax_payable_before_refund,
    "Less: Credits Applied": lambda r: r.credits.credits_applied,
    "Less: Refundable Credits Paid in Cash": lambda r: (
        r.credits.refundable_itc_refund + r.credits.refundable_provincial_refund
    ),
    "NET CORPORATE TAX AFTER CREDITS": lambda r: r.net_corporate_tax_after_credits,
    "Balance Owing / (Refund) at Year-End": lambda r: -r.estimated_year_end_position,
    "Unused Non-Refundable Credits": lambda r: r.credits.unused_credits,
    "Non-Eligible RDTOH — Year-End": lambda r: r.tax_pools.non_eligible_rdtoh_closing,
    "Eligible RDTOH — Year-End": lambda r: r.tax_pools.eligible_rdtoh_closing,
    "GRIP Available at Year-End": lambda r: r.tax_pools.grip_available,
    "CDA Available at Year-End": lambda r: r.tax_pools.cda_available,
    "TOTAL DIVIDEND REFUND": lambda r: r.dividends.dividend_refund,
    "Non-Eligible RDTOH Carried Forward": lambda r: r.dividends.non_eligible_rdtoh_carryforward,
    "Eligible RDTOH Carried Forward": lambda r: r.dividends.eligible_rdtoh_carryforward,
    "Excessive Eligible Dividend Designation": lambda r: r.dividends.excessive_eligible_designation,
    "Excessive Capital Dividend": lambda r: r.dividends.excessive_capital_dividend,
    "CDA Carried Forward": lambda r: r.dividends.cda_carryforward,
}


def _dashboard_value(ws, prefix):
    rows = [r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value or "").startswith(prefix)]
    assert len(rows) == 1, f"expected exactly one Dashboard row starting {prefix!r}, found {rows}"
    return ws.cell(rows[0], 2).value


@pytest.mark.parametrize("path", [FIXTURE_PATH, TEMPLATE_PATH], ids=["fixture", "template"])
@pytest.mark.parametrize("prefix", list(DASHBOARD_TO_ENGINE))
def test_dashboard_matches_engine(path, prefix):
    results = run_calculation(read_intake(path), tax_year=2025)
    ws = load_workbook(path, data_only=True)["Dashboard"]
    value = _dashboard_value(ws, prefix)
    assert value is not None, f"{prefix!r} has no cached value — re-save the workbook in Excel"
    assert value == pytest.approx(DASHBOARD_TO_ENGINE[prefix](results), abs=0.01)
