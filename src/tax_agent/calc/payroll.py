"""Payroll (CPP/CPP2/EI/WCB) calculations. See skills/tax-calculation/SKILL.md."""
from __future__ import annotations

from dataclasses import dataclass

from .rates import RateTable


@dataclass(frozen=True)
class PayrollResult:
    total_salaries: float
    employer_cpp: float
    employer_cpp2: float
    employer_ei: float
    estimated_wcb_premium: float


def compute_payroll(
    *,
    total_salaries: float,
    employee_cpp_total: float,
    employee_cpp2_total: float,
    employee_ei_total: float,
    wcb_assessable_payroll: float,
    wcb_premium_rate_per_100: float,
    rates: RateTable,
) -> PayrollResult:
    """
    Employer CPP and CPP2 match the employee totals 1:1. Employer EI is the employee
    total multiplied by the statutory multiplier (currently 1.4x).

    Note: an owner-manager with >40% voting control is excluded from EI on their own
    salary under the Employment Insurance Act. That exclusion must be applied by the
    caller when building `employee_ei_total` from the payroll register — this function
    does not know which employee is an excluded owner-manager.
    """
    multiplier = rates.payroll["ei_employer_multiplier"]
    employer_ei = employee_ei_total * multiplier
    wcb_premium = wcb_assessable_payroll / 100 * wcb_premium_rate_per_100

    return PayrollResult(
        total_salaries=total_salaries,
        employer_cpp=employee_cpp_total,
        employer_cpp2=employee_cpp2_total,
        employer_ei=employer_ei,
        estimated_wcb_premium=wcb_premium,
    )
