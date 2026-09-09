# Instructions for Claude Code (or any coding agent) working in this repository

This file is read by Claude Code automatically when this folder is opened. If you are a
human, read `README.md` instead — this file is written for an AI coding assistant
maintaining or extending the agent.

## What this project is

A local Python agent that calculates Canadian corporate (CCPC) tax from a completed
Excel intake workbook and writes a Word planning report. It is used by BIZINFOGRAPH to
serve accounting/finance clients. There is a **separate, not-yet-built Personal Tax
module** — do not add personal-tax logic here unless explicitly asked; keep the two
domains separate per the original design decision.

## Non-negotiable architectural rule

**The LLM never computes a tax number.** Every dollar figure in any output must come
from `src/tax_agent/calc/`, not from a model completion. If you are asked to add a new
calculated field, add it to the calc engine as a plain Python function with unit tests —
never by asking the LLM to "estimate" or "calculate" it in a prompt. The LLM's only job
is turning already-computed numbers into readable prose (see `reporting/narrative.py`).
If you find yourself writing a prompt that asks the model to do arithmetic, stop and add
a calc function instead.

## Provider-agnostic LLM client

OpenAI, DeepSeek, and Qwen (via Alibaba DashScope's OpenAI-compatible mode) are all
callable through the **same** `openai` Python SDK, just pointed at a different
`base_url`. Do not add separate SDKs per provider — extend
`src/tax_agent/llm/client.py`'s `PROVIDER_CONFIG` dict instead. If a new provider isn't
OpenAI-API-compatible, that's the one case where a new adapter file is justified — ask
before adding one.

## Rate tables are a spreadsheet, not code — and clients never touch them

Provincial/federal rates, thresholds, and CPP/EI figures live in
`config/Tax_Rates_<year>.xlsx`, never hardcoded inside `calc/` functions and never in
YAML. This file is maintained by whoever runs the agent — or by you, if asked to
"refresh the tax rates" — using web search to find the current CRA/provincial figures,
then editing that spreadsheet's cells directly. Clients only ever fill out their own
`clients/<slug>/intake.xlsx`; they never see or edit the rates file. See
`skills/rate-table-maintenance/SKILL.md` before touching any rate, and follow its
citation requirements (Source + Last Verified columns) every time you change a value.

## Testing expectations

`tests/fixtures/northern_peak_sample.xlsx` is a fully filled, hand-verified sample
scenario (an Alberta CCPC with an associated holdco, multi-province operations, TOSI
risk, SR&ED, etc.) with known-correct expected outputs baked into
`tests/test_calc_engine.py`. Any change to `calc/` must keep those assertions passing.
If a change is supposed to alter one of those numbers, update the test's expected value
**and** explain why in the commit message/PR description — a silent change to a tax
number is exactly the kind of bug this test suite exists to catch.

## Style conventions

- Python 3.10+, type hints on every public function.
- Every function in `calc/` gets a docstring stating which real-world tax rule it
  implements and any simplification it makes (see existing functions for the pattern —
  they carry the same caveats as the original Excel workbook's Dashboard tab).
- No print statements in library code — use the `logging` module. `cli.py` is the only
  place user-facing console output belongs.
- Keep `reporting/` (document generation) and `calc/` (math) strictly separate. A
  report-generation change should never require touching a calc function, and vice versa.

## Before committing a change to rates or formulas

1. Run `pytest tests/ -v` — all tests must pass.
2. If you changed a rate, note the source (e.g., "per CRA T4012 2026, effective March
   2026") in that value's Source column on the rates workbook — never a bare number with no citation.
3. Do not remove or soften any of the illustrative-rate disclaimers in `README.md`,
   the SKILL.md files, or the generated report template — these are intentional and
   protect both the firm and the client.
