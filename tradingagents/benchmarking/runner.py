"""Provider-neutral benchmark helpers for full TradingAgents graph runs."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import pathlib
import time
import urllib.request
import uuid
from collections import defaultdict
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.factory import normalize_provider, resolve_provider_bundle


ROLE_ORDER = (
    "market",
    "social",
    "news",
    "fundamentals",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
    "trader",
    "portfolio_manager",
    "risk_reflection",
)


@dataclasses.dataclass(frozen=True)
class ModelSet:
    name: str
    description: str
    agent_model_map: dict[str, str]


MODEL_SETS: dict[str, ModelSet] = {
    "openai_baseline": ModelSet(
        name="openai_baseline",
        description="Current OpenAI baseline: GPT-5.4 Mini analysts and GPT-5.4 synthesis roles.",
        agent_model_map={
            "market": "gpt-5.4-mini",
            "social": "gpt-5.4-mini",
            "news": "gpt-5.4-mini",
            "fundamentals": "gpt-5.4-mini",
            "risk_reflection": "gpt-5.4-mini",
            "bull_researcher": "gpt-5.4",
            "bear_researcher": "gpt-5.4",
            "research_manager": "gpt-5.4",
            "trader": "gpt-5.4",
            "portfolio_manager": "gpt-5.4",
        },
    ),
    "deepseek_kimi": ModelSet(
        name="deepseek_kimi",
        description="OpenRouter preset: DeepSeek V4 Flash analysts, DeepSeek V4 Pro risk, and Kimi K2.6 debate and synthesis roles.",
        agent_model_map={
            "market": "deepseek/deepseek-v4-flash",
            "social": "deepseek/deepseek-v4-flash",
            "news": "deepseek/deepseek-v4-flash",
            "fundamentals": "deepseek/deepseek-v4-flash",
            "risk_reflection": "deepseek/deepseek-v4-pro",
            "bull_researcher": "moonshotai/kimi-k2.6",
            "bear_researcher": "moonshotai/kimi-k2.6",
            "research_manager": "moonshotai/kimi-k2.6",
            "trader": "moonshotai/kimi-k2.6",
            "portfolio_manager": "moonshotai/kimi-k2.6",
        },
    ),
    "anthropic": ModelSet(
        name="anthropic",
        description="Anthropic comparator: Haiku analysts and Sonnet synthesis and risk roles.",
        agent_model_map={
            "market": "claude-haiku-4-5-20251001",
            "social": "claude-haiku-4-5-20251001",
            "news": "claude-haiku-4-5-20251001",
            "fundamentals": "claude-haiku-4-5-20251001",
            "risk_reflection": "claude-sonnet-4-6",
            "bull_researcher": "claude-sonnet-4-6",
            "bear_researcher": "claude-sonnet-4-6",
            "research_manager": "claude-sonnet-4-6",
            "trader": "claude-sonnet-4-6",
            "portfolio_manager": "claude-sonnet-4-6",
        },
    ),
}


def model_set_names() -> list[str]:
    return list(MODEL_SETS)


def load_env_file(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def load_default_env(repo_root: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    values.update(load_env_file(repo_root / ".env"))
    for key, value in values.items():
        if value and key not in os.environ:
            os.environ[key] = value
    return values


@dataclasses.dataclass(frozen=True)
class BenchmarkProviderBundle:
    provider: str
    base_url: str
    api_key: str
    api_key_env: str


def resolve_benchmark_provider_bundle(provider: str) -> BenchmarkProviderBundle:
    bundle = resolve_provider_bundle(provider)
    if not bundle.base_url or not bundle.api_key_env:
        raise SystemExit(f"{provider} does not expose a benchmark-compatible provider bundle.")
    api_key = os.getenv(bundle.api_key_env, "")
    if not api_key:
        raise SystemExit(f"{bundle.api_key_env} is not configured.")
    return BenchmarkProviderBundle(
        provider=bundle.provider,
        base_url=bundle.base_url,
        api_key=api_key,
        api_key_env=bundle.api_key_env,
    )


def fetch_model_catalog(base_url: str, api_key: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return list(payload.get("data", []))


def load_model_catalog(path: pathlib.Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    raise SystemExit(f"Catalog file must contain a JSON list or a top-level 'data' list: {path}")


def price_by_model_from_catalog(catalog: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    prices: dict[str, dict[str, float]] = {}
    for model in catalog:
        model_id = str(model.get("id", ""))
        if not model_id:
            continue
        prices[model_id] = {
            "input_token_rate": float(model.get("input_token_rate") or 0),
            "output_token_rate": float(model.get("output_token_rate") or 0),
            "cached_input_token_rate": float(model.get("cached_input_token_rate") or 0),
        }
    return prices


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "llm_output", None) or {}
    token_usage = usage.get("token_usage") or usage.get("usage") or {}
    input_tokens = token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
    output_tokens = token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0

    if not input_tokens and not output_tokens:
        generations = getattr(response, "generations", None) or []
        for generation_group in generations:
            for generation in generation_group:
                message = getattr(generation, "message", None)
                metadata = getattr(message, "usage_metadata", None) or {}
                input_tokens += int(metadata.get("input_tokens") or 0)
                output_tokens += int(metadata.get("output_tokens") or 0)

    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int((input_tokens or 0) + (output_tokens or 0)),
    }


class BenchmarkTraceCallback(BaseCallbackHandler):
    """Write one JSON event per LLM call."""

    def __init__(
        self,
        event_path: pathlib.Path,
        run_id: str,
        model_set: str,
        price_by_model: dict[str, dict[str, float]],
    ) -> None:
        self.event_path = event_path
        self.run_id = run_id
        self.model_set = model_set
        self.price_by_model = price_by_model
        self._starts: dict[str, dict[str, Any]] = {}
        self.event_path.parent.mkdir(parents=True, exist_ok=True)

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id, metadata=None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        prompt_count = sum(len(group) for group in messages)
        self._record_start(run_id, metadata or {}, prompt_count=prompt_count)

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, run_id, metadata=None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self._record_start(run_id, metadata or {}, prompt_count=len(prompts))

    def on_llm_end(self, response: Any, *, run_id, **kwargs) -> None:  # type: ignore[no-untyped-def]
        started = self._starts.pop(str(run_id), {})
        usage = _extract_usage(response)
        model = started.get("model") or "unknown"
        price = self.price_by_model.get(str(model), {})
        estimated_cost = (
            usage["input_tokens"] * float(price.get("input_token_rate") or 0)
            + usage["output_tokens"] * float(price.get("output_token_rate") or 0)
        )
        event = {
            **started,
            "ended_at": _now_iso(),
            "latency_ms": int((time.monotonic() - float(started.get("_started_monotonic", time.monotonic()))) * 1000),
            **usage,
            "estimated_cost_usd": estimated_cost,
            "error": None,
        }
        event.pop("_started_monotonic", None)
        self._write_event(event)

    def on_llm_error(self, error: BaseException, *, run_id, **kwargs) -> None:  # type: ignore[no-untyped-def]
        started = self._starts.pop(str(run_id), {})
        event = {
            **started,
            "ended_at": _now_iso(),
            "latency_ms": int((time.monotonic() - float(started.get("_started_monotonic", time.monotonic()))) * 1000),
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "error": str(error),
        }
        event.pop("_started_monotonic", None)
        self._write_event(event)

    def _record_start(self, run_id: Any, metadata: dict[str, Any], prompt_count: int) -> None:
        self._starts[str(run_id)] = {
            "run_id": self.run_id,
            "model_set": self.model_set,
            "agent_role": metadata.get("agent_role", "unknown"),
            "model": metadata.get("model_name", "unknown"),
            "started_at": _now_iso(),
            "_started_monotonic": time.monotonic(),
            "prompt_count": prompt_count,
        }

    def _write_event(self, event: dict[str, Any]) -> None:
        with self.event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


AbacusTraceCallback = BenchmarkTraceCallback


def build_cost_summary(event_path: pathlib.Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_estimated_cost_usd": 0.0,
        "by_role": defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}),
        "by_model": defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}),
    }
    if not event_path.exists():
        summary["by_role"] = {}
        summary["by_model"] = {}
        return summary

    for line in event_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        input_tokens = int(event.get("input_tokens") or 0)
        output_tokens = int(event.get("output_tokens") or 0)
        total_tokens = int(event.get("total_tokens") or input_tokens + output_tokens)
        cost = float(event.get("estimated_cost_usd") or 0)
        summary["total_calls"] += 1
        summary["total_input_tokens"] += input_tokens
        summary["total_output_tokens"] += output_tokens
        summary["total_tokens"] += total_tokens
        summary["total_estimated_cost_usd"] += cost
        for bucket_name, key in (("by_role", event.get("agent_role", "unknown")), ("by_model", event.get("model", "unknown"))):
            bucket = summary[bucket_name][key]
            bucket["calls"] += 1
            bucket["input_tokens"] += input_tokens
            bucket["output_tokens"] += output_tokens
            bucket["total_tokens"] += total_tokens
            bucket["estimated_cost_usd"] += cost

    summary["by_role"] = dict(summary["by_role"])
    summary["by_model"] = dict(summary["by_model"])
    return summary


def _section(title: str, body: Any) -> str:
    text = body if isinstance(body, str) else json.dumps(body, indent=2, default=str)
    return f"## {title}\n\n{text.strip() if text else '_No output captured._'}\n"


def build_quality_extract(state: dict[str, Any]) -> str:
    investment = state.get("investment_debate_state", {})
    risk = state.get("risk_debate_state", {})
    sections = [
        f"# TradingAgents Quality Extract: {state.get('company_of_interest')} ({state.get('trade_date')})\n",
        _section("Market Analyst", state.get("market_report", "")),
        _section("Social Analyst", state.get("sentiment_report", "")),
        _section("News Analyst", state.get("news_report", "")),
        _section("Fundamentals Analyst", state.get("fundamentals_report", "")),
        _section("Bull Researcher", investment.get("bull_history", "")),
        _section("Bear Researcher", investment.get("bear_history", "")),
        _section("Research Manager", investment.get("judge_decision", "")),
        _section("Trader", state.get("trader_investment_decision", state.get("trader_investment_plan", ""))),
        _section(
            "Risk Management",
            {
                "aggressive": risk.get("aggressive_history", ""),
                "neutral": risk.get("neutral_history", ""),
                "conservative": risk.get("conservative_history", ""),
                "judge": risk.get("judge_decision", ""),
            },
        ),
        _section("Portfolio Manager", state.get("final_trade_decision", "")),
    ]
    return "\n".join(sections)


def _write_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _run_one(
    ticker: str,
    analysis_date: str,
    provider: str,
    model_set: ModelSet,
    output_dir: pathlib.Path,
    price_by_model: dict[str, dict[str, float]],
    selected_analysts: list[str],
    llm_max_tokens: int | None = None,
) -> pathlib.Path:
    run_id = f"{analysis_date}_{ticker}_{model_set.name}_{uuid.uuid4().hex[:8]}"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    event_path = run_dir / "llm_events.jsonl"
    callback = BenchmarkTraceCallback(event_path, run_id, model_set.name, price_by_model)
    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": provider,
            "agent_model_map": model_set.agent_model_map,
            "results_dir": str(run_dir / "tradingagents_results"),
            "data_cache_dir": str(run_dir / "cache"),
            "memory_log_path": str(run_dir / "memory" / "trading_memory.md"),
            "checkpoint_enabled": False,
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
        }
    )
    if llm_max_tokens:
        config["llm_max_tokens"] = int(llm_max_tokens)

    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "ticker": ticker,
            "analysis_date": analysis_date,
            "provider": provider,
            "run_set": model_set.name,
            "model_set": model_set.name,
            "description": model_set.description,
            "selected_analysts": selected_analysts,
            "llm_max_tokens": llm_max_tokens,
            "started_at": _now_iso(),
        },
    )
    _write_json(run_dir / "model_map.json", model_set.agent_model_map)

    graph = TradingAgentsGraph(
        selected_analysts=selected_analysts,
        debug=False,
        config=config,
        callbacks=[callback],
    )
    try:
        final_state, decision = graph.propagate(ticker, analysis_date)
    except Exception as exc:
        _write_json(run_dir / "cost_summary.json", build_cost_summary(event_path))
        (run_dir / "error.txt").write_text(str(exc), encoding="utf-8")
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({"failed_at": _now_iso(), "error": str(exc)})
        _write_json(manifest_path, manifest)
        raise
    logged_state = graph.log_states_dict.get(str(analysis_date), final_state)

    _write_json(run_dir / "final_state.json", logged_state)
    _write_json(run_dir / "raw_final_state.json", final_state)
    (run_dir / "quality_extract.md").write_text(build_quality_extract(logged_state), encoding="utf-8")
    _write_json(run_dir / "cost_summary.json", build_cost_summary(event_path))

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({"completed_at": _now_iso(), "decision": decision})
    _write_json(manifest_path, manifest)
    return run_dir


def run_benchmark(args: argparse.Namespace) -> list[pathlib.Path]:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    load_default_env(repo_root)
    provider = normalize_provider(args.provider or os.getenv("TRADINGAGENTS_LLM_PROVIDER", "abacus"))
    provider_bundle = resolve_benchmark_provider_bundle(provider)
    if args.catalog_file:
        catalog = load_model_catalog(args.catalog_file.expanduser().resolve())
    else:
        catalog = fetch_model_catalog(provider_bundle.base_url, provider_bundle.api_key)
    price_by_model = price_by_model_from_catalog(catalog)
    output_dir = pathlib.Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "provider_model_catalog.json", catalog)

    selected_sets = args.run_set or model_set_names()
    selected_analysts = [item.strip() for item in args.analysts.split(",") if item.strip()]
    run_dirs = []
    for name in selected_sets:
        if name not in MODEL_SETS:
            raise SystemExit(f"Unknown run set: {name}. Valid values: {', '.join(model_set_names())}")
        run_dirs.append(
            _run_one(
                ticker=args.ticker.upper(),
                analysis_date=args.analysis_date,
                provider=provider_bundle.provider,
                model_set=MODEL_SETS[name],
                output_dir=output_dir,
                price_by_model=price_by_model,
                selected_analysts=selected_analysts,
                llm_max_tokens=args.llm_max_tokens,
            )
        )
    return run_dirs


def summarize_run_dirs(run_dirs: list[pathlib.Path], output_path: pathlib.Path | None = None) -> str:
    rows = []
    for run_dir in run_dirs:
        manifest_path = run_dir / "manifest.json"
        cost_path = run_dir / "cost_summary.json"
        if not manifest_path.exists() or not cost_path.exists():
            raise SystemExit(f"Run directory is missing manifest or cost summary: {run_dir}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cost = json.loads(cost_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "run_dir": run_dir,
                "provider": manifest.get("provider", "n/a"),
                "run_set": manifest.get("run_set", manifest.get("model_set", run_dir.name)),
                "decision": manifest.get("decision", "n/a"),
                "calls": int(cost.get("total_calls") or 0),
                "input_tokens": int(cost.get("total_input_tokens") or 0),
                "output_tokens": int(cost.get("total_output_tokens") or 0),
                "total_tokens": int(cost.get("total_tokens") or 0),
                "cost": float(cost.get("total_estimated_cost_usd") or 0),
            }
        )

    lines = [
        "# TradingAgents Benchmark Comparison",
        "",
        "| Provider | Run set | Decision | Calls | Input tokens | Output tokens | Total tokens | Est. cost | Run directory |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {provider} | {run_set} | {decision} | {calls} | {input_tokens:,} | {output_tokens:,} | {total_tokens:,} | ${cost:.6f} | `{run_dir}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "Each run directory contains:",
            "",
            "- `quality_extract.md`: readable analyst reports, debates, synthesis, risk management, and final portfolio output.",
            "- `llm_events.jsonl`: one callback-traced LLM event per call with role, model, token usage, latency, estimated cost, and error field.",
            "- `final_state.json` and `raw_final_state.json`: structured TradingAgents state captured at completion.",
            "- `model_map.json`: exact model routing used for that run.",
        ]
    )
    markdown = "\n".join(lines) + "\n"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    return markdown


def build_summary_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize completed TradingAgents benchmark runs.")
    parser.add_argument("run_dirs", nargs="+", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    return parser


def summary_main() -> int:
    args = build_summary_parser().parse_args()
    markdown = summarize_run_dirs([path.expanduser().resolve() for path in args.run_dirs], args.output)
    print(markdown, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run benchmark-grade TradingAgents graph evaluations.")
    parser.add_argument("--ticker", default="MU")
    parser.add_argument("--analysis-date", default=dt.date.today().isoformat())
    parser.add_argument("--provider")
    parser.add_argument("--run-set", action="append", choices=model_set_names())
    parser.add_argument("--analysts", default="market,social,news,fundamentals")
    parser.add_argument("--llm-max-tokens", type=int)
    parser.add_argument("--catalog-file", type=pathlib.Path)
    parser.add_argument("--output-dir", default="runs/tradingagents-benchmarks")
    return parser


def main() -> int:
    run_dirs = run_benchmark(build_parser().parse_args())
    for run_dir in run_dirs:
        print(run_dir)
    return 0
