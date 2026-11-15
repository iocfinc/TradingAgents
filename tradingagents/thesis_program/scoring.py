from __future__ import annotations

from tradingagents.thesis_program.schemas import (
    BottleneckAssessment,
    RankedOpportunitySet,
    ResearchPosition,
    SeedPackage,
)


def _bottleneck_score(criticality: int, concentration: int, substitutability: int) -> float:
    return round(
        (criticality * 0.5)
        + (concentration * 0.35)
        + ((11 - substitutability) * 0.15),
        2,
    )


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
            evidence_title = evidence_by_id[evidence_ids[0]].title if evidence_ids else "No evidence title"
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
                    trigger_monitoring=[evidence_title],
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
