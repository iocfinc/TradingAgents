from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tradingagents.thesis_program.handoff import build_tradingagents_handoff
from tradingagents.thesis_program.notion_payloads import build_notion_payload
from tradingagents.thesis_program.scoring import rank_research_positions
from tradingagents.thesis_program.seed_data import load_seed_package
from tradingagents.thesis_program.snapshot import build_snapshot
from tradingagents.thesis_program.visuals import render_explorer_html, render_mermaid_graph


def _run_directory(output_root: Path, artifact_slug: str, run_timestamp: str | None) -> Path:
    timestamp = run_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return output_root / artifact_slug / timestamp


def build_thesis_run(
    seed_path: str | Path,
    output_root: str | Path = "runs",
    top_n: int = 5,
    run_timestamp: str | None = None,
) -> Path:
    package = load_seed_package(seed_path)
    ranked = rank_research_positions(package)
    snapshot = build_snapshot(package, ranked)
    handoff = build_tradingagents_handoff(package, ranked, top_n=top_n)
    output_dir = _run_directory(Path(output_root), package.artifact_slug, run_timestamp)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    (output_dir / "evidence_ledger.json").write_text(
        json.dumps([record.model_dump() for record in package.evidence_records], indent=2),
        encoding="utf-8",
    )
    (output_dir / "ranked_opportunities.json").write_text(
        ranked.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "graph.mmd").write_text(render_mermaid_graph(package), encoding="utf-8")
    (output_dir / "explorer.html").write_text(
        render_explorer_html(package, ranked),
        encoding="utf-8",
    )
    (output_dir / "notion_payload.json").write_text(
        json.dumps(build_notion_payload(package, ranked, str(output_dir)), indent=2),
        encoding="utf-8",
    )
    (output_dir / "tradingagents_handoff.json").write_text(
        json.dumps(handoff, indent=2),
        encoding="utf-8",
    )
    (output_dir / "tradingagents_request_queue.json").write_text(
        json.dumps(handoff["analysis_requests"], indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        f"# {package.artifact_label}\n\nArtifacts written to `{output_dir}`.\n",
        encoding="utf-8",
    )
    return output_dir
