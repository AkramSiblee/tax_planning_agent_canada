"""
One-time build script for config/Tax_Rates_<year>.xlsx.

Run this only to create a NEW tax year's file from scratch (e.g., python
build_rates_workbook.py 2026). To UPDATE an existing year's rates, edit the .xlsx
directly — do not regenerate it, or you will lose any manual edits/citations already
made. See skills/rate-table-maintenance/SKILL.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

FONT_NAME = "Arial"
NAVY = "1F3864"
LTBLUE = "D9E2F3"
YELLOW = "FFFF99"
WHITE = "FFFFFF"
RED = "C00000"

font_title = Font(name=FONT_NAME, size=14, bold=True, color=WHITE)
font_header = Font(name=FONT_NAME, size=10, bold=True)
font_label = Font(name=FONT_NAME, size=10)
font_input = Font(name=FONT_NAME, size=10, color="0000FF")
font_note = Font(name=FONT_NAME, size=9, italic=True, color="808080")
font_warn = Font(name=FONT_NAME, size=9, italic=True, color=RED)

fill_title = PatternFill("solid", fgColor=NAVY)
fill_header = PatternFill("solid", fgColor=LTBLUE)
fill_input = PatternFill("solid", fgColor=YELLOW)

thin = Side(style="thin", color="BFBFBF")
border_all = Border(left=thin, right=thin, top=thin, bottom=thin)


def title_bar(ws, text, span, row=1):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    c = ws.cell(row=row, column=1, value=text)
    c.font = font_title
    c.fill = fill_title
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 26


def set_col_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build(tax_year: int, out_path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    # ---------------- README ----------------
    ws = wb.create_sheet("README")
    set_col_widths(ws, [3, 100])
    title_bar(ws, f"Tax Rates Reference — {tax_year}", span=2)
    row = 3
    ws.cell(row=row, column=2, value=(
        "This workbook is the single source of truth for every rate, threshold, and "
        "payroll figure the calculation engine uses. The engine (src/tax_agent/calc/"
        "rates.py) reads this file directly — nothing here is duplicated in Python code."
    )).font = font_label
    ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True)
    row += 2
    ws.cell(row=row, column=2, value=(
        "Clients never edit this file. Whoever maintains the agent (or an LLM/coding "
        "assistant asked to refresh rates) updates it — see "
        "skills/rate-table-maintenance/SKILL.md for the exact process."
    )).font = font_label
    ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True)
    row += 2
    ws.cell(row=row, column=2, value=(
        "Every value on the 'Provinces' and 'Federal & Payroll' tabs has a Source and "
        "Last Verified column. A value with no source is still illustrative/unverified "
        "— treat it as such regardless of how plausible the number looks."
    )).font = font_warn
    ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[row].height = 30

    # ---------------- Federal & Payroll ----------------
    ws = wb.create_sheet("Federal & Payroll")
    set_col_widths(ws, [42, 18, 34, 16])
    title_bar(ws, "Federal Rates & Payroll Figures", span=4)
    row = 3
    headers = ["Item", "Value", "Source", "Last Verified"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = font_header
        c.fill = fill_header
        c.border = border_all
    row += 1

    federal_rows = [
        ("general_rate_net", 0.15, "Illustrative — verify against current CRA T4012 / T2 guide"),
        ("small_business_rate", 0.09, "Illustrative — verify against current CRA T4012 / T2 guide"),
        ("sbd_base_limit", 500000, "Illustrative — verify against current CRA T4012 / T2 guide"),
        ("investment_income_addon", 0.2367, "Approximation — see skills/tax-calculation/SKILL.md"),
        ("rdtoh_addition_rate", 0.3067, "Illustrative — verify against current CRA publications"),
        ("dividend_refund_rate", 0.383333333333, "Illustrative — verify against current CRA publications"),
        ("instalment_threshold", 3000, "Illustrative — verify against current CRA publications"),
        ("taxable_capital_grind_start", 10000000, "Illustrative — verify against current CRA publications"),
        ("taxable_capital_grind_end", 50000000, "Illustrative — verify against current CRA publications"),
        ("passive_income_grind_start", 50000, "Illustrative — verify against current CRA publications"),
        ("passive_income_grind_end", 150000, "Illustrative — verify against current CRA publications"),
        ("cpp_employee_max", 3867.50, "Illustrative — verify against current CRA CPP tables"),
        ("cpp2_employee_max", 396.00, "Illustrative — verify against current CRA CPP2 tables"),
        ("cpp2_lower_threshold", 71300, "Illustrative — verify against current CRA YMPE figure"),
        ("cpp2_upper_threshold", 81200, "Illustrative — verify against current CRA additional ceiling"),
        ("ei_employee_max", 1049.12, "Illustrative — verify against current CRA EI tables"),
        ("ei_employer_multiplier", 1.4, "Statutory multiplier — confirm unchanged"),
    ]
    for name, value, source in federal_rows:
        ws.cell(row=row, column=1, value=name).font = font_label
        cell = ws.cell(row=row, column=2, value=value)
        cell.font = font_input
        cell.fill = fill_input
        ws.cell(row=row, column=3, value=source).font = font_note
        ws.cell(row=row, column=4, value=f"Illustrative as of {tax_year} build").font = font_note
        for c in range(1, 5):
            ws.cell(row=row, column=c).border = border_all
        row += 1
    ws.freeze_panes = "A4"

    # ---------------- Provinces ----------------
    ws = wb.create_sheet("Provinces")
    set_col_widths(ws, [26, 16, 16, 14, 26, 12, 34, 30, 16])
    title_bar(ws, "Provincial / Territorial Rates", span=9)
    row = 3
    headers = ["Province", "General Rate Combined", "Small Business Rate Combined",
               "SBD Threshold", "GST/HST Type", "GST/HST Rate", "Notes", "Source", "Last Verified"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = font_header
        c.fill = fill_header
        c.border = border_all
        c.alignment = Alignment(wrap_text=True, horizontal="center")
    row += 1

    provinces = [
        ("Alberta", 0.23, 0.11, 500000, "GST only", 0.05, "AB files its own AT1 return — not fully CRA-administered."),
        ("British Columbia", 0.27, 0.11, 500000, "GST only (+PST 7% separate)", 0.05, "PST is separate, not part of GST/HST."),
        ("Saskatchewan", 0.27, 0.10, 500000, "GST only (+PST 6% separate)", 0.05, "PST is separate."),
        ("Manitoba", 0.27, 0.09, 500000, "GST only (+RST 7% separate)", 0.05, "RST separate; MB small business rate historically 0%."),
        ("Ontario", 0.265, 0.122, 500000, "HST", 0.13, "ON corporate return is CRA-administered (harmonized)."),
        ("Quebec", 0.265, 0.122, 500000, "GST + QST (separate)", 0.14975, "QST administered by Revenu Québec, NOT CRA."),
        ("New Brunswick", 0.29, 0.115, 500000, "HST", 0.15, ""),
        ("Nova Scotia", 0.29, 0.115, 500000, "HST", 0.14, "NS reduced its HST rate — confirm current effective rate."),
        ("Prince Edward Island", 0.31, 0.10, 500000, "HST", 0.15, "SBD threshold raised to $500K in recent years — confirm."),
        ("Newfoundland and Labrador", 0.30, 0.115, 500000, "HST", 0.15, "SBD threshold raised to $500K in recent years — confirm."),
        ("Yukon", 0.27, 0.09, 500000, "GST only", 0.05, "Territorial small business rate historically 0%."),
        ("Northwest Territories", 0.265, 0.11, 500000, "GST only", 0.05, ""),
        ("Nunavut", 0.27, 0.12, 500000, "GST only", 0.05, ""),
    ]
    for name, gen, sb, thresh, gsttype, gstrate, notes in provinces:
        ws.cell(row=row, column=1, value=name).font = font_label
        c2 = ws.cell(row=row, column=2, value=gen); c2.font = font_input; c2.fill = fill_input; c2.number_format = "0.0%"
        c3 = ws.cell(row=row, column=3, value=sb); c3.font = font_input; c3.fill = fill_input; c3.number_format = "0.0%"
        c4 = ws.cell(row=row, column=4, value=thresh); c4.font = font_input; c4.fill = fill_input; c4.number_format = "$#,##0"
        c5 = ws.cell(row=row, column=5, value=gsttype); c5.font = font_input; c5.fill = fill_input
        c6 = ws.cell(row=row, column=6, value=gstrate); c6.font = font_input; c6.fill = fill_input; c6.number_format = "0.000%"
        ws.cell(row=row, column=7, value=notes).font = font_note
        ws.cell(row=row, column=8, value="Illustrative — verify against current provincial / CRA publications").font = font_note
        ws.cell(row=row, column=9, value=f"Illustrative as of {tax_year} build").font = font_note
        for c in range(1, 10):
            ws.cell(row=row, column=c).border = border_all
            ws.cell(row=row, column=c).alignment = Alignment(wrap_text=True, vertical="top")
        row += 1
    ws.freeze_panes = "A4"

    wb.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    out = Path(__file__).parent / f"Tax_Rates_{year}.xlsx"
    build(year, out)
