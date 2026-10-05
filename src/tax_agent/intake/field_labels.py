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
    "sred_itc_refundable": "Refundable Portion of SR&ED ITC ($)",
    "provincial_credit_refundable": "Refundable Portion of Provincial Credit ($)",
}

ASSOCIATED_CORPORATIONS = {
    "table_total_row": "TOTAL",
}

SHAREHOLDERS_TOSI = {
    "tosi_status_column_header": "TOSI Status",
    "name_column_header": "Shareholder Name",
    "not_excluded_value": "Not Excluded - TOSI Risk",
}

# Optional holdco section at the bottom of '3. Income Statement' (value in column B).
# If NONE of these labels are present, the reader leaves Intake.investment_detail as
# None and the engine uses the single AAII figure above (legacy workbooks keep working).
INVESTMENT_DETAIL = {
    "interest_and_rents": "Interest & Net Passive Rental Income (Part I)",
    "taxable_capital_gains": "Taxable Capital Gains (taxable portion only)",
    "eligible_portfolio_dividends": "Eligible Dividends Received - Portfolio",
    "non_eligible_portfolio_dividends": "Non-Eligible Dividends Received - Portfolio",
    "connected_eligible_dividends": "Eligible Dividends Received - Connected Corporation",
    "connected_non_eligible_dividends": "Non-Eligible Dividends Received - Connected Corporation",
    "connected_part_iv_from_payer_eligible_rdtoh": "Part IV on Connected Dividends - from Payer's Eligible RDTOH Refund",
    "connected_part_iv_from_payer_non_eligible_rdtoh": "Part IV on Connected Dividends - from Payer's Non-Eligible RDTOH Refund",
    "life_insurance_cda_credit": "Life Insurance Proceeds in Excess of ACB (CDA credit)",
}

DIVIDENDS_PAID = {
    "eligible": "Eligible Dividends Paid",
    "non_eligible": "Non-Eligible Dividends Paid",
    "capital": "Capital Dividends Paid (s.83(2) election)",
}

# Optional, on '5. Prior-Year Tax Attributes' (value in column C).
PRIOR_YEAR_AAII = "Prior-Year Adjusted Aggregate Investment Income (for SBD grind)"
