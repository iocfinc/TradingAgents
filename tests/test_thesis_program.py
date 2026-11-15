import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app
from tradingagents.thesis_program import handoff_runner
from tradingagents.thesis_program.handoff import build_tradingagents_handoff
from tradingagents.thesis_program.notion_payloads import build_notion_payload
from tradingagents.thesis_program.runner import build_thesis_run
from tradingagents.thesis_program.scoring import rank_research_positions
from tradingagents.thesis_program.seed_data import load_seed_package


FIXTURE_PATH = Path("tests/fixtures/tsmc_fab_output_seed.json")


def test_load_seed_package_validates_fixture_shape() -> None:
    package = load_seed_package(FIXTURE_PATH)

    assert package.artifact_slug == "tsmc-fab-output"
    assert {entity.entity_id for entity in package.entities} == {
        "tsmc",
        "asml",
        "tel",
        "entg",
    }


def test_rank_research_positions_orders_asml_first_for_bottleneck_strength() -> None:
    package = load_seed_package(FIXTURE_PATH)

    ranked = rank_research_positions(package)

    assert ranked.positions[0].ticker == "ASML"
    assert ranked.top_bottlenecks[0].entity_id == "asml"


def test_build_notion_payload_contains_summary_and_ranked_table() -> None:
    package = load_seed_package(FIXTURE_PATH)
    ranked = rank_research_positions(package)

    payload = build_notion_payload(package, ranked, run_dir="runs/tsmc-fab-output/demo")

    block_types = [block["type"] for block in payload["blocks"]]
    assert payload["title"].startswith("TSMC Fab Output")
    assert "callout" in block_types
    assert "table" in block_types


def test_build_tradingagents_handoff_preserves_ranked_analysis_order() -> None:
    package = load_seed_package(FIXTURE_PATH)
    ranked = rank_research_positions(package)

    handoff = build_tradingagents_handoff(package, ranked, top_n=2)

    assert handoff["artifact_slug"] == "tsmc-fab-output"
    assert [item["ticker"] for item in handoff["securities"]] == ["ASML", "8035.T"]
    assert handoff["analysis_requests"][0]["ticker"] == "ASML"
    assert handoff["analysis_requests"][0]["priority_rank"] == 1


def test_build_thesis_run_writes_required_artifacts(tmp_path: Path) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=3,
        run_timestamp="2026-05-25T12-00-00Z",
    )

    expected = {
        "snapshot.json",
        "evidence_ledger.json",
        "ranked_opportunities.json",
        "graph.mmd",
        "explorer.html",
        "notion_payload.json",
        "tradingagents_handoff.json",
        "tradingagents_request_queue.json",
        "README.md",
    }
    assert expected.issubset({path.name for path in output_dir.iterdir()})

    snapshot = json.loads((output_dir / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["artifact_slug"] == "tsmc-fab-output"


def test_build_tsmc_thesis_command_writes_run_directory(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "build-tsmc-thesis",
            "--seed-file",
            str(FIXTURE_PATH),
            "--output-dir",
            str(tmp_path),
            "--top-n",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert "tradingagents_handoff.json" in result.stdout


def test_run_thesis_handoff_dry_run_reads_analysis_queue(tmp_path: Path) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=2,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-thesis-handoff",
            "--handoff-file",
            str(queue_file),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "1. ASML" in result.stdout
    assert "2. 8035.T" in result.stdout


def test_run_thesis_handoff_persists_failure_artifact(tmp_path: Path, monkeypatch) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=1,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"

    class ExplodingGraph:
        def __init__(self, *args, **kwargs):
            self.propagator = self
            self.graph = self

        def create_initial_state(self, ticker, analysis_date, past_context=""):
            return {
                "ticker": ticker,
                "analysis_date": analysis_date,
                "past_context": past_context,
            }

        def get_graph_args(self):
            return {}

        def stream(self, *args, **kwargs):
            raise RuntimeError("forced network blocker")

    monkeypatch.setattr(handoff_runner, "TradingAgentsGraph", ExplodingGraph)

    results = handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=1,
        dry_run=False,
    )

    failure_file = (
        tmp_path
        / "handoff-results"
        / "01_ASML_2026-05-25"
        / "analysis_error.json"
    )
    assert failure_file.exists()
    assert results[0]["status"] == "failed"
    failure_payload = json.loads(failure_file.read_text(encoding="utf-8"))
    assert failure_payload["ticker"] == "ASML"
    assert failure_payload["status"] == "failed"
    assert failure_payload["error_type"] == "RuntimeError"
    assert "forced network blocker" in failure_payload["error"]
    assert failure_payload["execution_config"]["llm_provider"]


def test_run_thesis_handoff_passes_llm_timeout_into_graph_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=1,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"
    captured: dict[str, object] = {}

    class CapturingGraph:
        def __init__(self, *args, **kwargs):
            captured["config"] = kwargs["config"]
            self.propagator = self
            self.graph = self

        def create_initial_state(self, ticker, analysis_date, past_context=""):
            return {"ticker": ticker, "analysis_date": analysis_date}

        def get_graph_args(self):
            return {}

        def stream(self, *args, **kwargs):
            return iter(
                [
                    {
                        "final_trade_decision": "**Rating**: Hold",
                    }
                ]
            )

        def process_signal(self, signal):
            return "Hold"

    monkeypatch.setattr(handoff_runner, "TradingAgentsGraph", CapturingGraph)

    results = handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=1,
        dry_run=False,
        llm_timeout_seconds=45,
    )

    assert results[0]["rating"] == "Hold"
    assert captured["config"]["llm_timeout_seconds"] == 45


def test_run_thesis_handoff_supersedes_stale_error_after_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=1,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"
    request_dir = tmp_path / "handoff-results" / "01_ASML_2026-05-25"
    request_dir.mkdir(parents=True)
    stale_error = request_dir / "analysis_error.json"
    stale_error.write_text(
        json.dumps({"status": "failed", "error": "previous connection error"}),
        encoding="utf-8",
    )

    class SuccessfulGraph:
        def __init__(self, *args, **kwargs):
            self.propagator = self
            self.graph = self

        def create_initial_state(self, ticker, analysis_date, past_context=""):
            return {"ticker": ticker, "analysis_date": analysis_date}

        def get_graph_args(self):
            return {}

        def stream(self, *args, **kwargs):
            return iter(
                [
                    {
                        "messages": [],
                        "final_trade_decision": "**Rating**: Overweight",
                    }
                ]
            )

        def process_signal(self, signal):
            return "Overweight"

    monkeypatch.setattr(handoff_runner, "TradingAgentsGraph", SuccessfulGraph)

    handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=1,
        dry_run=False,
    )

    assert not stale_error.exists()
    superseded_error = request_dir / "analysis_error.superseded.json"
    assert superseded_error.exists()
    assert "previous connection error" in superseded_error.read_text(encoding="utf-8")
    assert (request_dir / "analysis_result.json").exists()


