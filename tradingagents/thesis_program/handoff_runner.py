from __future__ import annotations

import json
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


class HandoffAnalysisError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def load_analysis_queue(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        queue = payload.get("analysis_requests", [])
        if not isinstance(queue, list):
            raise ValueError("analysis_requests must be a list.")
        return queue
    if isinstance(payload, list):
        return payload
    raise ValueError("Handoff file must be a JSON object or list.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _diagnostics_for_state(
    final_state: Any,
    chunks_seen: int,
) -> dict[str, Any]:
    if isinstance(final_state, dict):
        return {
            "chunks_seen": chunks_seen,
            "last_state_keys": sorted(str(key) for key in final_state.keys()),
        }
    return {
        "chunks_seen": chunks_seen,
        "last_state_keys": [],
        "last_state_type": type(final_state).__name__ if final_state is not None else None,
    }


def _execution_config_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "llm_provider": config.get("llm_provider"),
        "quick_think_llm": config.get("quick_think_llm"),
        "deep_think_llm": config.get("deep_think_llm"),
        "agent_model_map": config.get("agent_model_map", {}),
        "provider_bundle_override": config.get("provider_bundle_override"),
        "llm_timeout_seconds": config.get("llm_timeout_seconds"),
        "max_recur_limit": config.get("max_recur_limit"),
    }


