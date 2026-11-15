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
