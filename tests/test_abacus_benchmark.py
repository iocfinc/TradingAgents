from __future__ import annotations

import json
import pathlib
import uuid
from types import SimpleNamespace

import pytest

from tradingagents.benchmarking.abacus import (
    MODEL_SETS,
    AbacusTraceCallback,
    build_cost_summary,
    build_parser,
    build_quality_extract,
    resolve_benchmark_provider_bundle,
    run_benchmark,
    model_set_names,
    summarize_run_dirs,
)
from tradingagents.benchmarking.report_pdf import build_report_html, build_report_stem, render_run_report
from tradingagents.graph.trading_graph import build_role_llm_specs
from tradingagents.llm_clients.factory import create_llm_client


def test_model_sets_cover_required_roles_without_route_llm() -> None:
    required = set(build_role_llm_specs({"llm_provider": "abacus"}).keys())

    assert model_set_names() == ["openai_baseline", "deepseek_kimi", "anthropic"]
    for model_set in MODEL_SETS.values():
        assert set(model_set.agent_model_map) == required
        assert "route-llm" not in set(model_set.agent_model_map.values())
    assert MODEL_SETS["deepseek_kimi"].agent_model_map["market"] == "deepseek/deepseek-v4-flash"
    assert MODEL_SETS["deepseek_kimi"].agent_model_map["risk_reflection"] == "deepseek/deepseek-v4-pro"
    assert MODEL_SETS["deepseek_kimi"].agent_model_map["portfolio_manager"] == "moonshotai/kimi-k2.6"


