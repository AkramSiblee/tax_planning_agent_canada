---
name: intake-collection
description: How the CCPC intake workbook is structured and how src/tax_agent/intake/excel_reader.py maps its cells to data. Read this before changing anything about what the agent reads from the workbook, or before editing the workbook template itself.
---

# Intake Collection

## The workbook

`clients/_template/CCPC_Tax_Planning_Intake_Workbook.xlsx` is the blank template every
new client copies. It has 17 tabs: a README, a Dashboard (computed, not read by this
agent — it's for the human reviewing the workbook in Excel), 13 numbered intake tabs, a
Province Rate Reference, and a hidden Lists tab (dropdown sources).

The agent only reads the **13 numbered intake tabs**. It ignores the Dashboard, README,
Province Rate Reference, and Lists tabs — those exist for the human filling out the
workbook, not for this agent (the agent has its own rate tables in `config/`, so it does
not need to read the workbook's Province Rate Reference).

## Why label-based lookup, not fixed cell addresses

The workbook's row numbers shift depending on how many sample/blank rows exist on a
given tab (e.g., if someone adds a row to the Shareholders table). **Never hardcode a
cell address like `C12` in the reader.** Instead, `excel_reader.py` searches column A of
each tab for a known label string and reads the value in the adjacent input column. This
is slower but survives structural edits to the workbook that a fixed-address reader
would silently misread.

```python
# The pattern used throughout excel_reader.py:
find_value_by_label(worksheet, label="Primary Province of Operation", value_col=3)
```

If you add a new field to the workbook template, add its label to
`intake/field_labels.py` and a corresponding field to `intake/schema.py` — do not just
read it ad hoc in `excel_reader.py`.

## Tables vs. single-value fields

Two different lookup patterns are needed:

- **Single-value fields** (Entity Setup, GST-HST, Instalments, Credits & Incentives,
  Special Items): one label, one value, found by `find_value_by_label`.
- **Table fields** (Income Statement line items, Balance Sheet, CCA Continuity,
  Associated Corporations, Shareholders & TOSI, Payroll Register): a header row is
  located first, then every row below it until a blank or "TOTAL" row is read into a
  list of dicts. See `find_table_rows()` in `excel_reader.py`.

## Required vs. optional fields

Fields the calc engine cannot proceed without (e.g., province, fiscal year, net active
business income) raise a `MissingIntakeDataError` naming the tab and label. Fields that
are genuinely optional if a client doesn't apply (e.g., foreign income, life insurance)
default to zero/empty rather than erroring — see `schema.py` for which fields are marked
`required=True`.

## Optional holdco section

The bottom of '3. Income Statement' has two optional blocks, read by label
(`field_labels.INVESTMENT_DETAIL` and `field_labels.DIVIDENDS_PAID`, value in column B):
investment income split by type (interest/rents, taxable capital gains, portfolio and
connected dividends, connected-dividend Part IV, life insurance CDA credit) and dividends
paid (eligible, non-eligible, capital).

**A block left entirely blank (or missing, in older workbooks) is read as `None`**, and
the engine falls back to the single AAII figure. This is deliberate — an unused optional
block must never replace a client's AAII with zeros.

## Prior-year AAII

'5. Prior-Year Tax Attributes' has an optional "Prior-Year Adjusted Aggregate Investment
Income (for SBD grind)" row (column C). Blank means *unknown* (not zero): the engine then
uses the current year as a proxy and flags it. A value — including 0 — overrides the proxy.

## Editing the template workbook

Saving with openpyxl drops the cached formula results, so `data_only=True` reads see
blank totals. After any openpyxl edit, re-save the template in Excel (or recalculate via
Excel COM / LibreOffice). Excel stores the cross-sheet dropdowns in an extension format
that openpyxl warns about ("Data Validation extension is not supported") — the reader
is unaffected, but do NOT re-save an Excel-saved template with openpyxl, or the
dropdowns will be lost.
