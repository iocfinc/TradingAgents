from __future__ import annotations

import pathlib

from tradingagents.headless_runner import (
    DEFAULT_HEADLESS_ANALYSTS,
    DEFAULT_HEADLESS_MODEL,
    HeadlessAnalysisRequest,
    build_headless_config,
    normalize_analysts,
    resolve_headless_request,
    run_headless_analysis,
)


def _final_state() -> dict[str, object]:
    return {
        "market_report": "Market report",
        "sentiment_report": "",
        "news_report": "News report",
        "fundamentals_report": "Fundamentals report",
        "investment_debate_state": {
            "bull_history": "Bull case",
            "bear_history": "Bear case",
            "judge_decision": "Manager decision",
        },
        "trader_investment_plan": "Trader plan",
        "risk_debate_state": {
            "aggressive_history": "Aggressive risk",
            "conservative_history": "Conservative risk",
            "neutral_history": "Neutral risk",
            "judge_decision": "Portfolio decision",
        },
        "final_trade_decision": "Watch",
    }


def test_headless_defaults_use_openrouter_hy3_english_and_today() -> None:
    request = HeadlessAnalysisRequest(ticker="tsm")

    resolved = resolve_headless_request(request)
    config = build_headless_config(request)

    assert resolved.ticker == "TSM"
    assert resolved.analysis_date
    assert tuple(resolved.analysts) == DEFAULT_HEADLESS_ANALYSTS
    assert config["llm_provider"] == "openrouter"
    assert config["quick_think_llm"] == DEFAULT_HEADLESS_MODEL
    assert config["deep_think_llm"] == DEFAULT_HEADLESS_MODEL
    assert config["output_language"] == "English"
    assert config["max_debate_rounds"] == 1
    assert config["max_risk_discuss_rounds"] == 1
    assert ".local-state" in config["results_dir"]
    assert ".local-state" in config["data_cache_dir"]


def test_normalize_analysts_falls_back_to_default_for_empty_input() -> None:
    assert normalize_analysts(" market, news ,fundamentals ") == ["market", "news", "fundamentals"]
    assert normalize_analysts("") == list(DEFAULT_HEADLESS_ANALYSTS)


def test_headless_run_calls_graph_and_writes_report(
    monkeypatch,
    tmp_path: pathlib.Path,
) -> None:
    captured: dict[str, object] = {}

    class FakeGraph:
        def __init__(self, selected_analysts, debug, config):  # type: ignore[no-untyped-def]
            captured["selected_analysts"] = selected_analysts
            captured["debug"] = debug
            captured["config"] = config

        def propagate(self, ticker: str, analysis_date: str):  # type: ignore[no-untyped-def]
            captured["ticker"] = ticker
            captured["analysis_date"] = analysis_date
            return _final_state(), "Watch"

    monkeypatch.setattr("tradingagents.headless_runner._load_graph_class", lambda: FakeGraph)

    result = run_headless_analysis(
        HeadlessAnalysisRequest(
            ticker="tsm",
            analysis_date="2026-06-18",
            output_dir=tmp_path,
        )
    )

    assert captured["selected_analysts"] == ["market", "news", "fundamentals"]
    assert captured["debug"] is False
    assert captured["ticker"] == "TSM"
    assert captured["analysis_date"] == "2026-06-18"
    assert captured["config"]["llm_provider"] == "openrouter"
    assert result.decision == "Watch"
    assert result.report_path.name == "complete_report.md"
    assert result.report_path.exists()
    assert result.output_dir.parent == tmp_path
    assert (result.output_dir / "1_analysts" / "market.md").read_text(encoding="utf-8") == "Market report"
