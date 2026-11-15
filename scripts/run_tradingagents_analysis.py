#!/usr/bin/env python3
"""Run a TradingAgents analysis without the interactive CLI prompts."""

from __future__ import annotations

import argparse
import pathlib

from tradingagents.headless_runner import (
    DEFAULT_HEADLESS_ANALYSTS,
    DEFAULT_HEADLESS_LANGUAGE,
    DEFAULT_HEADLESS_MODEL,
    DEFAULT_HEADLESS_PROVIDER,
    HeadlessAnalysisRequest,
    normalize_analysts,
    run_headless_analysis,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run headless TradingAgents analysis.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol to analyze, for example TSM or 0700.HK.")
    parser.add_argument("--analysis-date", help="Analysis date in YYYY-MM-DD format. Defaults to today.")
    parser.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("reports"))
    parser.add_argument("--output-language", default=DEFAULT_HEADLESS_LANGUAGE)
    parser.add_argument("--llm-provider", default=DEFAULT_HEADLESS_PROVIDER)
    parser.add_argument("--quick-model", default=DEFAULT_HEADLESS_MODEL)
    parser.add_argument("--deep-model", default=DEFAULT_HEADLESS_MODEL)
    parser.add_argument("--analysts", default=",".join(DEFAULT_HEADLESS_ANALYSTS))
    parser.add_argument("--research-depth", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_headless_analysis(
        HeadlessAnalysisRequest(
            ticker=args.ticker,
            analysis_date=args.analysis_date,
            output_language=args.output_language,
            llm_provider=args.llm_provider,
            quick_model=args.quick_model,
            deep_model=args.deep_model,
            analysts=normalize_analysts(args.analysts),
            research_depth=args.research_depth,
            output_dir=args.output_dir,
        )
    )
    print(f"analysis-date: {result.analysis_date}")
    print(f"output-dir: {result.output_dir}")
    print(f"report: {result.report_path}")
    print(f"decision: {result.decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
