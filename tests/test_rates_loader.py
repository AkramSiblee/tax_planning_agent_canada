"""Direct tests for calc/rates.py — the new Excel-based rates loader."""
import pytest

from tax_agent.calc.rates import (
    RateFileNotFoundError,
    UnknownProvinceError,
    load_rates,
)


def test_loads_2025_rates():
    rates = load_rates(2025)
    assert rates.tax_year == 2025
    assert rates.federal["sbd_base_limit"] == pytest.approx(500000)
    assert rates.payroll["ei_employer_multiplier"] == pytest.approx(1.4)


def test_province_lookup():
    rates = load_rates(2025)
    alberta = rates.province("Alberta")
    assert alberta.general_rate_combined == pytest.approx(0.23)
    assert alberta.small_business_rate_combined == pytest.approx(0.11)
    assert alberta.gst_hst_type == "GST only"


def test_all_thirteen_provinces_load():
    rates = load_rates(2025)
    assert len(rates.provinces) == 13


def test_unknown_province_raises_clear_error():
    rates = load_rates(2025)
    with pytest.raises(UnknownProvinceError, match="Not A Real Province"):
        rates.province("Not A Real Province")


def test_missing_tax_year_raises_clear_error():
    with pytest.raises(RateFileNotFoundError, match="2099"):
        load_rates(2099)
