# TSMC Fab Output Thesis Program Design

## Objective

Build a decision-grade supply-chain thesis program for TSMC fab output that:

- identifies bottlenecks and monopoly-like dependencies
- turns those findings into researchable public-market positions
- produces local visual artifacts plus Notion-syncable payloads
- hands a ranked opportunity set into TradingAgents for deeper single-security analysis

This design keeps the supply-chain thesis logic inside this product repo and uses TradingAgents only for the downstream security-analysis step.

## Current Repo Context

The current `TradingAgents` repo already has:

- the multi-agent research and decision engine
- saved report rendering flows
- benchmark helpers and CLI entrypoints

The current repo does not have:

- a supply-chain evidence schema
- a TSMC fab-output thesis builder
- a bottleneck and monopoly scoring model
- a ranked opportunity handoff format
- a Notion-ready supply-chain artifact pipeline

The new program should therefore be a separate product-side module that prepares structured thesis inputs for existing TradingAgents runs.

## Recommended Approach

### Option 1: Deterministic local thesis builder with static seed corpus

Seed the program with repo-local evidence records and curated entities, build derived rankings and visuals deterministically, then pass shortlisted tickers into TradingAgents.

Pros:

- fast to implement and test
- deterministic outputs
- good fit for local verification and repeatable artifacts

Cons:

- freshness depends on manual evidence refreshes

### Option 2: Hybrid builder with deterministic core plus optional live evidence refresh

Keep the deterministic local artifact pipeline, but allow optional live evidence intake later from filings, IR pages, and industry sources.

Pros:

- preserves a stable local contract
- grows into fresher research over time
- avoids blocking initial delivery on networked intake

Cons:

- requires clearer boundaries between confirmed local evidence and refreshed evidence

### Option 3: Fully live crawling and graph construction

Build the thesis program around web ingestion first, then generate the graph and rankings from live sources every run.

Pros:

- freshest possible output

Cons:

- high implementation risk
- harder to test and verify
- likely to produce brittle runs and provenance gaps

### Recommendation

Use Option 2.

The first implementation should ship a deterministic local thesis builder with explicit evidence provenance, versioned visual artifacts, and a stable TradingAgents handoff. The design should leave a narrow seam for later live evidence refresh without making the initial program dependent on external scraping.

## System Design

### Top-Level Flow

1. Load a repo-local TSMC fab-output seed package.
2. Normalize evidence records, entities, dependencies, and candidate securities.
3. Score each dependency for bottleneck intensity, monopoly concentration, and thesis relevance.
4. Rank researchable public-market positions from those dependency scores.
5. Render visual artifacts and a Notion-ready payload from the same structured snapshot.
6. Emit a TradingAgents handoff file that can be consumed by a follow-on runner for deeper security analysis.

### Module Boundary

Add a new package under `tradingagents/thesis_program/` with focused files:

- `schemas.py`
  - Pydantic models for evidence, entities, dependencies, positions, visual summaries, and handoff payloads
- `seed_data.py`
  - local seed dataset loader for the TSMC fab-output program
- `scoring.py`
  - deterministic bottleneck, monopoly, and opportunity scoring
- `snapshot.py`
  - snapshot assembly and version metadata
- `visuals.py`
  - HTML and Mermaid-oriented visual artifact generation
- `notion_payloads.py`
  - Notion-syncable block payload builder
- `handoff.py`
  - TradingAgents shortlist payload builder
- `runner.py`
  - orchestration entrypoint for end-to-end thesis generation

Add thin CLI wiring rather than embedding logic into the interactive trading CLI.

## Data Model

### Core Records

#### EvidenceRecord

Fields:

- `evidence_id`
- `title`
- `publisher`
- `source_type`
- `published_on`
- `url_or_path`
- `tier`
- `claim_text`
- `entities`
- `notes`

Rules:

- Tier 1: official filings, investor relations, government, patents, company docs
- Tier 2: reputable reporting or industry analysis
- Tier 3: directional clue only, must remain visibly unconfirmed

#### SupplyEntity

Fields:

- `entity_id`
- `name`
- `entity_type`
- `role_in_fab_output`
- `country`
- `is_public`
- `ticker`
- `description`

Examples:

- TSMC
- ASML
- Tokyo Electron
- Applied Materials
- Shin-Etsu Chemical
- GlobalWafers
- Air Liquide
- Entegris

#### DependencyEdge

Fields:

- `edge_id`
- `from_entity_id`
- `to_entity_id`
- `dependency_type`
- `criticality`
- `concentration_score`
- `substitutability_score`
- `evidence_ids`
- `inference_note`

This record is the main bridge between provenance and the rendered supply-chain graph.

#### BottleneckAssessment

Fields:

- `entity_id`
- `bottleneck_score`
- `monopoly_score`
- `single_point_of_failure`
- `failure_mode`
- `thesis_summary`
- `supporting_evidence_ids`
- `open_questions`

