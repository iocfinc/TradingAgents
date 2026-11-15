#!/usr/bin/env python3
"""Compatibility wrapper for the legacy Abacus benchmark summary command."""

from __future__ import annotations

from tradingagents.benchmarking.runner import summary_main


if __name__ == "__main__":
    raise SystemExit(summary_main())
