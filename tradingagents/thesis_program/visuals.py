from __future__ import annotations

from tradingagents.thesis_program.schemas import RankedOpportunitySet, SeedPackage


def render_mermaid_graph(package: SeedPackage) -> str:
    lines = ["graph LR"]
    for edge in package.dependencies:
        lines.append(
            f"    {edge.from_entity_id}[{edge.from_entity_id}] --> {edge.to_entity_id}[{edge.to_entity_id}]"
        )
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