def _stream_to_final_state(
    graph: TradingAgentsGraph,
    init_state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    final_state: Any = None
    chunks_seen = 0
    for chunk in graph.graph.stream(init_state, **graph.propagator.get_graph_args()):
        chunks_seen += 1
        final_state = chunk

    diagnostics = _diagnostics_for_state(final_state, chunks_seen)
    if final_state is None:
        raise HandoffAnalysisError(
            "TradingAgents graph produced no stream chunks; final_trade_decision was unavailable.",
            diagnostics,
        )
    if not isinstance(final_state, dict):
        raise HandoffAnalysisError(
            "TradingAgents graph completed with a non-dict final state; "
            "final_trade_decision was unavailable.",
            diagnostics,
        )

    final_trade_decision = final_state.get("final_trade_decision")
    if not isinstance(final_trade_decision, str) or not final_trade_decision.strip():
        raise HandoffAnalysisError(
            "TradingAgents graph completed without final_trade_decision; "
            f"last_state_keys={diagnostics['last_state_keys']}.",
            diagnostics,
        )

    return final_state, diagnostics


def _supersede_stale_error(request_dir: Path) -> None:
    error_path = request_dir / "analysis_error.json"
    if not error_path.exists():
        return
    error_path.replace(request_dir / "analysis_error.superseded.json")


def _load_existing_completed_result(request_dir: Path) -> dict[str, Any] | None:
    result_path = request_dir / "analysis_result.json"
    if not result_path.exists():
        return None
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if payload.get("status") != "completed":
        return None
    _supersede_stale_error(request_dir)
    return payload


def run_thesis_handoff(
    handoff_file: str | Path,
    output_root: str | Path = "runs/thesis-handoff-analysis",
    limit: int | None = None,
    dry_run: bool = False,
    llm_timeout_seconds: int | None = None,
    analysis_timeout_seconds: int | None = None,
) -> list[dict[str, Any]]:
    queue = load_analysis_queue(handoff_file)
    if limit is not None:
        queue = queue[:limit]
    if dry_run:
        return queue

    results: list[dict[str, Any]] = []
    for request in queue:
        ticker = str(request["ticker"])
        analysis_date = str(request["analysis_date"])
        request_dir = (
            Path(output_root)
            / f"{int(request['priority_rank']):02d}_{ticker}_{analysis_date}"
        )
        request_dir.mkdir(parents=True, exist_ok=True)
        existing_result = _load_existing_completed_result(request_dir)
        if existing_result is not None:
            results.append(existing_result)
            _write_json(
                request_dir / "analysis_progress.json",
                {
                    "ticker": ticker,
                    "analysis_date": analysis_date,
                    "priority_rank": request["priority_rank"],
                    "status": "completed",
                    "completed_at": _utc_now(),
                    "result_path": str(request_dir / "analysis_result.json"),
                    "resume_mode": "existing_result",
                },
            )
            continue
        diagnostics: dict[str, Any] = {"chunks_seen": 0, "last_state_keys": []}
        execution_config: dict[str, Any] = {}
        progress_path = request_dir / "analysis_progress.json"
        _write_json(
            request_dir / "handoff_request.json",
            {
                "ticker": ticker,
                "analysis_date": analysis_date,
                "priority_rank": request["priority_rank"],
                "selected_analysts": request.get("selected_analysts", []),
                "thesis_summary": request.get("thesis_summary", ""),
            },
        )
        _write_json(
            progress_path,
            {
                "ticker": ticker,
                "analysis_date": analysis_date,
                "priority_rank": request["priority_rank"],
                "status": "running",
                "started_at": _utc_now(),
                "llm_timeout_seconds": llm_timeout_seconds,
                "analysis_timeout_seconds": analysis_timeout_seconds,
            },
        )
        try:
            config = DEFAULT_CONFIG.copy()
            config["results_dir"] = str(request_dir / "results")
            config["data_cache_dir"] = str(request_dir / "cache")
            config["memory_log_path"] = str(
                request_dir / "memory" / "trading_memory.md"
            )
            if llm_timeout_seconds is not None:
                config["llm_timeout_seconds"] = int(llm_timeout_seconds)
            execution_config = _execution_config_summary(config)
            progress_payload = json.loads(progress_path.read_text(encoding="utf-8"))
            progress_payload["execution_config"] = execution_config
            _write_json(progress_path, progress_payload)
            selected_analysts = list(
                request.get(
                    "selected_analysts",
                    ["market", "social", "news", "fundamentals"],
                )
            )
            graph = TradingAgentsGraph(
                selected_analysts=selected_analysts,
                debug=True,
                config=config,
            )
            init_state = graph.propagator.create_initial_state(
                ticker,
                analysis_date,
                past_context=str(request.get("thesis_summary", "")),
            )
            previous_handler = None
            if analysis_timeout_seconds is not None:
                def _timeout_handler(signum, frame):
                    raise TimeoutError(
                        f"Analysis timed out after {int(analysis_timeout_seconds)} seconds."
                    )

                previous_handler = signal.getsignal(signal.SIGALRM)
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(int(analysis_timeout_seconds))
            try:
                final_state, diagnostics = _stream_to_final_state(graph, init_state)
            finally:
                if analysis_timeout_seconds is not None:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, previous_handler)
            rating = graph.process_signal(final_state["final_trade_decision"])
            result_payload = {
                "ticker": ticker,
                "analysis_date": analysis_date,
                "priority_rank": request["priority_rank"],
                "status": "completed",
                "rating": rating,
                "final_trade_decision": final_state["final_trade_decision"],
                "diagnostics": diagnostics,
                "execution_config": execution_config,
            }
            _supersede_stale_error(request_dir)
            _write_json(request_dir / "analysis_result.json", result_payload)
            _write_json(
                progress_path,
                {
                    "ticker": ticker,
                    "analysis_date": analysis_date,
                    "priority_rank": request["priority_rank"],
                    "status": "completed",
                    "completed_at": _utc_now(),
                    "diagnostics": diagnostics,
                    "execution_config": execution_config,
                    "result_path": str(request_dir / "analysis_result.json"),
                },
            )
            results.append(result_payload)
        except Exception as exc:
            diagnostics = getattr(exc, "diagnostics", diagnostics)
            error_payload = {
                "ticker": ticker,
                "analysis_date": analysis_date,
                "priority_rank": request["priority_rank"],
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "thesis_summary": request.get("thesis_summary", ""),
                "diagnostics": diagnostics,
                "execution_config": execution_config,
            }
            _write_json(request_dir / "analysis_error.json", error_payload)
            _write_json(
                progress_path,
                {
                    "ticker": ticker,
                    "analysis_date": analysis_date,
                    "priority_rank": request["priority_rank"],
                    "status": "failed",
                    "failed_at": _utc_now(),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "diagnostics": diagnostics,
                    "execution_config": execution_config,
                    "error_path": str(request_dir / "analysis_error.json"),
                },
            )
            results.append(error_payload)
            continue
    return results
