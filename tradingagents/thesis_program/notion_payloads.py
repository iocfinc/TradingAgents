from __future__ import annotations

from tradingagents.thesis_program.schemas import RankedOpportunitySet, SeedPackage


def build_notion_payload(package: SeedPackage, ranked: RankedOpportunitySet, run_dir: str) -> dict:
    return {
        "artifact_slug": package.artifact_slug,
        "title": f"{package.artifact_label} Thesis Run - {package.as_of_date}",
        "blocks": [
            {
                "type": "callout",
                "text": (
                    f"Top bottleneck: {ranked.top_bottlenecks[0].entity_id} | "
                    f"Top position: {ranked.positions[0].ticker}"
                ),
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
