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
uses the current year's adjusted AAII as a proxy unless a `prior_year_aaii_override` is
supplied (intake label "Prior-Year Adjusted Aggregate Investment Income (for SBD grind)"
on tab 5). When the proxy is used and the grind is non-zero, the engine raises a flag.

## Investment Income & Part IV — `calc/investment_income.py`

Used when the intake supplies `investment_detail` (the optional holdco section). Without
it, the single AAII figure is treated as Part I investment income exactly as before.

- **Part I investment income** = interest & passive rents + taxable capital gains. Taxed
  at the investment-income rate (see Corporate Tax below).
- **Dividends received** are deducted under s.112, so they are NOT in Part I income.
- **Adjusted AAII for the grind** = Part I investment income + portfolio dividends
  (s.125(7)). Connected-corporation dividends are excluded.
- **Part IV tax** = 38 1/3% (`part_iv_tax_rate`) of portfolio dividends + this
  corporation's share of each connected payer's dividend refund (an intake input — it
  comes from the payer's Schedule 3 and can't be derived from the recipient's data).
- Part IV on eligible portfolio dividends, and connected Part IV from the payer's
  *eligible* RDTOH, go to eligible RDTOH; all other Part IV goes to non-eligible RDTOH.
- **Non-taxable capital gains** = taxable gains x (1 - inclusion) / inclusion, using
  `capital_gains_inclusion_rate` (1/2) → credits the CDA.

**Simplifications**: no Part IV reduction for non-capital losses; adjusted AAII does not
exclude gains on active-business assets or net capital loss carryovers; gains are
assumed net of same-year capital losses.

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

- Non-eligible RDTOH addition: `part_i_investment_income * 0.3067` + Part IV routed to
  non-eligible RDTOH. Eligible RDTOH addition: Part IV routed to eligible RDTOH.
- Dividend needed to fully recover an RDTOH balance: `balance / 0.3833`.
- **GRIP addition** (`grip_addition()`): `0.72 x ABI above the SBD limit` + eligible
  dividends received (`grip_general_rate_factor`). Simplification: the real Schedule 53
  base is taxable income less SBD income less AAII, which also reflects loss deductions.
- **CDA addition** (`cda_addition()`): non-taxable capital gains + life insurance proceeds
  over ACB. Capital dividends received are not modelled separately.
- Balances in `TaxPoolsResult` are year-end, BEFORE dividends paid in the year.
- The "lesser of" limits in s.129(4) other than 30 2/3% of investment income are not
  modelled (they bind only with losses or foreign tax credits).

## Dividends Paid — `calc/dividends.py`

- **Dividend refund** at 38 1/3% of taxable dividends paid (s.129(1)): eligible dividends
  recover eligible RDTOH only; non-eligible dividends recover non-eligible RDTOH first,
  then any eligible RDTOH left after the eligible-dividend refund.
- **Excessive eligible dividend designation** = eligible dividends paid − year-end GRIP
  (including this year's addition). Part III.1 tax 20% (`part_iii_1_rate`); the extra
  10% for the anti-avoidance case is not modelled.
- **Excessive capital dividend** = capital dividends paid − year-end CDA. Part III tax
  60% (`part_iii_rate`). Simplification: uses year-end CDA, not the CDA on the payment
  date — a gain realized after the dividend was paid would not have counted.
- Both penalty taxes are reported as if NO corrective election (s.185.1(2) / s.184(3)) is
  filed, and the engine flags the election in each case.
- `net_corporate_tax_after_credits` = Part I + Part IV + Part III.1 + Part III −
  dividend refund − credits applied.

## Credits — `calc/corporate_tax.py::apply_credits_to_part_i()`

SR&ED ITC and the provincial credit reduce **Part I tax only**, and never below zero —
they cannot offset Part IV, Part III.1 or Part III tax.

1. Non-refundable credits (SR&ED ITC − its refundable portion, + provincial credit) are
   applied first. Their excess is `unused_credits`: carried forward, excluded from the
   year-end position, and flagged.
2. The refundable SR&ED portion (`sred_itc_refundable`, intake row "Refundable Portion
   of SR&ED ITC ($)") reduces any Part I tax left; the rest is `refundable_itc_refund`,
   paid in cash (s.127.1) and included in the year-end position, with a flag that it
   depends on CRA accepting the claim.

The refundable portion must be between 0 and the total SR&ED ITC (else `ValueError`).
It defaults to 0 — fully non-refundable — when not supplied. The template defaults the
row to the full ITC when "Enhanced 35% Refundable Rate Applies?" is Yes.

**Simplifications**: both credits are applied against combined federal + provincial
Part I tax (not each against its own government's tax); the provincial credit is
always treated as non-refundable.

## Regression scenarios

- `tests/test_calc_engine.py`: Northern Peak Consulting Inc. (opco, 2025). Investment
  income is split by type: the portfolio dividend is taxed under Part IV, and the
  dividend from the connected sister holdco carries Part IV equal to the holdco's refund.
- `tests/test_holdco_scenario.py`: Northern Peak Holdings Inc. (holdco, 2026): split
  investment income, Part IV on portfolio + connected dividends, refund ordering, GRIP
  and CDA additions, and both penalty taxes. Every expected value has its arithmetic
  in a comment next to it.

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
