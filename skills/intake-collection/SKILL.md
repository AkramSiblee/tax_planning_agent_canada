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

## Known simplification carried from the original workbook

The Excel Dashboard used this year's investment income as a stand-in for the prior-year
AAII test. The Python reader does the same — it reads only the current intake, with no
mechanism yet to pull a genuine prior-year figure. If a client's prior-year AAII is
known, add it as an explicit override field rather than trying to make the current-year
proxy "smarter" — see the TODO in `schema.py`.
