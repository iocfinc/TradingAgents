#!/usr/bin/env python3
"""Compatibility wrapper for the legacy Abacus benchmark PDF command."""

from __future__ import annotations

from tradingagents.benchmarking.report_pdf import main


if __name__ == "__main__":
    raise SystemExit(main())
