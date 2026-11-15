# TSMC Fab Output Thesis Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic supply-chain thesis pipeline for TSMC fab output that scores bottlenecks and monopolies, ranks researchable public-market positions, renders local visual and Notion-ready artifacts, and emits a TradingAgents handoff payload.

**Architecture:** Add a focused `tradingagents/thesis_program/` package that loads a local seed corpus, validates entities/evidence/dependencies with Pydantic, computes transparent rules-based scores, assembles a versioned snapshot, and renders HTML, Mermaid, Notion, and handoff artifacts. Expose the pipeline through a new non-interactive CLI command rather than mixing supply-chain logic into the interactive analyzer flow.

**Tech Stack:** Python 3.10+, Pydantic, Typer, JSON, static HTML, Mermaid text, pytest

---

## File Structure

- Create: `tradingagents/thesis_program/__init__.py`
  - public package surface for the thesis program
- Create: `tradingagents/thesis_program/schemas.py`
  - Pydantic models for evidence, entities, dependencies, assessments, ranked opportunities, and full snapshot
- Create: `tradingagents/thesis_program/seed_data.py`
  - local seed loader and validation helpers
- Create: `tradingagents/thesis_program/scoring.py`
  - deterministic bottleneck, monopoly, and thesis-strength scoring
- Create: `tradingagents/thesis_program/snapshot.py`
  - assemble the validated input and scored output into a serializable snapshot
- Create: `tradingagents/thesis_program/visuals.py`
  - Mermaid and self-contained HTML artifact rendering
- Create: `tradingagents/thesis_program/notion_payloads.py`
  - Notion-ready JSON block payload generation
- Create: `tradingagents/thesis_program/handoff.py`
  - TradingAgents shortlist payload generation
- Create: `tradingagents/thesis_program/runner.py`
  - orchestration entrypoint and run-directory writing
- Create: `tests/fixtures/tsmc_fab_output_seed.json`
  - deterministic fixture corpus for one end-to-end TSMC seed run
- Create: `tests/test_thesis_program.py`
  - end-to-end unit coverage for validation, ranking, payload generation, and runner outputs
- Modify: `cli/main.py`
  - add a non-interactive `build-tsmc-thesis` Typer command

### Task 1: Add the failing thesis-program tests and seed fixture

**Files:**
- Create: `tests/fixtures/tsmc_fab_output_seed.json`
- Create: `tests/test_thesis_program.py`

- [ ] **Step 1: Write the seed fixture**

