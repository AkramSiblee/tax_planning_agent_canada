"""
Every label string the reader searches for, in one place. If the intake workbook
template's wording changes, update it here — never inline a label string inside
excel_reader.py itself.
"""

ENTITY_SETUP = {
    "entity_name": "Legal Name of Corporation",
    "province": "Primary Province of Operation",
    "tax_year": "Tax Year",
    "is_associated": "Associated with Other Corporation(s)?",
}

INCOME_STATEMENT = {
    "net_active_business_income": "Net Active Business Income (for SBD numerator)",
    "aggregate_investment_income": "Aggregate Investment Income (for passive-income grind)",
    "net_income_before_tax": "Net Income Before Tax (total)",
}

PRIOR_YEAR_ATTRIBUTES = {
    "eligible_rdtoh_opening": "Eligible RDTOH — Opening Balance",
    "non_eligible_rdtoh_opening": "Non-Eligible RDTOH — Opening Balance",
    "grip_opening": "GRIP — Opening Balance",
    "cda_opening": "CDA — Opening Balance",
}

PAYROLL_REGISTER = {
    "total_salaries": "TOTAL",  # column C of the payroll table's TOTAL row
}

GST_HST = {
    "taxable_supplies": "Taxable Supplies (revenue subject to GST/HST)",
    "total_itcs": "Total ITCs",
}

INSTALMENTS = {
    "instalments_paid": "Total Instalments Paid",
}

CREDITS = {
    "sred_itc": "Estimated SR&ED Investment Tax Credit",
    "provincial_credit": "Provincial Credit Amount ($)",
}

ASSOCIATED_CORPORATIONS = {
    "table_total_row": "TOTAL",
}

SHAREHOLDERS_TOSI = {
    "tosi_status_column_header": "TOSI Status",
    "name_column_header": "Shareholder Name",
    "not_excluded_value": "Not Excluded - TOSI Risk",
}
