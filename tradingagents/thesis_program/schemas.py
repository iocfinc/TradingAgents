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
