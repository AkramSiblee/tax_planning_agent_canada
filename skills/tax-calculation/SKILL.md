---
name: tax-calculation
description: Every formula in the deterministic calc engine (src/tax_agent/calc/), the real-world tax rule each implements, and the simplifications each one makes. Read this before adding, changing, or debugging any calculated number.
---

# Tax Calculation Engine

All formulas here mirror the ones originally validated in the CCPC intake workbook's
Dashboard tab against a hand-checked sample scenario (Northern Peak Consulting Inc. —
see `tests/fixtures/`). If you change a formula, that regression test must still pass
(or be deliberately updated with a documented reason).

## Small Business Deduction (SBD) — `calc/sbd.py`

- **Passive-income grind**: `reduction = min(500_000, max(0, (aaii - 50_000) * 5))`
  — the federal $500K limit is reduced $5 for every $1 of aggregate investment income
  (AAII) over $50,000, fully eliminated at $150,000 AAII.
- **Taxable-capital grind**: `reduction = min(500_000, max(0, (taxable_capital - 10_000_000) / 40_000_000 * 500_000))`
  — reduces the limit once the associated group's taxable capital employed in Canada
  exceeds $10M, eliminated at $50M.
- **Combined**: the federal limit after grinding is `500_000 - max(passive_reduction, taxcap_reduction)`
  (CRA applies the larger of the two reductions, not both additively).
- **Entity-level limit**: if the corporation is associated with others, its own limit is
  the lesser of the grind-adjusted federal limit and its Schedule 23 allocation — see
  `calc/sbd.py::entity_sbd_limit()`.

**Simplification**: AAII should technically be the *prior* year's figure. This engine
uses the current year's as a proxy unless a `prior_year_aaii_override` is supplied in
the intake. Flag this in any report output.

## Corporate Tax — `calc/corporate_tax.py`

Three income streams, each at a different combined (federal+provincial) rate pulled
from `config/Tax_Rates_<year>.xlsx`:

1. Active business income within the SBD limit → `sb_rate`
2. Active business income above the SBD limit → `general_rate`
3. Aggregate investment income → `general_rate + INVESTMENT_INCOME_FEDERAL_ADDON`
   (`INVESTMENT_INCOME_FEDERAL_ADDON = 0.2367`, a constant approximating the loss of the
   federal general rate reduction plus the refundable Part I tax addition on investment
   income — **not** an exact figure; document this every time it's surfaced in output.)

## RDTOH / GRIP / CDA — `calc/rdtoh_grip_cda.py`

- Non-eligible RDTOH addition this year: `aaii * 0.3067` (the refundable-tax fraction).
- Dividend needed to fully recover an RDTOH balance: `balance / 0.3833`.
- GRIP and CDA are carried-forward balances only in v1 — no current-year addition is
  calculated automatically (e.g., the non-taxable half of a capital gain is not yet
  wired into CDA). If asked to model a CDA addition, treat it as a new function, not a
  patch to the opening-balance passthrough.

## Payroll — `calc/payroll.py`

- Employer CPP and CPP2 contributions match the employee total 1:1.
- Employer EI contribution is `employee_ei_total * 1.4`.
- An owner-manager with >40% voting control is excluded from EI on their own salary —
  this must be flagged in the intake schema (`is_ei_exempt_owner`), not inferred.

## GST/HST — `calc/gst.py`

- Net tax = GST/HST collected on taxable supplies minus total input tax credits (ITCs).
- Meals & entertainment ITCs are restricted to 50% — this is entered by the user in the
  intake, not calculated automatically, since not every meal expense line is
  GST/HST-bearing at the same rate.

## Instalment Threshold — `calc/engine.py::instalments_required()`

Instalments are flagged as required if tax payable exceeded $3,000 in **either** of the
prior two years, tested independently for federal and each province. This is a
forward-looking flag (for next year), separate from the current year's actual balance
owing/refund calculation.

## Every rate comes from `config/Tax_Rates_<year>.xlsx`

Never hardcode a province's rate inside a function. `calc/rates.py::load_rates(year)`
loads the workbook once; every other module calls into it. Clients never see or edit
this file — see `skills/rate-table-maintenance/SKILL.md` for how it gets updated.