```json
{
  "artifact_slug": "tsmc-fab-output",
  "artifact_label": "TSMC Fab Output",
  "as_of_date": "2026-05-25",
  "methodology_version": "v1",
  "entities": [
    {
      "entity_id": "tsmc",
      "name": "TSMC",
      "entity_type": "fab-operator",
      "role_in_fab_output": "advanced logic foundry",
      "country": "Taiwan",
      "is_public": true,
      "ticker": "TSM",
      "description": "Leading advanced-node semiconductor foundry."
    },
    {
      "entity_id": "asml",
      "name": "ASML",
      "entity_type": "equipment-supplier",
      "role_in_fab_output": "EUV lithography",
      "country": "Netherlands",
      "is_public": true,
      "ticker": "ASML",
      "description": "Primary EUV lithography tool supplier."
    },
    {
      "entity_id": "tel",
      "name": "Tokyo Electron",
      "entity_type": "equipment-supplier",
      "role_in_fab_output": "deposition and etch",
      "country": "Japan",
      "is_public": true,
      "ticker": "8035.T",
      "description": "Critical wafer processing equipment supplier."
    },
    {
      "entity_id": "entg",
      "name": "Entegris",
      "entity_type": "materials-supplier",
      "role_in_fab_output": "filtration and specialty materials",
      "country": "United States",
      "is_public": true,
      "ticker": "ENTG",
      "description": "Supplier of filtration, handling, and specialty materials."
    }
  ],
  "evidence_records": [
    {
      "evidence_id": "ev1",
      "title": "ASML annual report",
      "publisher": "ASML",
      "source_type": "annual-report",
      "published_on": "2026-01-31",
      "url_or_path": "https://example.com/asml-annual-report",
      "tier": 1,
      "claim_text": "EUV tool supply remains capacity-constrained and mission-critical for advanced-node output.",
      "entities": ["asml", "tsmc"],
      "notes": "Tier 1 company disclosure."
    },
    {
      "evidence_id": "ev2",
      "title": "Tokyo Electron process tool overview",
      "publisher": "Tokyo Electron",
      "source_type": "investor-presentation",
      "published_on": "2026-02-14",
      "url_or_path": "https://example.com/tel-process-tools",
      "tier": 1,
      "claim_text": "Deposition and etch remain high-criticality steps in advanced semiconductor output.",
      "entities": ["tel", "tsmc"],
      "notes": "Tier 1 equipment disclosure."
    },
    {
      "evidence_id": "ev3",
      "title": "Entegris filtration note",
      "publisher": "Industry publication",
      "source_type": "industry-analysis",
      "published_on": "2026-03-02",
      "url_or_path": "https://example.com/entg-filtration",
      "tier": 2,
      "claim_text": "High-purity filtration and materials handling remain necessary for advanced fab uptime and yield.",
      "entities": ["entg", "tsmc"],
      "notes": "Tier 2 industry analysis."
    }
  ],
  "dependencies": [
    {
      "edge_id": "edge-asml-tsmc",
      "from_entity_id": "asml",
      "to_entity_id": "tsmc",
      "dependency_type": "lithography",
      "criticality": 10,
      "concentration_score": 10,
      "substitutability_score": 1,
      "evidence_ids": ["ev1"],
      "inference_note": ""
    },
    {
      "edge_id": "edge-tel-tsmc",
      "from_entity_id": "tel",
      "to_entity_id": "tsmc",
      "dependency_type": "etch-deposition",
      "criticality": 8,
      "concentration_score": 6,
      "substitutability_score": 4,
      "evidence_ids": ["ev2"],
      "inference_note": ""
    },
    {
      "edge_id": "edge-entg-tsmc",
      "from_entity_id": "entg",
      "to_entity_id": "tsmc",
      "dependency_type": "materials-filtration",
      "criticality": 7,
      "concentration_score": 5,
      "substitutability_score": 5,
      "evidence_ids": ["ev3"],
      "inference_note": ""
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

```python
import json
from pathlib import Path

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
        "README.md",
    }
    assert expected.issubset({path.name for path in output_dir.iterdir()})

    snapshot = json.loads((output_dir / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["artifact_slug"] == "tsmc-fab-output"
```

- [ ] **Step 3: Run the test file to verify it fails**

Run: `pytest tests/test_thesis_program.py -v`

Expected: `FAIL` with `ModuleNotFoundError: No module named 'tradingagents.thesis_program'`

- [ ] **Step 4: Commit the red test state**

```bash
git add tests/fixtures/tsmc_fab_output_seed.json tests/test_thesis_program.py
git commit -m "test: add thesis program coverage"
```

### Task 2: Implement schemas, seed loading, and scoring until the ranking tests pass

**Files:**
- Create: `tradingagents/thesis_program/__init__.py`
- Create: `tradingagents/thesis_program/schemas.py`
- Create: `tradingagents/thesis_program/seed_data.py`
- Create: `tradingagents/thesis_program/scoring.py`
- Modify: `tests/test_thesis_program.py`

- [ ] **Step 1: Write the minimal package surface**

```python
# tradingagents/thesis_program/__init__.py
"""Deterministic thesis-program tooling for supply-chain opportunity generation."""

from tradingagents.thesis_program.runner import build_thesis_run

__all__ = ["build_thesis_run"]
```

- [ ] **Step 2: Write the core schemas**

```python
# tradingagents/thesis_program/schemas.py
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class EvidenceRecord(BaseModel):
    evidence_id: str
    title: str
    publisher: str
    source_type: str
    published_on: str
    url_or_path: str
    tier: int = Field(ge=1, le=3)
    claim_text: str
    entities: List[str]
    notes: str = ""


class SupplyEntity(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    role_in_fab_output: str
    country: str
    is_public: bool
    ticker: str | None = None
    description: str


class DependencyEdge(BaseModel):
    edge_id: str
    from_entity_id: str
    to_entity_id: str
    dependency_type: str
    criticality: int = Field(ge=1, le=10)
    concentration_score: int = Field(ge=1, le=10)
    substitutability_score: int = Field(ge=1, le=10)
    evidence_ids: List[str]
    inference_note: str = ""


class SeedPackage(BaseModel):
    artifact_slug: str
    artifact_label: str
    as_of_date: str
    methodology_version: str
    entities: List[SupplyEntity]
    evidence_records: List[EvidenceRecord]
    dependencies: List[DependencyEdge]


class BottleneckAssessment(BaseModel):
    entity_id: str
    bottleneck_score: float
    monopoly_score: float
    single_point_of_failure: bool
    failure_mode: str
    thesis_summary: str
    supporting_evidence_ids: List[str]
    open_questions: List[str]


class ResearchPosition(BaseModel):
    position_id: str
    ticker: str
    issuer: str
    supply_chain_role: str
    direction: str
    instrument_type: str
    thesis_strength: float
    bottleneck_linkage: float
    monopoly_linkage: float
    valuation_sensitivity: str
    trigger_monitoring: List[str]
    key_risks: List[str]
    supporting_entity_ids: List[str]
    supporting_evidence_ids: List[str]
    thesis_summary: str


class RankedOpportunitySet(BaseModel):
    artifact_slug: str
    as_of_date: str
    methodology_version: str
    positions: List[ResearchPosition]
    top_bottlenecks: List[BottleneckAssessment]
    top_monopolies: List[BottleneckAssessment]
    unresolved_questions: List[str]
```

- [ ] **Step 3: Write the seed loader**

```python
# tradingagents/thesis_program/seed_data.py
from __future__ import annotations

import json
from pathlib import Path

from tradingagents.thesis_program.schemas import SeedPackage


def load_seed_package(path: str | Path) -> SeedPackage:
    seed_path = Path(path)
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    return SeedPackage.model_validate(payload)
```

- [ ] **Step 4: Write the minimal scoring implementation**

```python
# tradingagents/thesis_program/scoring.py
from __future__ import annotations

from tradingagents.thesis_program.schemas import (
    BottleneckAssessment,
    RankedOpportunitySet,
    ResearchPosition,
    SeedPackage,
)


def _bottleneck_score(criticality: int, concentration: int, substitutability: int) -> float:
    return round((criticality * 0.5) + (concentration * 0.35) + ((11 - substitutability) * 0.15), 2)


def _monopoly_score(concentration: int, substitutability: int) -> float:
    return round((concentration * 0.7) + ((11 - substitutability) * 0.3), 2)


def rank_research_positions(package: SeedPackage) -> RankedOpportunitySet:
    entities_by_id = {entity.entity_id: entity for entity in package.entities}
    evidence_by_id = {record.evidence_id: record for record in package.evidence_records}
    assessments: list[BottleneckAssessment] = []
    positions: list[ResearchPosition] = []

    for edge in package.dependencies:
        source_entity = entities_by_id[edge.from_entity_id]
        bottleneck = _bottleneck_score(
            criticality=edge.criticality,
            concentration=edge.concentration_score,
            substitutability=edge.substitutability_score,
        )
        monopoly = _monopoly_score(
            concentration=edge.concentration_score,
            substitutability=edge.substitutability_score,
        )
        evidence_ids = list(edge.evidence_ids)
        assessments.append(
            BottleneckAssessment(
                entity_id=source_entity.entity_id,
                bottleneck_score=bottleneck,
                monopoly_score=monopoly,
                single_point_of_failure=edge.concentration_score >= 9,
                failure_mode=f"{source_entity.name} disruption reduces {package.artifact_label} output capacity.",
                thesis_summary=f"{source_entity.name} is a critical dependency for {edge.dependency_type}.",
                supporting_evidence_ids=evidence_ids,
                open_questions=[],
            )
        )
        if source_entity.is_public and source_entity.ticker:
            positions.append(
                ResearchPosition(
                    position_id=f"position-{source_entity.entity_id}",
                    ticker=source_entity.ticker,
                    issuer=source_entity.name,
                    supply_chain_role=source_entity.role_in_fab_output,
                    direction="long",
                    instrument_type="equity",
                    thesis_strength=round((bottleneck * 0.6) + (monopoly * 0.4), 2),
                    bottleneck_linkage=bottleneck,
                    monopoly_linkage=monopoly,
                    valuation_sensitivity="Higher fab-output intensity should reinforce strategic supplier value.",
                    trigger_monitoring=[
                        evidence_by_id[evidence_ids[0]].title if evidence_ids else "No evidence title"
                    ],
                    key_risks=["Demand slowdown", "capex delays", "alternative tool adoption"],
                    supporting_entity_ids=[source_entity.entity_id],
                    supporting_evidence_ids=evidence_ids,
                    thesis_summary=f"{source_entity.name} screens as a bottleneck-linked supplier to TSMC fab output.",
                )
            )

    positions.sort(key=lambda item: item.thesis_strength, reverse=True)
    assessments.sort(key=lambda item: item.bottleneck_score, reverse=True)
    monopolies = sorted(assessments, key=lambda item: item.monopoly_score, reverse=True)
    return RankedOpportunitySet(
        artifact_slug=package.artifact_slug,
        as_of_date=package.as_of_date,
        methodology_version=package.methodology_version,
        positions=positions,
        top_bottlenecks=assessments,
        top_monopolies=monopolies,
        unresolved_questions=[],
    )
```

- [ ] **Step 5: Run the targeted tests to verify the ranking tests pass**

Run: `pytest tests/test_thesis_program.py::test_load_seed_package_validates_fixture_shape tests/test_thesis_program.py::test_rank_research_positions_orders_asml_first_for_bottleneck_strength -v`

Expected: `2 passed`

- [ ] **Step 6: Commit the scoring baseline**

```bash
git add tradingagents/thesis_program/__init__.py tradingagents/thesis_program/schemas.py tradingagents/thesis_program/seed_data.py tradingagents/thesis_program/scoring.py
git commit -m "feat: add thesis program scoring baseline"
```

### Task 3: Implement Notion payloads, handoff generation, snapshot assembly, and artifact rendering

**Files:**
- Create: `tradingagents/thesis_program/snapshot.py`
- Create: `tradingagents/thesis_program/visuals.py`
- Create: `tradingagents/thesis_program/notion_payloads.py`
- Create: `tradingagents/thesis_program/handoff.py`
- Modify: `tests/test_thesis_program.py`

- [ ] **Step 1: Add the failing payload-specific assertions if they are still skipped or incomplete**

```python
def test_build_notion_payload_contains_summary_and_ranked_table() -> None:
    package = load_seed_package(FIXTURE_PATH)
    ranked = rank_research_positions(package)

    payload = build_notion_payload(package, ranked, run_dir="runs/tsmc-fab-output/demo")

    assert payload["artifact_slug"] == "tsmc-fab-output"
    assert payload["blocks"][0]["type"] == "callout"
    assert payload["blocks"][-1]["type"] == "bulleted_list"


def test_build_tradingagents_handoff_preserves_ranked_analysis_order() -> None:
    package = load_seed_package(FIXTURE_PATH)
    ranked = rank_research_positions(package)

    handoff = build_tradingagents_handoff(package, ranked, top_n=2)

    assert handoff["recommended_analysis_order"] == ["ASML", "8035.T"]
```

- [ ] **Step 2: Run those tests to verify they fail**

Run: `pytest tests/test_thesis_program.py::test_build_notion_payload_contains_summary_and_ranked_table tests/test_thesis_program.py::test_build_tradingagents_handoff_preserves_ranked_analysis_order -v`

Expected: `FAIL` with import or attribute errors for missing payload builders

- [ ] **Step 3: Implement snapshot, Notion payload, and handoff builders**

```python
# tradingagents/thesis_program/snapshot.py
from __future__ import annotations

from tradingagents.thesis_program.schemas import RankedOpportunitySet, SeedPackage


def build_snapshot(package: SeedPackage, ranked: RankedOpportunitySet) -> dict:
    return {
        "artifact_slug": package.artifact_slug,
        "artifact_label": package.artifact_label,
        "as_of_date": package.as_of_date,
        "methodology_version": package.methodology_version,
        "entities": [entity.model_dump() for entity in package.entities],
        "evidence_records": [record.model_dump() for record in package.evidence_records],
        "dependencies": [edge.model_dump() for edge in package.dependencies],
        "ranked_opportunities": ranked.model_dump(),
    }
```

```python
# tradingagents/thesis_program/notion_payloads.py
from __future__ import annotations

from tradingagents.thesis_program.schemas import RankedOpportunitySet, SeedPackage


def build_notion_payload(package: SeedPackage, ranked: RankedOpportunitySet, run_dir: str) -> dict:
    return {
        "artifact_slug": package.artifact_slug,
        "title": f"{package.artifact_label} Thesis Run - {package.as_of_date}",
        "blocks": [
            {
                "type": "callout",
                "text": f"Top bottleneck: {ranked.top_bottlenecks[0].entity_id} | Top position: {ranked.positions[0].ticker}",
            },
            {
                "type": "table",
                "title": "Ranked Opportunities",
                "rows": [
                    {
                        "ticker": position.ticker,
                        "issuer": position.issuer,
                        "thesis_strength": position.thesis_strength,
                    }
                    for position in ranked.positions
                ],
            },
            {
                "type": "bulleted_list",
                "items": [
                    f"Artifacts: {run_dir}",
                    f"Methodology: {package.methodology_version}",
                ],
            },
        ],
    }
```

```python
# tradingagents/thesis_program/handoff.py
from __future__ import annotations

from tradingagents.thesis_program.schemas import RankedOpportunitySet, SeedPackage


def build_tradingagents_handoff(package: SeedPackage, ranked: RankedOpportunitySet, top_n: int) -> dict:
    chosen = ranked.positions[:top_n]
    return {
        "artifact_slug": package.artifact_slug,
        "as_of_date": package.as_of_date,
        "recommended_analysis_order": [item.ticker for item in chosen],
        "securities": [
            {
                "ticker": item.ticker,
                "issuer": item.issuer,
                "thesis_summary": item.thesis_summary,
                "trigger_monitoring": item.trigger_monitoring,
                "key_risks": item.key_risks,
            }
            for item in chosen
        ],
    }
```

- [ ] **Step 4: Implement the Mermaid and HTML renderers**

```python
# tradingagents/thesis_program/visuals.py
from __future__ import annotations

from tradingagents.thesis_program.schemas import RankedOpportunitySet, SeedPackage


def render_mermaid_graph(package: SeedPackage) -> str:
    lines = ["graph LR"]
    for edge in package.dependencies:
        lines.append(f"    {edge.from_entity_id}[{edge.from_entity_id}] --> {edge.to_entity_id}[{edge.to_entity_id}]")
    return "\n".join(lines) + "\n"


def render_explorer_html(package: SeedPackage, ranked: RankedOpportunitySet) -> str:
    top_rows = "".join(
        f"<tr><td>{position.ticker}</td><td>{position.issuer}</td><td>{position.thesis_strength}</td></tr>"
        for position in ranked.positions
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{package.artifact_label} Explorer</title>
  <style>
    body {{ font-family: Helvetica, Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #ccc; padding: 8px; }}
  </style>
</head>
<body>
  <h1>{package.artifact_label}</h1>
  <p>As of {package.as_of_date}</p>
  <h2>Top Positions</h2>
  <table>
    <thead><tr><th>Ticker</th><th>Issuer</th><th>Thesis Strength</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
</body>
</html>
"""
```

- [ ] **Step 5: Run the payload and rendering tests**

Run: `pytest tests/test_thesis_program.py::test_build_notion_payload_contains_summary_and_ranked_table tests/test_thesis_program.py::test_build_tradingagents_handoff_preserves_ranked_analysis_order -v`

Expected: `2 passed`

- [ ] **Step 6: Commit the payload and rendering layer**

```bash
git add tradingagents/thesis_program/snapshot.py tradingagents/thesis_program/visuals.py tradingagents/thesis_program/notion_payloads.py tradingagents/thesis_program/handoff.py
git commit -m "feat: add thesis program artifacts and handoff payloads"
```

### Task 4: Implement the runner and required artifact writing

**Files:**
- Create: `tradingagents/thesis_program/runner.py`
- Modify: `tests/test_thesis_program.py`

- [ ] **Step 1: Write the failing runner-output test if the full artifact assertion is not already active**

```python
def test_build_thesis_run_writes_required_artifacts(tmp_path: Path) -> None:
    output_dir = build_thesis_run(
        seed_path=FIXTURE_PATH,
        output_root=tmp_path,
        top_n=3,
        run_timestamp="2026-05-25T12-00-00Z",
    )

    assert (output_dir / "explorer.html").exists()
    assert (output_dir / "graph.mmd").exists()
    assert (output_dir / "tradingagents_handoff.json").exists()
```

- [ ] **Step 2: Run the runner test to verify it fails**

Run: `pytest tests/test_thesis_program.py::test_build_thesis_run_writes_required_artifacts -v`

Expected: `FAIL` with missing `build_thesis_run`

- [ ] **Step 3: Implement the end-to-end runner**

```python
# tradingagents/thesis_program/runner.py
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
    ts = run_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return output_root / artifact_slug / ts


def build_thesis_run(
    seed_path: str | Path,
    output_root: str | Path = "runs",
    top_n: int = 5,
    run_timestamp: str | None = None,
) -> Path:
    package = load_seed_package(seed_path)
    ranked = rank_research_positions(package)
    snapshot = build_snapshot(package, ranked)
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
    (output_dir / "explorer.html").write_text(render_explorer_html(package, ranked), encoding="utf-8")
    (output_dir / "notion_payload.json").write_text(
        json.dumps(build_notion_payload(package, ranked, str(output_dir)), indent=2),
        encoding="utf-8",
    )
    (output_dir / "tradingagents_handoff.json").write_text(
        json.dumps(build_tradingagents_handoff(package, ranked, top_n=top_n), indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        f"# {package.artifact_label}\\n\\nArtifacts written to `{output_dir}`.\\n",
        encoding="utf-8",
    )
    return output_dir
```

- [ ] **Step 4: Run the full thesis test file**

Run: `pytest tests/test_thesis_program.py -v`

Expected: `5 passed`

- [ ] **Step 5: Commit the runner**

```bash
git add tradingagents/thesis_program/runner.py
git commit -m "feat: add thesis program runner"
```

### Task 5: Wire the CLI command and verify a real local run

**Files:**
- Modify: `cli/main.py`
- Test: `tests/test_thesis_program.py`

- [ ] **Step 1: Add the failing CLI smoke test**

```python
from typer.testing import CliRunner

from cli.main import app


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
```

- [ ] **Step 2: Run the CLI smoke test to verify it fails**

Run: `pytest tests/test_thesis_program.py::test_build_tsmc_thesis_command_writes_run_directory -v`

Expected: `FAIL` because `build-tsmc-thesis` is not registered yet

- [ ] **Step 3: Add the CLI command**

```python
# cli/main.py
from tradingagents.thesis_program.runner import build_thesis_run


@app.command("build-tsmc-thesis")
def build_tsmc_thesis(
    seed_file: str = typer.Option(..., "--seed-file", help="Path to the seed corpus JSON file."),
    output_dir: str = typer.Option("runs", "--output-dir", help="Root directory for generated thesis artifacts."),
    top_n: int = typer.Option(5, "--top-n", min=1, help="Number of ranked securities to include in the TradingAgents handoff."),
) -> None:
    run_dir = build_thesis_run(
        seed_path=seed_file,
        output_root=output_dir,
        top_n=top_n,
    )
    console.print(f"[green]TSMC thesis artifacts written to {run_dir}[/green]")
    console.print(f"[green]TradingAgents handoff: {run_dir / 'tradingagents_handoff.json'}[/green]")
```

- [ ] **Step 4: Run the CLI smoke test again**

Run: `pytest tests/test_thesis_program.py::test_build_tsmc_thesis_command_writes_run_directory -v`

Expected: `1 passed`

- [ ] **Step 5: Run a real local artifact build**

Run: `python -m cli.main build-tsmc-thesis --seed-file tests/fixtures/tsmc_fab_output_seed.json --output-dir runs --top-n 3`

Expected: console output includes the generated run directory path and `tradingagents_handoff.json`

- [ ] **Step 6: Inspect the generated directory**

Run: `find runs/tsmc-fab-output -maxdepth 2 -type f | sort`

Expected: a fresh timestamped run folder containing `snapshot.json`, `evidence_ledger.json`, `ranked_opportunities.json`, `graph.mmd`, `explorer.html`, `notion_payload.json`, `tradingagents_handoff.json`, and `README.md`

- [ ] **Step 7: Commit the CLI integration**

```bash
git add cli/main.py
git commit -m "feat: expose thesis program via cli"
```

### Task 6: Final verification against the actual goal slice

**Files:**
- Verify: `tradingagents/thesis_program/*.py`
- Verify: `tests/test_thesis_program.py`
- Verify: latest `runs/tsmc-fab-output/<timestamp>/`

- [ ] **Step 1: Run the full targeted test suite**

Run: `pytest tests/test_thesis_program.py -v`

Expected: all thesis-program tests pass

- [ ] **Step 2: Verify the real run artifacts exist**

Run: `find runs/tsmc-fab-output -maxdepth 2 -type f | sort`

Expected: latest run contains all eight required artifact files

- [ ] **Step 3: Verify the ranked handoff order**

Run: `python - <<'PY'
import json
from pathlib import Path
latest = sorted(Path("runs/tsmc-fab-output").glob("*"))[-1]
payload = json.loads((latest / "tradingagents_handoff.json").read_text())
print(payload["recommended_analysis_order"])
PY`

Expected: a deterministic ticker order, with the strongest bottleneck-linked supplier first

- [ ] **Step 4: Verify the Notion payload shape**

Run: `python - <<'PY'
import json
from pathlib import Path
latest = sorted(Path("runs/tsmc-fab-output").glob("*"))[-1]
payload = json.loads((latest / "notion_payload.json").read_text())
print(payload["title"])
print([block["type"] for block in payload["blocks"]])
PY`

Expected: a title plus block types including `callout`, `table`, and `bulleted_list`

- [ ] **Step 5: Commit the final verified slice**

```bash
git add tradingagents/thesis_program cli/main.py tests/test_thesis_program.py tests/fixtures/tsmc_fab_output_seed.json runs/tsmc-fab-output docs/superpowers/plans/2026-05-25-tsmc-fab-output-thesis-program.md
git commit -m "feat: add deterministic tsmc thesis program"
```
