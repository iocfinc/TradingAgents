"""Non-interactive TradingAgents analysis runner."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from typing import Any, Sequence

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.reporting import save_report_to_disk

DEFAULT_HEADLESS_ANALYSTS = ("market", "news", "fundamentals")
DEFAULT_HEADLESS_PROVIDER = "openrouter"
DEFAULT_HEADLESS_MODEL = "tencent/hy3-preview"
DEFAULT_HEADLESS_LANGUAGE = "English"


@dataclasses.dataclass(frozen=True)
class HeadlessAnalysisRequest:
    ticker: str
    analysis_date: str | None = None
    output_language: str = DEFAULT_HEADLESS_LANGUAGE
    llm_provider: str = DEFAULT_HEADLESS_PROVIDER
    quick_model: str = DEFAULT_HEADLESS_MODEL
    deep_model: str = DEFAULT_HEADLESS_MODEL
    analysts: Sequence[str] = DEFAULT_HEADLESS_ANALYSTS
    research_depth: int = 1
    output_dir: Path = Path("reports")


@dataclasses.dataclass(frozen=True)
class HeadlessAnalysisResult:
    ticker: str
    analysis_date: str
    output_dir: Path
    report_path: Path
    decision: Any
    final_state: dict[str, Any]


def _today() -> str:
    return dt.date.today().isoformat()


def normalize_analysts(analysts: Sequence[str] | str | None) -> list[str]:
    if analysts is None:
        return list(DEFAULT_HEADLESS_ANALYSTS)
    if isinstance(analysts, str):
        values = analysts.split(",")
    else:
        values = analysts
    normalized = []
    for value in values:
        text = str(value).strip().lower()
        if text:
            normalized.append(text)
    return normalized or list(DEFAULT_HEADLESS_ANALYSTS)


def resolve_headless_request(request: HeadlessAnalysisRequest) -> HeadlessAnalysisRequest:
    return dataclasses.replace(
        request,
        ticker=request.ticker.strip().upper(),
        analysis_date=request.analysis_date or _today(),
        analysts=tuple(normalize_analysts(request.analysts)),
        output_dir=Path(request.output_dir),
    )


def build_headless_config(request: HeadlessAnalysisRequest) -> dict[str, Any]:
    resolved = resolve_headless_request(request)
    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": resolved.llm_provider.lower(),
            "quick_think_llm": resolved.quick_model,
            "deep_think_llm": resolved.deep_model,
            "output_language": resolved.output_language,
            "checkpoint_enabled": False,
            "max_debate_rounds": int(resolved.research_depth),
            "max_risk_discuss_rounds": int(resolved.research_depth),
        }
    )
    return config


def _load_graph_class():
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph


def run_headless_analysis(request: HeadlessAnalysisRequest) -> HeadlessAnalysisResult:
    resolved = resolve_headless_request(request)
    config = build_headless_config(resolved)
    graph_cls = _load_graph_class()
    graph = graph_cls(
        selected_analysts=list(resolved.analysts),
        debug=False,
        config=config,
    )
    final_state, decision = graph.propagate(resolved.ticker, resolved.analysis_date)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = resolved.output_dir / f"{resolved.ticker}_{timestamp}"
    report_path = save_report_to_disk(final_state, resolved.ticker, run_dir)
    return HeadlessAnalysisResult(
        ticker=resolved.ticker,
        analysis_date=resolved.analysis_date,
        output_dir=run_dir,
        report_path=report_path,
        decision=decision,
        final_state=final_state,
    )