def test_run_thesis_handoff_persists_incomplete_stream_blocker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=1,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"

    class IncompleteGraph:
        def __init__(self, *args, **kwargs):
            self.propagator = self
            self.graph = self

        def create_initial_state(self, ticker, analysis_date, past_context=""):
            return {"ticker": ticker, "analysis_date": analysis_date}

        def get_graph_args(self):
            return {}

        def stream(self, *args, **kwargs):
            return iter([{"messages": [], "market_report": "partial"}])

    monkeypatch.setattr(handoff_runner, "TradingAgentsGraph", IncompleteGraph)

    results = handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=1,
        dry_run=False,
    )

    failure_file = (
        tmp_path
        / "handoff-results"
        / "01_ASML_2026-05-25"
        / "analysis_error.json"
    )
    assert results[0]["status"] == "failed"
    failure_payload = json.loads(failure_file.read_text(encoding="utf-8"))
    assert failure_payload["status"] == "failed"
    assert failure_payload["error_type"] == "HandoffAnalysisError"
    assert "final_trade_decision" in failure_payload["error"]
    assert failure_payload["execution_config"]["llm_provider"]
    assert failure_payload["diagnostics"]["chunks_seen"] == 1
    assert "market_report" in failure_payload["diagnostics"]["last_state_keys"]


def test_run_thesis_handoff_persists_overall_timeout_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=1,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"

    class SlowGraph:
        def __init__(self, *args, **kwargs):
            self.propagator = self
            self.graph = self

        def create_initial_state(self, ticker, analysis_date, past_context=""):
            return {"ticker": ticker, "analysis_date": analysis_date}

        def get_graph_args(self):
            return {}

        def stream(self, *args, **kwargs):
            time.sleep(2)
            return iter([])

    monkeypatch.setattr(handoff_runner, "TradingAgentsGraph", SlowGraph)

    results = handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=1,
        dry_run=False,
        analysis_timeout_seconds=1,
    )

    failure_file = (
        tmp_path
        / "handoff-results"
        / "01_ASML_2026-05-25"
        / "analysis_error.json"
    )
    assert failure_file.exists()
    assert results[0]["status"] == "failed"
    failure_payload = json.loads(failure_file.read_text(encoding="utf-8"))
    assert failure_payload["status"] == "failed"
    assert "timed out" in failure_payload["error"].lower()


def test_run_thesis_handoff_skips_completed_result_and_ignores_stale_error(
    tmp_path: Path,
) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=1,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"
    handoff_dir = tmp_path / "handoff-results" / "01_ASML_2026-05-25"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "analysis_error.json").write_text(
        json.dumps(
            {
                "ticker": "ASML",
                "analysis_date": "2026-05-25",
                "priority_rank": 1,
                "status": "failed",
                "error": "stale blocker",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (handoff_dir / "analysis_result.json").write_text(
        json.dumps(
            {
                "ticker": "ASML",
                "analysis_date": "2026-05-25",
                "priority_rank": 1,
                "status": "completed",
                "rating": "Underweight",
                "final_trade_decision": "done",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    results = handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=1,
        dry_run=False,
    )

    assert results[0]["status"] == "completed"
    assert results[0]["rating"] == "Underweight"


def test_run_thesis_handoff_continues_past_failed_ticker(tmp_path: Path, monkeypatch) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=2,
        run_timestamp="2026-05-25T12-00-00Z",
    )
    queue_file = output_dir / "tradingagents_request_queue.json"

    class MixedGraph:
        def __init__(self, *args, **kwargs):
            self.propagator = self
            self.graph = self
            self._ticker = None

        def create_initial_state(self, ticker, analysis_date, past_context=""):
            self._ticker = ticker
            return {"ticker": ticker, "analysis_date": analysis_date}

        def get_graph_args(self):
            return {}

        def stream(self, *args, **kwargs):
            if self._ticker == "ASML":
                raise RuntimeError("first ticker failed")
            return iter([{"final_trade_decision": "**Rating**: Hold"}])

        def process_signal(self, signal):
            return "Hold"

    monkeypatch.setattr(handoff_runner, "TradingAgentsGraph", MixedGraph)

    results = handoff_runner.run_thesis_handoff(
        handoff_file=queue_file,
        output_root=tmp_path / "handoff-results",
        limit=2,
        dry_run=False,
    )

    assert len(results) == 2
    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "completed"
    assert results[1]["ticker"] == "8035.T"
