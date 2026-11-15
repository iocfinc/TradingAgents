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
        "analysis_requests": [
            {
                "ticker": item.ticker,
                "analysis_date": package.as_of_date,
                "priority_rank": index,
                "thesis_summary": item.thesis_summary,
                "selected_analysts": ["market", "social", "news", "fundamentals"],
            }
            for index, item in enumerate(chosen, start=1)
        ],
    }