def test_trace_callback_writes_usage_and_estimated_cost(tmp_path: pathlib.Path) -> None:
    event_path = tmp_path / "llm_events.jsonl"
    callback = AbacusTraceCallback(
        event_path=event_path,
        run_id="run-1",
        model_set="openai_baseline",
        price_by_model={
            "gpt-5.4-mini": {
                "input_token_rate": 0.00000075,
                "output_token_rate": 0.0000045,
            }
        },
    )
    run_id = uuid.uuid4()

    callback.on_llm_start(
        serialized={},
        prompts=["hello"],
        run_id=run_id,
        metadata={"agent_role": "market", "model_name": "gpt-5.4-mini"},
    )
    callback.on_llm_end(
        SimpleNamespace(
            llm_output={"token_usage": {"prompt_tokens": 100, "completion_tokens": 25}},
            generations=[],
        ),
        run_id=run_id,
    )

    rows = [json.loads(line) for line in event_path.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["agent_role"] == "market"
    assert rows[0]["model"] == "gpt-5.4-mini"
    assert rows[0]["input_tokens"] == 100
    assert rows[0]["output_tokens"] == 25
    assert rows[0]["estimated_cost_usd"] == pytest.approx(0.0001875)


def test_build_cost_summary_aggregates_events(tmp_path: pathlib.Path) -> None:
    event_path = tmp_path / "llm_events.jsonl"
    event_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "agent_role": "market",
                        "model": "gpt-5.4-mini",
                        "latency_ms": 1000,
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                        "estimated_cost_usd": 0.1,
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "agent_role": "market",
                        "model": "gpt-5.4-mini",
                        "latency_ms": 2000,
                        "input_tokens": 50,
                        "output_tokens": 10,
                        "total_tokens": 60,
                        "estimated_cost_usd": 0.05,
                        "error": None,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    summary = build_cost_summary(event_path)

    assert summary["total_calls"] == 2
    assert summary["total_input_tokens"] == 150
    assert summary["total_output_tokens"] == 30
    assert summary["total_estimated_cost_usd"] == pytest.approx(0.15)
    assert summary["by_role"]["market"]["calls"] == 2


def test_build_quality_extract_includes_full_tradingagents_sections() -> None:
    state = {
        "company_of_interest": "MU",
        "trade_date": "2026-05-06",
        "market_report": "Market report text",
        "sentiment_report": "Sentiment report text",
        "news_report": "News report text",
        "fundamentals_report": "Fundamentals report text",
        "investment_debate_state": {
            "bull_history": "Bull case",
            "bear_history": "Bear case",
            "judge_decision": "Research manager view",
        },
        "trader_investment_decision": "Trader plan",
        "risk_debate_state": {
            "aggressive_history": "Aggressive risk",
            "neutral_history": "Neutral risk",
            "conservative_history": "Conservative risk",
            "judge_decision": "Risk judge",
        },
        "final_trade_decision": "Portfolio manager decision",
    }

    markdown = build_quality_extract(state)

    assert "## Market Analyst" in markdown
    assert "## Bull Researcher" in markdown
    assert "## Risk Management" in markdown
    assert "## Portfolio Manager" in markdown
    assert "Portfolio manager decision" in markdown


def test_abacus_client_forwards_role_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("ABACUS_API_KEY", "abacus-test-key")
    monkeypatch.setattr(
        "tradingagents.llm_clients.openai_client.NormalizedChatOpenAI",
        FakeChatOpenAI,
    )

    create_llm_client(
        provider="abacus",
        model="gpt-5.4-mini",
        callbacks=[],
        tags=["role:market"],
        metadata={"agent_role": "market", "model_set": "openai_baseline"},
        max_tokens=1600,
    ).get_llm()

    assert captured["tags"] == ["role:market"]
    assert captured["metadata"]["agent_role"] == "market"
    assert captured["max_tokens"] == 1600


def test_graph_provider_kwargs_forward_max_completion_tokens() -> None:
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {"llm_provider": "abacus", "llm_max_tokens": 900}

    kwargs = graph._get_provider_kwargs()

    assert kwargs["max_completion_tokens"] == 900


def test_benchmark_provider_bundle_uses_openrouter_key_and_url_for_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ABACUS_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")

    bundle = resolve_benchmark_provider_bundle("abacus_ai")

    assert bundle.provider == "openrouter"
    assert bundle.base_url == "https://openrouter.ai/api/v1"
    assert bundle.api_key == "openrouter-test-key"


def test_benchmark_provider_bundle_rejects_missing_provider_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY is not configured"):
        resolve_benchmark_provider_bundle("openrouter")


def test_summarize_run_dirs_writes_comparison_markdown(tmp_path: pathlib.Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"provider": "openrouter", "run_set": "openai_baseline", "model_set": "openai_baseline", "decision": "Hold"}),
        encoding="utf-8",
    )
    (run_dir / "cost_summary.json").write_text(
        json.dumps(
            {
                "total_calls": 2,
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "total_tokens": 150,
                "total_estimated_cost_usd": 0.0123,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "comparison.md"

    markdown = summarize_run_dirs([run_dir], output_path)

    assert "# TradingAgents Benchmark Comparison" in markdown
    assert "| openrouter | openai_baseline | Hold | 2 | 100 | 50 | 150 | $0.012300 |" in markdown
    assert "`quality_extract.md`" in markdown
    assert "exact model routing used for that run" in markdown
    assert output_path.read_text(encoding="utf-8") == markdown


def test_build_report_html_includes_a4_cover_and_sections(tmp_path: pathlib.Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "ticker": "GRAB",
                "decision": "Hold",
                "analysis_date": "2026-05-06",
                "description": "DeepSeek/Kimi test",
                "provider": "openrouter",
                "run_set": "deepseek_kimi",
                "run_id": "run-1",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "cost_summary.json").write_text(
        json.dumps(
            {
                "total_calls": 10,
                "total_tokens": 12345,
                "total_estimated_cost_usd": 0.1234,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "model_map.json").write_text(
        json.dumps({"market": "deepseek-v4-flash", "portfolio_manager": "kimi-k2.6"}),
        encoding="utf-8",
    )
    (run_dir / "quality_extract.md").write_text(
        "# TradingAgents Quality Extract: GRAB\n\n## Market Analyst\n\n**Rating**: Hold",
        encoding="utf-8",
    )

    html = build_report_html(run_dir)

    assert "size: A4" in html
    assert "GRAB<br>Research Packet" in html
    assert "deepseek-v4-flash" in html
    assert "TradingAgents Benchmark Run" in html
    assert "openrouter" in html
    assert "deepseek_kimi" in html
    assert "<h2>Market Analyst</h2>" in html


def test_render_run_report_uses_manifest_metadata_for_output_stem(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "rendered"
    run_dir.mkdir()
    manifest = {
        "ticker": "3067.HK",
        "provider": "openrouter",
        "run_set": "deepseek_kimi",
        "decision": "Underweight",
        "analysis_date": "2026-05-06",
        "description": "Fixture-backed benchmark run",
        "run_id": "run-2",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "cost_summary.json").write_text(
        json.dumps({"total_calls": 1, "total_tokens": 10, "total_estimated_cost_usd": 0.01}),
        encoding="utf-8",
    )
    (run_dir / "model_map.json").write_text(json.dumps({"market": "deepseek/deepseek-v4-flash"}), encoding="utf-8")
    (run_dir / "quality_extract.md").write_text("# TradingAgents Quality Extract\n", encoding="utf-8")

    monkeypatch.setattr("tradingagents.benchmarking.report_pdf.CHROME_PATH", pathlib.Path("/missing/chrome"))

    with pytest.raises(SystemExit, match="Google Chrome not found"):
        render_run_report(run_dir, output_dir)

    html_path = output_dir / f"{build_report_stem(manifest, run_dir.name)}.html"
    assert html_path.exists()
    assert html_path.name == "3067.HK_openrouter_deepseek_kimi_tradingagents_report.html"


def test_run_benchmark_writes_full_artifact_set_from_fixture_catalog(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_catalog = pathlib.Path(__file__).parent / "fixtures" / "openrouter_model_catalog.json"

    class FakeGraph:
        def __init__(self, selected_analysts, debug, config, callbacks):
            self.selected_analysts = selected_analysts
            self.debug = debug
            self.config = config
            self.callbacks = callbacks
            self.log_states_dict: dict[str, dict[str, object]] = {}

        def propagate(self, ticker: str, analysis_date: str):
            callback = self.callbacks[0]
            run_id = uuid.uuid4()
            callback.on_llm_start(
                serialized={},
                prompts=["prompt"],
                run_id=run_id,
                metadata={"agent_role": "market", "model_name": "deepseek/deepseek-v4-flash"},
            )
            callback.on_llm_end(
                SimpleNamespace(
                    llm_output={"token_usage": {"prompt_tokens": 80, "completion_tokens": 20}},
                    generations=[],
                ),
                run_id=run_id,
            )
            final_state = {
                "company_of_interest": ticker,
                "trade_date": analysis_date,
                "market_report": "Market report text",
                "sentiment_report": "Sentiment report text",
                "news_report": "News report text",
                "fundamentals_report": "Fundamentals report text",
                "investment_debate_state": {
                    "bull_history": "Bull case",
                    "bear_history": "Bear case",
                    "judge_decision": "Research manager view",
                },
                "trader_investment_decision": "Trader plan",
                "risk_debate_state": {
                    "aggressive_history": "Aggressive risk",
                    "neutral_history": "Neutral risk",
                    "conservative_history": "Conservative risk",
                    "judge_decision": "Risk judge",
                },
                "final_trade_decision": "Hold",
            }
            self.log_states_dict[analysis_date] = final_state
            return final_state, "Hold"

    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setattr("tradingagents.benchmarking.runner.TradingAgentsGraph", FakeGraph)

    args = build_parser().parse_args(
        [
            "--ticker",
            "grab",
            "--analysis-date",
            "2026-05-06",
            "--provider",
            "openrouter",
            "--run-set",
            "deepseek_kimi",
            "--catalog-file",
            str(fixture_catalog),
            "--output-dir",
            str(tmp_path / "runs" / "tradingagents-benchmarks"),
        ]
    )

    run_dirs = run_benchmark(args)

    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert run_dir.parent.name == "tradingagents-benchmarks"
    for artifact in (
        "manifest.json",
        "model_map.json",
        "llm_events.jsonl",
        "cost_summary.json",
        "final_state.json",
        "raw_final_state.json",
        "quality_extract.md",
    ):
        assert (run_dir / artifact).exists(), artifact

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider"] == "openrouter"
    assert manifest["run_set"] == "deepseek_kimi"
    assert manifest["ticker"] == "GRAB"

    model_map = json.loads((run_dir / "model_map.json").read_text(encoding="utf-8"))
    assert model_map["market"] == "deepseek/deepseek-v4-flash"
    assert model_map["portfolio_manager"] == "moonshotai/kimi-k2.6"

    catalog = json.loads((run_dir.parent / "provider_model_catalog.json").read_text(encoding="utf-8"))
    assert catalog[0]["id"] == "deepseek/deepseek-v4-flash"
