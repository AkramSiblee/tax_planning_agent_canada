---
name: report-generation
description: How the Word planning report is assembled from calc engine results, and how the LLM narrative step fits in. Read this before changing report layout/content or the recommendation prompt.
---

# Report Generation

## Two-stage pipeline — do not merge these stages

1. **`calc/engine.py`** produces a plain Python dict/dataclass of every number
   (`CalculationResults`) — entity info, tax breakdown, RDTOH/GRIP/CDA, payroll, GST,
   flags (e.g., `passive_income_grinding: bool`, `tosi_risk_shareholders: list[str]`).
   No LLM involved.
2. **`reporting/narrative.py`** sends *only that results object* (not the client's raw
   financials) to the configured LLM with a prompt asking it to write the
   recommendations section in prose, given the numbers as fixed facts it must not alter.
   **`reporting/docx_report.py`** then assembles the full document: it inserts the
   calc-engine numbers directly into tables (never via the LLM) and drops the LLM's
   returned narrative text into the "Planning Recommendations" section only.

If the LLM's narrative text contains a number that doesn't match `CalculationResults`,
that's a bug in the prompt or a hallucination — `narrative.py` includes a
`_sanity_check_narrative()` pass that flags (does not silently accept) any dollar figure
in the LLM's text that isn't traceable back to `CalculationResults`. Do not remove this
check to make output "cleaner."

## Three output files, not two

`cli.py`'s `run` command writes three files to `clients/<slug>/outputs/`:

1. `calculation_results.json` — raw `CalculationResults`, machine-readable.
2. `Calculation_Results.xlsx` — the same raw numbers as a multi-tab workbook
   (`reporting/excel_report.py::ExcelReportBuilder`), one tab per calc sub-result
   (Summary, SBD, Corporate Tax, Tax Pools, Payroll, GST-HST, Flags). Like the JSON
   file, this is pure calc-engine output — no LLM call, no narrative — so it is written
   even when `--skip-narrative` is passed.
3. `Tax_Planning_Report.docx` — the narrative report described below. Skipped when
   `--skip-narrative` is passed or the LLM call fails.

If `CalculationResults` gains a new field, update both `excel_report.py` and
`docx_report.py` together — they read the same dataclass and should never drift into
showing different numbers for the same run.

## Report structure (mirrors the original hand-built report)

1. Title block (entity name, fiscal year, "planning aid, not filed advice" disclaimer)
2. Executive summary + key-metrics table
3. Entity overview table
4. Current-year tax position (SBD breakdown table, credits/instalments table)
5. RDTOH / GRIP / CDA table
6. Payroll & GST/HST compliance table
7. Planning recommendations (LLM-generated prose, numbered)
8. Limitations & next steps (static text, not LLM-generated — see below)

## The Limitations section is static, not generated

Section 8's text is a hardcoded constant in `docx_report.py`
(`STANDARD_LIMITATIONS_TEXT`), listing the same caveats as `README.md`'s "Known
Limitations." Do not let the LLM write this section — it must be identical across every
report, every client, every run.

## python-docx, not docx-js

This agent runs on a client's own machine via plain Python, so report generation uses
the `python-docx` library, not the Node-based `docx` package used during prototyping in
Claude's sandbox. The two have different APIs — don't copy-paste code between them.

## Formatting conventions

- Font: Calibri throughout (safe, ships with Office, matches the original workbook's
  Arial-adjacent professional look closely enough — swap to Arial in
  `docx_report.py::STYLE_FONT` if the client prefers exact consistency with the
  workbook).
- Navy (`1F3864`) for headings, matching the original workbook and presentation for
  brand consistency across every BIZINFOGRAPH deliverable.
- Currency formatting: always two decimal places, `$#,##0.00`, negative amounts in
  parentheses — apply via `utils.format_currency()`, never an inline f-string, so the
  format stays consistent if it needs to change later.

## Adding a new section

Add a new `_build_<section>()` method to `DocxReportBuilder` in `docx_report.py` and
call it from `build()` in the order you want it to appear. Keep each section's method
self-contained — it should take `CalculationResults` and return nothing but mutated
document state, so sections can be reordered or removed without cross-dependencies.