#### ResearchPosition

Fields:

- `position_id`
- `ticker`
- `issuer`
- `supply_chain_role`
- `direction`
- `instrument_type`
- `thesis_strength`
- `bottleneck_linkage`
- `monopoly_linkage`
- `valuation_sensitivity`
- `trigger_monitoring`
- `key_risks`
- `supporting_entity_ids`
- `supporting_evidence_ids`

#### RankedOpportunitySet

Fields:

- `artifact_slug`
- `as_of_date`
- `methodology_version`
- `positions`
- `top_bottlenecks`
- `top_monopolies`
- `unresolved_questions`

## Scoring Design

### Bottleneck Score

Composite score from:

- direct fab-output criticality
- low substitutability
- long replacement cycle
- process-step uniqueness
- cross-node dependency count

### Monopoly Score

Composite score from:

- market concentration
- technical uniqueness
- switching cost
- regulatory or IP barriers
- supplier redundancy

### Thesis Strength Score

Composite score from:

- bottleneck linkage
- monopoly linkage
- public-market accessibility
- clarity of causal path from fab output to issuer economics
- evidence quality

The initial version should be rules-based and transparent. No model-generated scoring logic should decide rankings.

## Artifact Outputs

Each run should write a versioned folder under `runs/tsmc-fab-output/<timestamp>/`.

Required outputs:

- `snapshot.json`
  - full structured program state
- `evidence_ledger.json`
  - normalized evidence records
- `ranked_opportunities.json`
  - ranked public-market shortlist
- `graph.mmd`
  - Mermaid graph source
- `explorer.html`
  - single-file local visual explorer
- `notion_payload.json`
  - block payload ready for Notion sync
- `tradingagents_handoff.json`
  - shortlist and rationale for downstream analysis
- `README.md`
  - run summary with paths and methodology version

## Visual Artifact Design

### Explorer HTML

The HTML explorer should show:

- top bottlenecks
- monopoly-like nodes
- entity-to-entity dependency graph
- ranked opportunity table
- unresolved evidence gaps

It should be static and self-contained so it can be inspected locally without a server.

### Mermaid Graph

The Mermaid artifact should provide a simple dependency map that can be pasted into Notion or other docs even when the full HTML explorer is not used.

## Notion Sync Contract

The first implementation should generate a Notion-ready payload, not perform live Notion mutation by default.

Payload sections:

- title and run metadata
- summary callout
- bottleneck table
- monopoly table
- ranked opportunity table
- unresolved questions
- artifact links or relative paths

This keeps the product repo deterministic while leaving room for a later authenticated sync command.

## TradingAgents Handoff Contract

The handoff file should be explicit and narrow.

It should include:

- ranked securities
- one-paragraph thesis per security
- key catalysts and monitoring triggers
- risk summary
- recommended analysis order

Example downstream use:

- choose the top `N` tickers from `tradingagents_handoff.json`
- run existing TradingAgents analysis one ticker at a time
- save those richer single-security reports alongside the thesis run

This preserves the boundary that the thesis program does cross-security discovery and ranking, while TradingAgents performs deeper per-security reasoning.

## CLI Surface

Add a non-interactive command path, for example:

`python -m cli.main build-tsmc-thesis --artifact tsmc-fab-output`

Optional flags:

- `--output-dir`
- `--top-n`
- `--seed-file`

The first version should not require live credentials.

## Testing Strategy

Write tests first for:

- schema validation
- deterministic scoring behavior
- ranked opportunity ordering
- artifact generation
- Notion payload shape
- TradingAgents handoff shape

Use a small repo-local seed fixture so tests do not depend on external APIs.

## Error Handling

The runner should fail clearly when:

- the seed corpus is missing
- evidence references an unknown entity
- ranked opportunities resolve to no public-market positions
- artifact writing fails

Errors should preserve partial outputs when possible, especially the evidence ledger and snapshot.

## Scope Boundaries

Included in this slice:

- deterministic local seed-driven thesis program
- provenance-aware bottleneck and monopoly scoring
- visual artifacts
- Notion-ready payload
- TradingAgents handoff file

Not included in this slice:

- live web crawling
- live Notion writes
- automated TradingAgents execution over the shortlist
- portfolio construction across the ranked set

## Open Assumptions

- The first target artifact is `tsmc-fab-output`.
- The initial corpus can be seed-driven and local.
- Visual artifacts only need to be static local files for v1.
- TradingAgents remains a downstream analysis consumer, not the orchestration layer for the thesis builder itself.

## Implementation Readiness Check

This design is small enough for one implementation plan.

The first plan should:

1. add schemas and fixtures
2. add scoring and snapshot assembly
3. add visual and Notion payload renderers
4. add CLI wiring and handoff output
5. add targeted tests and verify deterministic artifacts
