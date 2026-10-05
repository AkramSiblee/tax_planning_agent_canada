"""
Rebuilds the Dashboard tab of a CCPC intake workbook so its formulas mirror the Python
calc engine (src/tax_agent/calc/): investment-income split, Part IV, credits against
Part I tax only, dividend refund ordering, GRIP/CDA additions, Part III.1 / Part III.

The agent never reads the Dashboard — it exists for a reviewer opening the workbook in
Excel. tests/test_dashboard.py fails if the Dashboard and the engine disagree; when you
change a calc rule, update LAYOUT below and rerun this on the template and the fixture:

    python tools/rebuild_dashboard.py clients/_template/CCPC_Tax_Planning_Intake_Workbook.xlsx \
        tests/fixtures/northern_peak_sample.xlsx

Requirements: Windows with Microsoft Excel installed, and pywin32 (`pip install pywin32`).
Excel (not openpyxl) does the editing so that cached formula values and the workbook's
dropdowns survive the save.

Safe to rerun: it accepts both the original Dashboard layout and the one it produces.
Each workbook is rebuilt on a temporary copy outside this (OneDrive-synced) folder and
only copied back once the rebuild succeeds, so Excel AutoSave can never leave a
half-edited workbook behind. It refuses to run if any input row it depends on has moved.

This is a maintainer tool: user-facing output via print() is intentional here.
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

import win32com.client

IS = "'3. Income Statement'"
PY = "'5. Prior-Year Tax Attributes'"
CR = "'12. Credits & Incentives'"
R = "0.383333333333"  # Part IV rate = dividend refund rate (38 1/3%)

# Every address the formulas depend on, with the label expected in column A.
EXPECTED_LABELS = [
    ("3. Income Statement", 52, "Interest & Net Passive Rental Income (Part I)"),
    ("3. Income Statement", 53, "Taxable Capital Gains (taxable portion only)"),
    ("3. Income Statement", 54, "Eligible Dividends Received - Portfolio"),
    ("3. Income Statement", 55, "Non-Eligible Dividends Received - Portfolio"),
    ("3. Income Statement", 56, "Eligible Dividends Received - Connected Corporation"),
    ("3. Income Statement", 57, "Non-Eligible Dividends Received - Connected Corporation"),
    ("3. Income Statement", 58, "Part IV on Connected Dividends - from Payer's Eligible RDTOH Refund"),
    ("3. Income Statement", 59, "Part IV on Connected Dividends - from Payer's Non-Eligible RDTOH Refund"),
    ("3. Income Statement", 60, "Life Insurance Proceeds in Excess of ACB (CDA credit)"),
    ("3. Income Statement", 63, "Eligible Dividends Paid"),
    ("3. Income Statement", 64, "Non-Eligible Dividends Paid"),
    ("3. Income Statement", 65, "Capital Dividends Paid (s.83(2) election)"),
    ("5. Prior-Year Tax Attributes", 30, "Prior-Year Adjusted Aggregate Investment Income (for SBD grind)"),
    ("12. Credits & Incentives", 9, "Estimated SR&ED Investment Tax Credit"),
    ("12. Credits & Incentives", 10, "Refundable Portion of SR&ED ITC ($)"),
    ("12. Credits & Incentives", 14, "Provincial Credit Amount ($)"),
    ("12. Credits & Incentives", 15, "Refundable Portion of Provincial Credit ($)"),
]

# Rows to copy each cell style from. The original workbook layout has fixed positions;
# a workbook this tool already rebuilt is read back through the LAYOUT keys below.
LEGACY_FIRST_HEADER = "2. CURRENT-YEAR CORPORATE TAX ESTIMATE (federal + provincial)"
LEGACY_STYLE_ROWS = {"header": 27, "money": 28, "total": 31, "signed": 33, "text": 34,
                     "bold": 45, "flag": 56, "note": 59}
# Each source must be a row WITHOUT a column-C note, or the note's italic styling spreads.
CURRENT_STYLE_KEYS = {"header": "h2", "money": "portfolio", "total": "p4", "signed": "owing",
                      "text": "inst_next", "bold": "cda_flag", "flag": "f1", "note": "f10"}

D = "{detail}=\"Yes\""  # shorthand used inside formulas

# (key, style, label, formula or None, note) — formulas reference other rows as {key}.
LAYOUT = [
    ("h2", "header", "2. INVESTMENT INCOME & PART IV TAX", None, None),
    ("detail", "text", "Investment-Income Detail Supplied? (holdco section, '3. Income Statement')",
     f"=IF(SUMPRODUCT(--({IS}!B52:B60<>0))>0,\"Yes\",\"No\")",
     "If No, the single Aggregate Investment Income figure is used for everything below."),
    ("part_i_inv", "money", "Part I Investment Income (interest, rents, taxable capital gains)",
     f"=IF({D},{IS}!B52+{IS}!B53,{IS}!B48)", "Dividends received are deductible (s.112) and excluded here."),
    ("portfolio", "money", "Portfolio Dividends Received (non-connected)",
     f"=IF({D},{IS}!B54+{IS}!B55,0)", None),
    ("connected", "money", "Connected-Corporation Dividends Received",
     f"=IF({D},{IS}!B56+{IS}!B57,0)", None),
    ("p4_port", "money", "Part IV Tax on Portfolio Dividends (38⅓%)", f"={{portfolio}}*{R}", None),
    ("p4_conn", "money", "Part IV Tax on Connected Dividends (share of payer's refund)",
     f"=IF({D},{IS}!B58+{IS}!B59,0)", None),
    ("p4", "total", "TOTAL PART IV TAX (refundable — added to RDTOH)", "={p4_port}+{p4_conn}", None),
    ("cg_cda", "money", "Non-Taxable Capital Gains (credits the CDA)",
     f"=IF({D},{IS}!B53,0)", "Equals the taxable portion at a 1/2 inclusion rate."),
    (None, None, None, None, None),
    ("h3", "header", "3. CURRENT-YEAR CORPORATE TAX ESTIMATE (federal + provincial)", None, None),
    ("t_sbd", "money", "Tax on SBD-Rate Income", "=B23*B11", None),
    ("t_gen", "money", "Tax on General-Rate Active Business Income", "=B24*B12", None),
    ("t_inv", "money", "Tax on Part I Investment Income", "={part_i_inv}*B13", None),
    ("part_i", "total", "PART I TAX (before credits)", "={t_sbd}+{t_gen}+{t_inv}", None),
    ("t_p4", "money", "Part IV Tax", "={p4}", None),
    ("t_p31", "money", "Part III.1 Tax — excessive eligible dividend (20%, if no election)",
     "=0.2*{eedd}", "Avoidable by the s.185.1(2) election to treat the excess as non-eligible."),
    ("t_p3", "money", "Part III Tax — excessive capital dividend (60%, if no election)",
     "=0.6*{excd}", "Avoidable by the s.184(3) election to treat the excess as a taxable dividend."),
    ("before_refund", "total", "TOTAL TAX PAYABLE BEFORE DIVIDEND REFUND",
     "={part_i}+{t_p4}+{t_p31}+{t_p3}", None),
    ("less_refund", "money", "Less: Dividend Refund", "={refund}", None),
    ("less_credits", "money", "Less: Credits Applied Against Part I Tax (never below zero)",
     f"=MIN({CR}!C9+{CR}!C14,MAX(0,{{part_i}}))",
     "SR&ED ITC + provincial credit reduce Part I tax only — not Part IV, III.1 or III."),
    ("less_cash", "money", "Less: Refundable Credits Paid in Cash (excess over Part I tax)",
     f"=({CR}!C10+{CR}!C15)-({{less_credits}}-MIN(({CR}!C9-{CR}!C10)+({CR}!C14-{CR}!C15),MAX(0,{{part_i}})))",
     "Paid only once the SR&ED / provincial claim is accepted."),
    ("net", "total", "NET CORPORATE TAX AFTER CREDITS",
     "={before_refund}-{less_refund}-{less_credits}-{less_cash}", None),
    ("instalments", "money", "Less: Instalments Already Paid", "='11. Instalments & Compliance'!B20", None),
    ("owing", "signed", "Balance Owing / (Refund) at Year-End", "={net}-{instalments}", None),
    ("unused", "money", "Unused Non-Refundable Credits (carry forward — NOT in the balance above)",
     f"=(({CR}!C9-{CR}!C10)+({CR}!C14-{CR}!C15))-MIN(({CR}!C9-{CR}!C10)+({CR}!C14-{CR}!C15),MAX(0,{{part_i}}))",
     None),
    ("inst_next", "text", "Instalments Likely Required Next Year?", "=IF({part_i}>3000,\"Yes\",\"No\")", None),
    (None, None, None, None, None),
    ("h4", "header", "4. RDTOH / GRIP / CDA — RECOVERABLE TAX POOLS", None, None),
    ("ne_add", "money", "Non-Eligible RDTOH Addition (30⅔% of Part I investment income + non-eligible Part IV)",
     f"={{part_i_inv}}*0.3067+IF({D},{IS}!B55*{R}+{IS}!B59,0)", None),
    ("ne_open", "money", "Non-Eligible RDTOH — Opening Balance", f"={PY}!C6", None),
    ("ne_close", "money", "Non-Eligible RDTOH — Year-End, Before Dividends", "={ne_open}+{ne_add}", None),
    ("e_add", "money", "Eligible RDTOH Addition (eligible portfolio Part IV + connected Part IV from payer's eligible RDTOH)",
     f"=IF({D},{IS}!B54*{R}+{IS}!B58,0)", None),
    ("e_open", "money", "Eligible RDTOH — Opening Balance", f"={PY}!C5", None),
    ("e_close", "money", "Eligible RDTOH — Year-End, Before Dividends", "={e_open}+{e_add}", None),
    ("grip_add", "money", "GRIP Addition (0.72 × general-rate ABI + eligible dividends received)",
     f"=0.72*B24+IF({D},{IS}!B54+{IS}!B56,0)", None),
    ("grip", "money", "GRIP Available at Year-End", f"={PY}!C9+{{grip_add}}", None),
    ("cda_add", "money", "CDA Addition (non-taxable capital gains + life insurance over ACB)",
     f"={{cg_cda}}+IF({D},{IS}!B60,0)", None),
    ("cda", "money", "CDA Available at Year-End", f"={PY}!C12+{{cda_add}}", None),
    ("ne_needed", "money", "Non-Eligible Dividend Needed to Fully Recover Non-Eligible RDTOH (÷38⅓%)",
     f"={{ne_close}}/{R}", None),
    ("e_needed", "money", "Eligible Dividend Needed to Fully Recover Eligible RDTOH (÷38⅓%)",
     f"={{e_close}}/{R}", None),
    (None, None, None, None, None),
    ("h5", "header", "5. DIVIDENDS PAID THIS YEAR — REFUND & DESIGNATION TESTS", None, None),
    ("pd_e", "money", "Eligible Dividends Paid", f"={IS}!B63", None),
    ("pd_ne", "money", "Non-Eligible Dividends Paid", f"={IS}!B64", None),
    ("pd_c", "money", "Capital Dividends Paid", f"={IS}!B65", None),
    ("ref_ne", "money", "Refund from Non-Eligible RDTOH (non-eligible dividends × 38⅓%)",
     f"=MIN({{pd_ne}}*{R},{{ne_close}})", None),
    ("ref_e", "money", "Refund from Eligible RDTOH (eligible dividends, then non-eligible overflow)",
     f"=MIN({{pd_e}}*{R},{{e_close}})+MIN({{pd_ne}}*{R}-{{ref_ne}},{{e_close}}-MIN({{pd_e}}*{R},{{e_close}}))",
     "Eligible dividends recover eligible RDTOH only; non-eligible dividends use non-eligible RDTOH first."),
    ("refund", "total", "TOTAL DIVIDEND REFUND", "={ref_ne}+{ref_e}", None),
    ("ne_cf", "money", "Non-Eligible RDTOH Carried Forward", "={ne_close}-{ref_ne}", None),
    ("e_cf", "money", "Eligible RDTOH Carried Forward", "={e_close}-{ref_e}", None),
    ("eedd", "money", "Excessive Eligible Dividend Designation (eligible paid over GRIP)",
     "=MAX(0,{pd_e}-{grip})", None),
    ("grip_cf", "money", "GRIP Carried Forward", "=MAX(0,{grip}-{pd_e})", None),
    ("excd", "money", "Excessive Capital Dividend (capital paid over CDA)", "=MAX(0,{pd_c}-{cda})", None),
    ("cda_cf", "money", "CDA Carried Forward", "=MAX(0,{cda}-{pd_c})", None),
    ("cda_flag", "bold", "⚠ Action Flag",
     "=IF({cda_cf}>0,\"CDA balance sitting idle — consider a capital dividend election\",\"No unused CDA balance\")", None),
    (None, None, None, None, None),
    ("h6", "header", "6. PAYROLL, GST/HST & COMPLIANCE SUMMARY", None, None),
    ("sal", "money", "Total Salaries & Wages Paid", "='9. Payroll Register'!C13", None),
    ("ei", "money", "Employer EI Contribution (1.4x)", "='9. Payroll Register'!C18", None),
    ("gst", "signed", "GST/HST Net Tax Owing / (Refund)", "='10. GST-HST'!C28", None),
    ("cca", "money", "CCA Claimed This Year (reduces taxable income above — apply manually if not yet reflected)",
     "='6. CCA Continuity'!H13", None),
    ("sred", "money", "SR&ED Investment Tax Credit Estimate (of which refundable: see Credits tab)", f"={CR}!C9", None),
    ("prov", "money", "Provincial Credit Estimate", f"={CR}!C14", None),
    (None, None, None, None, None),
    ("h7", "header", "7. PLANNING FLAGS TO DISCUSS WITH YOUR ACCOUNTANT", None, None),
    ("f1", "flag", None, "=IF(B18>0,\"• Passive income is grinding the SBD limit — consider moving investments to a holding company or reducing corporate investment income.\",\"\")", None),
    ("f2", "flag", None, "=IF(COUNTIF('8. Shareholders & TOSI'!I5:I20,\"Not Excluded - TOSI Risk\")>0,\"• One or more shareholders flagged for TOSI risk — dividends to them may be taxed at top marginal rate.\",\"\")", None),
    ("f3", "flag", None, "=IF({cda_cf}>0,\"• Unused Capital Dividend Account balance — a tax-free capital dividend may be available.\",\"\")", None),
    ("f4", "flag", None, f"=IF(AND(B18>0,{PY}!C30=\"\"),\"• SBD grind uses current-year investment income as a proxy — enter the prior-year adjusted AAII on '5. Prior-Year Tax Attributes'.\",\"\")", None),
    ("f5", "flag", None, "=IF({p4}>{refund},\"• Part IV tax exceeds this year's dividend refund — the difference sits in RDTOH until taxable dividends are paid.\",\"\")", None),
    ("f6", "flag", None, "=IF({eedd}>0,\"• Eligible dividends exceed GRIP — Part III.1 tax applies unless the s.185.1(2) election is filed.\",\"\")", None),
    ("f7", "flag", None, "=IF({excd}>0,\"• Capital dividend exceeds the CDA — 60% Part III tax unless the s.184(3) election is filed.\",\"\")", None),
    ("f8", "flag", None, "=IF({unused}>0,\"• Non-refundable credits exceed Part I tax — the excess carries forward and is NOT in the year-end balance.\",\"\")", None),
    ("f9", "flag", None, "=IF({less_cash}>0,\"• Refundable credits exceed Part I tax — the cash refund depends on CRA / the province accepting the claim.\",\"\")", None),
    ("f10", "note", "• Salary vs. dividend mix for each owner-manager should be modelled against personal marginal rates (see the separate Personal Tax module) — corporate tax alone does not determine the optimal mix.", None, None),
]

FIRST_ROW = 27


def resolve_rows():
    rows, r = {}, FIRST_ROW
    for key, *_ in LAYOUT:
        if key:
            rows[key] = r
        r += 1
    return rows


def render(formula, rows):
    return re.sub(r"\{(\w+)\}", lambda m: f"B{rows[m.group(1)]}", formula)


def style_rows_for(dash, path) -> dict[str, int]:
    first_header = dash.Cells(FIRST_ROW, 1).Text
    if first_header == LEGACY_FIRST_HEADER:
        return LEGACY_STYLE_ROWS
    if first_header == LAYOUT[0][2]:
        rows = resolve_rows()
        return {style: rows[key] for style, key in CURRENT_STYLE_KEYS.items()}
    raise RuntimeError(
        f"{path}: Dashboard!A{FIRST_ROW} is {first_header!r} — not a layout this tool recognises."
    )


def rebuild(xl, path: str) -> None:
    wb = xl.Workbooks.Open(path)
    try:
        for sheet, row, label in EXPECTED_LABELS:
            got = wb.Worksheets(sheet).Cells(row, 1).Text
            if got != label:
                raise RuntimeError(f"{path}: {sheet}!A{row} is {got!r}, expected {label!r}")
        dash = wb.Worksheets("Dashboard")
        style_sources = style_rows_for(dash, path)

        # SBD section fixes (rows 17, 18, 22).
        dash.Range("A17").Value = "Adjusted Aggregate Investment Income (current year — Part I investment income + portfolio dividends)"
        dash.Range("B17").Formula = f"=IF(SUMPRODUCT(--({IS}!B52:B60<>0))>0,{IS}!B52+{IS}!B53+{IS}!B54+{IS}!B55,{IS}!B48)"
        dash.Range("C17").Value = "Connected-corporation dividends are excluded. The grind below uses the PRIOR-year figure from '5. Prior-Year Tax Attributes' when entered."
        dash.Range("A18").Value = "Passive-Income Grind (5 × (prior-year adjusted AAII − $50,000), capped; current year used as proxy if prior year blank)"
        dash.Range("B18").Formula = f"=MIN(500000,MAX(0,(IF({PY}!C30=\"\",B17,{PY}!C30)-50000)*5))"
        dash.Range("B22").Formula = (
            "=MIN(B21,IF('1. Entity Setup'!$C$28=\"Yes\",IFERROR(VLOOKUP(\"*\"&B5&\"*\","
            "'7. Associated Corporations'!A5:F9,6,FALSE()),500000),500000))"
        )
        dash.Range("C22").Value = ("If associated, pulls this entity's Schedule 23 allocation by matching its legal name "
                                   "(from Entity Setup) on the Associated Corporations tab; if not found or not associated, "
                                   "defaults to the full $500K (post-grind).")

        # Snapshot style rows to a scratch sheet, then clear everything from row 27 down.
        scratch = wb.Worksheets.Add()
        scratch.Name = "_dash_styles"
        for i, (name, src) in enumerate(style_sources.items(), start=1):
            dash.Range(f"A{src}:D{src}").Copy(scratch.Range(f"A{i}:D{i}"))
            scratch.Rows(i).RowHeight = dash.Rows(src).RowHeight
        style_row = {name: i for i, name in enumerate(style_sources, start=1)}

        last = FIRST_ROW + len(LAYOUT) + 20
        block = dash.Range(f"A{FIRST_ROW}:D{last}")
        block.UnMerge()
        block.Clear()
        for r in range(FIRST_ROW, last + 1):
            dash.Rows(r).RowHeight = 15

        rows = resolve_rows()
        r = FIRST_ROW
        for key, style, label, formula, note in LAYOUT:
            if style:
                src = style_row[style]
                scratch.Range(f"A{src}:D{src}").Copy(dash.Range(f"A{r}:D{r}"))
                dash.Rows(r).RowHeight = scratch.Rows(src).RowHeight
                dash.Range(f"A{r}:D{r}").ClearContents()
                if style in ("flag", "note"):
                    dash.Range(f"A{r}").Value = label if formula is None else None
                    if formula:
                        dash.Range(f"A{r}").Formula = render(formula, rows)
                else:
                    dash.Range(f"A{r}").Value = label
                    if formula:
                        dash.Range(f"B{r}").Formula = render(formula, rows)
                if note:
                    dash.Range(f"C{r}").Value = note
            r += 1

        # Readability: wrap long labels, give notes the workbook's existing note style
        # (Dashboard!C13), and size rows to fit. Merged header/flag rows keep their height.
        note_font = dash.Range("C13").Font
        note_cells = [f"C{rows[k]}" for k, *_, n in LAYOUT if k and n] + ["C17", "C22"]
        for addr in note_cells:
            cell = dash.Range(addr)
            cell.Font.Name = note_font.Name
            cell.Font.Size = note_font.Size
            cell.Font.Italic = note_font.Italic
            cell.Font.Color = note_font.Color
            cell.WrapText = True
            cell.VerticalAlignment = -4108  # xlCenter
        autofit_rows = [17, 18, 19, 20, 21, 22, 23, 24] + [rows[k] for k, style, *_ in LAYOUT
                                       if k and style not in ("header", "flag", "note")]
        for ar in autofit_rows:
            dash.Range(f"A{ar}").WrapText = True
            dash.Rows(ar).AutoFit()
            if dash.Rows(ar).RowHeight < 15:
                dash.Rows(ar).RowHeight = 15

        xl.DisplayAlerts = False
        scratch.Delete()
        xl.CalculateFull()
        wb.Save()
    finally:
        wb.Close(False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("workbooks", nargs="+", type=Path, help="intake workbook(s) to rebuild")
    args = parser.parse_args()

    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for original in args.workbooks:
                original = original.resolve()
                work = Path(tmp) / original.name
                shutil.copy2(original, work)
                rebuild(xl, str(work))
                shutil.copy2(work, original)
                print(f"rebuilt Dashboard in {original}")
    finally:
        xl.Quit()


if __name__ == "__main__":
    main()
