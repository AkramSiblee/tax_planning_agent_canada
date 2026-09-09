"""
Regression tests against the hand-verified Northern Peak Consulting Inc. scenario.

If you change a calc/ formula and one of these assertions needs to change too, that's
expected — but update the expected value deliberately and explain why (see CLAUDE.md).
A silently-changed number here is exactly the bug class this suite exists to catch.
"""
from pathlib import Path

import pytest

from tax_agent.calc import run_calculation
from tax_agent.intake.excel_reader import read_intake
from tax_agent.intake.schema import Intake

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "northern_peak_sample.xlsx"


def _northern_peak_intake() -> Intake:
    """The known-correct Northern Peak Consulting Inc. scenario, built by hand."""
    return Intake(
        entity_name="Northern Peak Consulting Inc.",
        province="Alberta",
        tax_year=2025,
        is_associated=True,
        net_active_business_income=190_000,
        aggregate_investment_income=55_000,
        net_income_before_tax=285_000,
        group_taxable_capital=1_565_000,
        schedule_23_allocation=350_000,
        non_eligible_rdtoh_opening=42_300,
        eligible_rdtoh_opening=18_500,
        grip_opening=65_000,
        cda_opening=22_000,
        total_salaries=600_000,
        employee_cpp_total=23_205,
        employee_cpp2_total=1_980,
        employee_ei_total=5_245.60,
        wcb_assessable_payroll=600_000,
        wcb_premium_rate_per_100=1.15,
        taxable_supplies=1_200_000,
        total_itcs=48_100,
        instalments_paid=40_500,
        sred_itc=22_750,
        provincial_credit=9_750,
        tosi_risk_shareholders=["Daniel Okafor"],
    )


class TestCalcEngineWithHandBuiltIntake:
    def setup_method(self):
        self.results = run_calculation(_northern_peak_intake(), tax_year=2025)

    def test_sbd_limit(self):
        assert self.results.sbd.passive_grind == pytest.approx(25_000)
        assert self.results.sbd.taxcap_grind == pytest.approx(0)
        assert self.results.sbd.federal_limit_after_grinds == pytest.approx(475_000)
        assert self.results.sbd.entity_limit == pytest.approx(350_000)
        assert self.results.sbd.abi_at_sbd_rate == pytest.approx(190_000)
        assert self.results.sbd.abi_at_general_rate == pytest.approx(0)
        assert self.results.sbd.is_grinding is True

    def test_corporate_tax(self):
        ct = self.results.corporate_tax
        assert ct.tax_on_sbd_income == pytest.approx(20_900)
        assert ct.tax_on_general_income == pytest.approx(0)
        assert ct.tax_on_investment_income == pytest.approx(25_668.5, abs=0.5)
        assert ct.total_tax_before_credits == pytest.approx(46_568.5, abs=0.5)

    def test_tax_pools(self):
        tp = self.results.tax_pools
        assert tp.non_eligible_rdtoh_addition == pytest.approx(16_868.5, abs=0.5)
        assert tp.non_eligible_rdtoh_closing == pytest.approx(59_168.5, abs=0.5)
        assert tp.eligible_rdtoh_closing == pytest.approx(18_500)
        assert tp.grip_available == pytest.approx(65_000)
        assert tp.cda_available == pytest.approx(22_000)

    def test_payroll(self):
        pr = self.results.payroll
        assert pr.employer_cpp == pytest.approx(23_205)
        assert pr.employer_cpp2 == pytest.approx(1_980)
        assert pr.employer_ei == pytest.approx(7_343.84, abs=0.1)
        assert pr.estimated_wcb_premium == pytest.approx(6_900)

    def test_gst(self):
        assert self.results.gst.net_tax == pytest.approx(11_900)

    def test_year_end_position(self):
        # 46,568.50 - 22,750 - 9,750 = 14,068.50 net; 40,500 paid -> 26,431.50 refund
        assert self.results.net_corporate_tax_after_credits == pytest.approx(14_068.5, abs=0.5)
        assert self.results.estimated_year_end_position == pytest.approx(26_431.5, abs=0.5)

    def test_flags(self):
        assert any("grinding" in f.lower() for f in self.results.flags)
        assert any("Daniel Okafor" in f for f in self.results.flags)
        assert any("Capital Dividend" in f for f in self.results.flags)


class TestExcelReaderEndToEnd:
    """Reads the actual fixture workbook and confirms the same figures come out."""

    def setup_method(self):
        if not FIXTURE_PATH.exists():
            pytest.skip(f"Fixture not found at {FIXTURE_PATH}")
        self.intake = read_intake(FIXTURE_PATH)
        self.results = run_calculation(self.intake, tax_year=2025)

    def test_entity_fields(self):
        assert self.intake.entity_name == "Northern Peak Consulting Inc."
        assert self.intake.province == "Alberta"
        assert self.intake.tax_year == 2025

    def test_income_statement_fields(self):
        assert self.intake.net_active_business_income == pytest.approx(190_000)
        assert self.intake.aggregate_investment_income == pytest.approx(55_000)

    def test_calculated_total_tax_matches_hand_built_scenario(self):
        assert self.results.corporate_tax.total_tax_before_credits == pytest.approx(46_568.5, abs=1.0)

    def test_tosi_risk_detected(self):
        assert "Daniel Okafor" in self.intake.tosi_risk_shareholders
