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
from tax_agent.intake.schema import Intake, InvestmentIncomeDetail

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
        sred_itc_refundable=22_750,  # enhanced 35% rate applies -> fully refundable
        provincial_credit=9_750,
        tosi_risk_shareholders=["Daniel Okafor"],
        # Investment income split by type (fixture '3. Income Statement' holdco section).
        # The 15,000 portfolio dividend is s.112-deductible and taxed under Part IV, not
        # Part I; the 40,000 dividend from the connected sister holdco attracts Part IV
        # equal to the holdco's full refund on it (40,000 x 38 1/3% = 15,333.33).
        investment_detail=InvestmentIncomeDetail(
            interest_and_rents=20_000,  # 12,000 interest + 8,000 net passive rent
            taxable_capital_gains=20_000,
            eligible_portfolio_dividends=15_000,
            connected_non_eligible_dividends=40_000,
            connected_part_iv_from_payer_non_eligible_rdtoh=15_333.33,
        ),
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

    def test_investment_income_split(self):
        inv = self.results.investment_income
        assert inv.part_i_investment_income == pytest.approx(40_000)  # 20,000 + 20,000
        assert inv.adjusted_aaii_for_grind == pytest.approx(55_000)  # + 15,000 portfolio divs
        assert inv.part_iv_on_portfolio_dividends == pytest.approx(5_750, abs=0.01)  # 15,000 x 38 1/3%
        assert inv.part_iv_on_connected_dividends == pytest.approx(15_333.33, abs=0.01)
        assert inv.part_iv_tax == pytest.approx(21_083.33, abs=0.01)

    def test_corporate_tax(self):
        ct = self.results.corporate_tax
        assert ct.tax_on_sbd_income == pytest.approx(20_900)
        assert ct.tax_on_general_income == pytest.approx(0)
        # 40,000 Part I investment income x 46.67% (was 55,000 x 46.67% = 25,668.50
        # before the portfolio dividend was moved out of Part I)
        assert ct.tax_on_investment_income == pytest.approx(18_668, abs=0.5)
        assert ct.total_tax_before_credits == pytest.approx(39_568, abs=0.5)

    def test_tax_pools(self):
        tp = self.results.tax_pools
        # 40,000 x 30.67% = 12,268 + 15,333.33 connected Part IV = 27,601.33
        assert tp.non_eligible_rdtoh_addition == pytest.approx(27_601.33, abs=0.5)
        assert tp.non_eligible_rdtoh_closing == pytest.approx(69_901.33, abs=0.5)
        assert tp.eligible_rdtoh_closing == pytest.approx(24_250, abs=0.01)  # 18,500 + 5,750 Part IV
        assert tp.grip_available == pytest.approx(80_000)  # 65,000 + 15,000 eligible divs received
        assert tp.cda_available == pytest.approx(42_000)  # 22,000 + 20,000 untaxed half of gains

    def test_payroll(self):
        pr = self.results.payroll
        assert pr.employer_cpp == pytest.approx(23_205)
        assert pr.employer_cpp2 == pytest.approx(1_980)
        assert pr.employer_ei == pytest.approx(7_343.84, abs=0.1)
        assert pr.estimated_wcb_premium == pytest.approx(6_900)

    def test_gst(self):
        assert self.results.gst.net_tax == pytest.approx(11_900)

    def test_year_end_position(self):
        # 39,568 Part I + 21,083.33 Part IV = 60,651.33; no dividends paid, so no refund.
        # 60,651.33 - 22,750 - 9,750 = 28,151.33 net; 40,500 paid -> 12,348.67 refund
        assert self.results.total_tax_payable_before_refund == pytest.approx(60_651.33, abs=0.5)
        assert self.results.net_corporate_tax_after_credits == pytest.approx(28_151.33, abs=0.5)
        assert self.results.estimated_year_end_position == pytest.approx(12_348.67, abs=0.5)

    def test_flags(self):
        assert any("grinding" in f.lower() for f in self.results.flags)
        assert any("Daniel Okafor" in f for f in self.results.flags)
        assert any("Capital Dividend" in f and "42,000.00" in f for f in self.results.flags)
        assert any("Part IV tax of $21,083.33" in f for f in self.results.flags)


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

    def test_refundable_sred_portion_read(self):
        assert self.intake.sred_itc_refundable == pytest.approx(22_750)

    def test_investment_detail_read_from_holdco_section(self):
        assert self.intake.investment_detail == _northern_peak_intake().investment_detail

    def test_calculated_total_tax_matches_hand_built_scenario(self):
        assert self.results.corporate_tax.total_tax_before_credits == pytest.approx(39_568, abs=1.0)
        assert self.results.net_corporate_tax_after_credits == pytest.approx(28_151.33, abs=1.0)

    def test_tosi_risk_detected(self):
        assert "Daniel Okafor" in self.intake.tosi_risk_shareholders
