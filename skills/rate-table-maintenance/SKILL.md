---
name: rate-table-maintenance
description: How to update config/Tax_Rates_<year>.xlsx when CRA or a province changes a rate, threshold, or CPP/EI figure. Read this before editing any rate value, or before an LLM/coding assistant is asked to refresh rates for a new tax year.
---

# Rate Table Maintenance

## Why rates live in a spreadsheet, not code or YAML

`config/Tax_Rates_<year>.xlsx` is the single source of truth for every rate, threshold,
and payroll figure the calc engine uses. This is deliberate, and it is a spreadsheet
(not YAML, not hardcoded Python) specifically so that:

- **Clients never touch it.** They only ever fill out their own `clients/<slug>/intake.xlsx`
  — rates are entirely separate from client input, by design.
- **An LLM or coding assistant can maintain it directly**, the same way it would edit any
  other spreadsheet — no code changes, no redeploy, just updated cells with a citation.
- **It's auditable at a glance** — anyone can open it in Excel and see exactly what
  rate was used for a given report, and when it was last verified.

`src/tax_agent/calc/rates.py` reads this file directly via label-based lookup (same
pattern as the intake reader — see `skills/intake-collection/SKILL.md`). There is no
YAML or hardcoded fallback anywhere in the calc engine.

## File structure

Three tabs:

1. **README** — human-facing description of the file's purpose (kept in sync with this
   SKILL.md's summary).
2. **Federal & Payroll** — single-value rows: `Item | Value | Source | Last Verified`.
   Every federal rate/threshold and every CPP/CPP2/EI payroll figure lives here.
3. **Provinces** — one row per province/territory: `Province | General Rate Combined |
   Small Business Rate Combined | SBD Threshold | GST/HST Type | GST/HST Rate | Notes |
   Source | Last Verified`.

**One file per tax year.** `Tax_Rates_2025.xlsx`, `Tax_Rates_2026.xlsx`, etc. Never
overwrite a prior year's file — past client reports must remain reproducible against
the rates actually in effect when they were generated. `load_rates(tax_year)` in
`calc/rates.py` picks the file by year.

## How an LLM/coding assistant should update this file

When asked to "refresh the tax rates" or "update rates for `<year>`":

1. **Copy** the most recent year's file to a new `Tax_Rates_<year>.xlsx` (do not edit
   the prior year in place) — or open `config/build_rates_workbook.py` and run it for a
   brand-new year if no prior file exists yet as a starting scaffold, then immediately
   fill in real values over the illustrative placeholders it generates.
2. **Use web search** to find each rate from an authoritative source: CRA's own
   published corporate tax rate pages, each province's Ministry of Finance site, and
   CRA's CPP/EI contribution rate tables for the payroll figures.
3. **Update the Value column only** — never touch the Item/Province name columns, and
   never touch `src/tax_agent/calc/rates.py` or any other `.py` file to special-case a
   number.
4. **Fill the Source column with the actual citation**, e.g. `"CRA, Corporation tax
   rates, accessed 2026-03-01"` or `"Alberta Treasury Board and Finance, Corporate
   Income Tax, 2026 Budget"` — never leave the placeholder `"Illustrative — verify..."`
   text once a value has actually been verified.
5. **Fill the Last Verified column** with the date the check was done, not the date the
   rate took effect.
6. **Run `pytest tests/ -v`** after any change. The existing regression test uses 2025
   figures — if you're updating 2025's file in place (e.g., fixing a genuine error
   rather than rolling to a new year), the test's expected values may need deliberate
   updates too; if you're adding a new year's file, the 2025 test should be unaffected.

## What "other key tax figures" means, and how to extend this file

If the calc engine grows to need a new figure (e.g., an SR&ED expenditure limit, an
immediate-expensing cap), add it as a new row on the "Federal & Payroll" tab (or a new
column on "Provinces" if it varies by province) — then add its key to the `_FEDERAL_KEYS`
or `_PAYROLL_KEYS` list in `calc/rates.py` so the loader actually picks it up. A value
sitting in the spreadsheet that the loader doesn't read yet is inert — both sides of
that wiring need to be done together.

## Never do this

- Never let a client's intake workbook or session touch this file.
- Never hardcode a rate inside a `calc/` Python function "just for this one case."
- Never delete or silently overwrite a prior year's rates workbook.
- Never leave a changed value with the placeholder source text still in place.
