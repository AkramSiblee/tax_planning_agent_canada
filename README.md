# CCPC Tax Planning Agent (v1 — Business Tax Only)

A local agent that reads a completed CCPC tax intake workbook, runs a deterministic
Canadian corporate-tax calculation engine (all provinces/territories), and produces a
filled workbook plus a Word planning report — using an LLM only to write the plain-language
recommendations, never to do the math.

**Scope of v1:** Business/corporate tax for Canadian-Controlled Private Corporations
(CCPCs) only. Personal tax is a separate module, planned later.

**Runs entirely on your own computer.** No hosting, no server, no client data leaves
your machine except the specific text sent to your chosen LLM provider for the
recommendations section (see "What gets sent to the LLM" below).

---

## 1. Before You Start

Read this whole section once. It explains what the agent does and does not do, so you
don't have to guess later.

- **The tax math is NOT done by the LLM.** All rates, thresholds, and formulas live in
  `config/Tax_Rates_<year>.xlsx` and `src/tax_agent/calc/`. The LLM only writes the narrative
  explanation of results the calc engine already produced.
- **Rates need annual verification.** `config/Tax_Rates_2025.xlsx` is illustrative — verify
  every figure against current CRA and provincial publications before relying on any
  output for a real filing. See `skills/rate-table-maintenance/SKILL.md` for how to update it.
- **This is a planning aid, not a filed return.** Every report generated carries this
  disclaimer. Always have a professional accountant review before acting.
- **You never touch the rates file.** `config/Tax_Rates_<year>.xlsx` holds every rate,
  threshold, and payroll figure — you only ever fill out your own
  `clients/<slug>/intake.xlsx`. Rates get refreshed periodically by whoever maintains
  the agent (often with an LLM/coding assistant's help — see
  `skills/rate-table-maintenance/SKILL.md`), not by you.
- **You must supply your own LLM API key.** There is no default provider configured.
  You choose OpenAI, DeepSeek, or Qwen (or any OpenAI-compatible endpoint) in `.env`.

---

## 2. Requirements

- Python 3.10 or later
- An API key for **one** LLM provider: OpenAI, DeepSeek, or Qwen (Alibaba DashScope)
- Recommended: VS Code with the Claude Code extension, or any editor — the agent itself
  is a plain Python CLI and does not require Claude Code to run.

---

## 3. Setup (one time)

```bash
# 1. From this folder, create a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies and the agent itself (editable install)
pip install -r requirements.txt
pip install -e .

# 3. Copy the environment template and fill in your API key
cp .env.example .env
```

Open `.env` in any text editor and fill in **one** provider block. Leave the others blank.

```ini
# Pick ONE provider and fill in its key. Leave the rest blank.
LLM_PROVIDER=openai          # openai | deepseek | qwen
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=
QWEN_API_KEY=
```

DeepSeek and Qwen both expose OpenAI-compatible endpoints, so the agent uses a single
client under the hood — see `src/tax_agent/llm/README.md` if you want the technical detail.

---

## 4. Running the Agent for a New Client

**Step 1 — Copy the blank intake workbook for this client:**

```bash
mkdir -p clients/<client-slug>
cp clients/_template/CCPC_Tax_Planning_Intake_Workbook.xlsx clients/<client-slug>/intake.xlsx
```

Replace `<client-slug>` with something like `northern-peak-consulting`.

**Step 2 — Fill out `clients/<client-slug>/intake.xlsx` in Excel.**

Open it and complete every yellow input cell, following the instructions on its own
`README` tab. Every province is supported — the province you select on the `1. Entity
Setup` tab drives every rate lookup automatically.

**Step 3 — Run the agent:**

```bash
python -m tax_agent.cli run --client <client-slug>
```

This will:
1. Read `clients/<client-slug>/intake.xlsx`
2. Run the calculation engine (SBD, RDTOH/GRIP/CDA, payroll, GST/HST, instalments)
3. Call your configured LLM to write the planning-recommendations narrative
4. Write `clients/<client-slug>/outputs/Tax_Planning_Report.docx`
5. Write `clients/<client-slug>/outputs/calculation_results.json` (the raw numbers, for your own records or for feeding into other tools)
6. Write `clients/<client-slug>/outputs/Calculation_Results.xlsx` (the same raw numbers as a multi-tab workbook — Summary, SBD, Corporate Tax, Tax Pools, Payroll, GST-HST, Flags — for reviewing in Excel instead of JSON)

**Useful flags:**

```bash
python -m tax_agent.cli run --client <client-slug> --tax-year 2025   # pick a rate-table year
python -m tax_agent.cli run --client <client-slug> --skip-narrative  # calc engine only, no LLM call — still writes the JSON and Excel results, just no .docx
python -m tax_agent.cli validate --client <client-slug>              # sanity-check the intake without running the full report
```

---

## 5. What Gets Sent to the LLM

Only the calculation **results** (numbers, not the client's raw financial statements) —
entity name, province, the computed tax figures, RDTOH/GRIP/CDA balances, and flags like
"TOSI risk" — are sent to your chosen provider to generate the recommendations narrative.
See `src/tax_agent/reporting/narrative.py` for the exact prompt if you want to audit this
yourself before running it on real client data.

---

## 6. Folder Structure

```
tax-planning-agent/
├── README.md                    <- you are here
├── CLAUDE.md                    <- instructions for Claude Code / any coding agent editing this repo
├── .env.example                 <- copy to .env and fill in your API key
├── requirements.txt
├── config/
│   └── Tax_Rates_2025.xlsx       <- all provincial/federal rates — the single source of truth for numbers, maintained separately from client input
├── skills/                      <- SKILL.md files documenting each capability (see below)
├── src/tax_agent/               <- the agent's source code
│   ├── llm/                     <- provider-agnostic LLM client (OpenAI/DeepSeek/Qwen)
│   ├── calc/                    <- the deterministic tax calculation engine
│   ├── intake/                  <- reads the filled Excel workbook into structured data
│   ├── reporting/               <- generates the Word report (python-docx) and the LLM narrative
│   └── cli.py                   <- command-line entrypoint
├── clients/
│   ├── _template/               <- blank intake workbook — copy this per new client
│   └── <client-slug>/           <- created per client: intake.xlsx + outputs/
└── tests/                       <- regression tests, including a full sample scenario
```

---

## 7. Skills Reference

Each subfolder under `skills/` documents one capability in depth — read the relevant one
before modifying that part of the agent:

| Skill | Covers |
|---|---|
| `skills/intake-collection/SKILL.md` | The intake workbook's structure and how the Excel reader maps cells to data |
| `skills/tax-calculation/SKILL.md` | Every formula in the calc engine, with the same caveats as the original workbook |
| `skills/report-generation/SKILL.md` | How the Word report is assembled and how to change its content/layout |
| `skills/rate-table-maintenance/SKILL.md` | How to update `config/Tax_Rates_<year>.xlsx` when CRA/provincial rates change |

---

## 8. Known Limitations (carried over from the original workbook)

- The passive-income grind uses the **current year's** investment income as a stand-in
  for the prior-year AAII test CRA actually applies.
- The investment-income tax rate is an approximation (general rate + a fixed federal
  add-on), not an exact province-by-province figure.
- Taxable capital employed in Canada is approximated as total assets — the real
  definition is more technical.
- No personal-tax integration yet — salary vs. dividend recommendations are qualitative,
  not calculated against real personal marginal rates.

None of this is hidden from the client — every report generated states these limitations
explicitly.
