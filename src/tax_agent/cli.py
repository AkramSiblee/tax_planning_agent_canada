"""
Command-line entrypoint. See README.md section 4 for usage examples.

This is the only module in the package allowed to use print() for user-facing output —
everything else uses the logging module (see CLAUDE.md style conventions).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENTS_DIR = REPO_ROOT / "clients"


def _client_intake_path(client_slug: str) -> Path:
    return CLIENTS_DIR / client_slug / "intake.xlsx"


def _client_outputs_dir(client_slug: str) -> Path:
    out = CLIENTS_DIR / client_slug / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def cmd_validate(args: argparse.Namespace) -> int:
    from tax_agent.intake import read_intake, MissingIntakeDataError

    intake_path = _client_intake_path(args.client)
    if not intake_path.exists():
        print(f"No intake file found at {intake_path}. Copy the template first — see README.md section 4, step 1.")
        return 1

    try:
        intake = read_intake(intake_path)
    except MissingIntakeDataError as exc:
        print(f"Intake is missing required data: {exc}")
        return 1

    print(f"Intake for {args.client!r} looks valid:")
    print(f"  Entity: {intake.entity_name}")
    print(f"  Province: {intake.province}")
    print(f"  Tax year: {intake.tax_year}")
    print(f"  Net active business income: {intake.net_active_business_income:,.2f}")
    print(f"  Aggregate investment income: {intake.aggregate_investment_income:,.2f}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from tax_agent.calc import run_calculation
    from tax_agent.intake import read_intake, MissingIntakeDataError

    intake_path = _client_intake_path(args.client)
    if not intake_path.exists():
        print(f"No intake file found at {intake_path}. Copy the template first — see README.md section 4, step 1.")
        return 1

    try:
        intake = read_intake(intake_path)
    except MissingIntakeDataError as exc:
        print(f"Cannot run — intake is missing required data: {exc}")
        return 1

    tax_year = args.tax_year or intake.tax_year
    results = run_calculation(intake, tax_year)

    outputs_dir = _client_outputs_dir(args.client)

    results_dict = dataclasses.asdict(results)
    json_path = outputs_dir / "calculation_results.json"
    json_path.write_text(json.dumps(results_dict, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {json_path}")

    print(f"\nEstimated corporate tax before credits: ${results.corporate_tax.total_tax_before_credits:,.2f}")
    print(f"Estimated year-end position: ${results.estimated_year_end_position:,.2f} "
          f"({'refund' if results.estimated_year_end_position >= 0 else 'owing'})")
    if results.flags:
        print("\nFlags:")
        for f in results.flags:
            print(f"  - {f}")

    if args.skip_narrative:
        print("\n--skip-narrative set: no report generated.")
        return 0

    from tax_agent.llm import LLMConfigError
    from tax_agent.reporting import DocxReportBuilder, generate_recommendations

    try:
        narrative = generate_recommendations(results)
    except LLMConfigError as exc:
        print(f"\nCannot generate the report's recommendations section: {exc}")
        print("Fix your .env, or rerun with --skip-narrative to get calculation_results.json only.")
        return 1

    report_path = outputs_dir / "Tax_Planning_Report.docx"
    DocxReportBuilder(results, narrative).save(report_path)
    print(f"Wrote {report_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tax_agent.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Check an intake workbook without running the full report")
    p_validate.add_argument("--client", required=True, help="Client folder slug under clients/")
    p_validate.set_defaults(func=cmd_validate)

    p_run = sub.add_parser("run", help="Run the calculation engine and generate the report")
    p_run.add_argument("--client", required=True, help="Client folder slug under clients/")
    p_run.add_argument("--tax-year", type=int, default=None, help="Override the rate table year (defaults to the intake's own Tax Year field)")
    p_run.add_argument("--skip-narrative", action="store_true", help="Run the calc engine only — no LLM call, no .docx report")
    p_run.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
