"""A4 report rendering for completed TradingAgents benchmark runs."""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import subprocess
from typing import Any


CHROME_PATH = pathlib.Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_usd(value: float) -> str:
    return f"${value:,.4f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def _markdown_to_html(markdown: str) -> str:
    """Small markdown renderer for TradingAgents reports.

    This intentionally supports only the structures emitted by
    `quality_extract.md` so the PDF pipeline has no extra dependencies.
    """
    lines = markdown.splitlines()
    blocks: list[str] = []
    in_list = False
    in_table = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            blocks.append("</tbody></table>")
            in_table = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            close_list()
            close_table()
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            close_list()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-", ":", " "} for cell in cells):
                continue
            if not in_table:
                blocks.append("<table><tbody>")
                in_table = True
            tag = "th" if all(cell and not re.search(r"\d", cell) for cell in cells) else "td"
            blocks.append("<tr>" + "".join(f"<{tag}>{_inline_markdown(cell)}</{tag}>" for cell in cells) + "</tr>")
            continue
        close_table()

        if stripped.startswith("# "):
            close_list()
            blocks.append(f"<h1>{_inline_markdown(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            close_list()
            blocks.append(f"<h2>{_inline_markdown(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            close_list()
            blocks.append(f"<h3>{_inline_markdown(stripped[4:])}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_inline_markdown(stripped[2:])}</li>")
        else:
            close_list()
            blocks.append(f"<p>{_inline_markdown(stripped)}</p>")

    close_list()
    close_table()
    return "\n".join(blocks)


def _model_map_html(model_map: dict[str, str]) -> str:
    rows = []
    for role, model in sorted(model_map.items()):
        rows.append(f"<div><span>{html.escape(role)}</span><strong>{html.escape(model)}</strong></div>")
    return "\n".join(rows)


def build_report_html(run_dir: pathlib.Path) -> str:
    manifest = _read_json(run_dir / "manifest.json")
    cost = _read_json(run_dir / "cost_summary.json")
    model_map = _read_json(run_dir / "model_map.json")
    quality = (run_dir / "quality_extract.md").read_text(encoding="utf-8")
    body_html = _markdown_to_html(quality)
    decision = str(manifest.get("decision", "n/a"))
    decision_class = re.sub(r"[^a-z0-9]+", "-", decision.lower()).strip("-") or "na"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(manifest.get("ticker", "TradingAgents"))} TradingAgents Report</title>
<style>
@page {{
  size: A4;
  margin: 14mm 13mm 16mm;
}}
:root {{
  --ink: #111111;
  --muted: #65615a;
  --paper: #f4efe6;
  --sheet: #fffaf0;
  --line: #d7cfc2;
  --accent: #b53a2d;
  --accent-soft: #f0d8d1;
  --mono: "SFMono-Regular", "JetBrains Mono", "Menlo", monospace;
  --sans: "Avenir Next", "Satoshi", "Geist", "Helvetica Neue", sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 10.4pt;
  line-height: 1.52;
}}
.report-shell {{
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% 0%, rgba(181, 58, 45, 0.12), transparent 30%),
    linear-gradient(135deg, rgba(255,255,255,0.80), rgba(255,250,240,0.92));
}}
.cover {{
  display: grid;
  grid-template-columns: 1.45fr 0.75fr;
  gap: 9mm;
  min-height: 128mm;
  padding: 10mm 0 9mm;
  border-bottom: 1.2pt solid var(--ink);
}}
.kicker {{
  font-family: var(--mono);
  text-transform: uppercase;
  letter-spacing: 0.13em;
  font-size: 7.5pt;
  color: var(--accent);
  margin-bottom: 8mm;
}}
.title {{
  font-size: 35pt;
  line-height: 0.9;
  letter-spacing: -0.065em;
  margin: 0 0 8mm;
  max-width: 140mm;
}}
.subtitle {{
  max-width: 118mm;
  color: var(--muted);
  font-size: 11.5pt;
  line-height: 1.45;
}}
.decision {{
  display: inline-block;
  margin-top: 8mm;
  padding: 3mm 5mm;
  border: 1pt solid var(--ink);
  border-radius: 999px;
  font-family: var(--mono);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  background: var(--accent-soft);
}}
.decision.hold {{ background: #e4ead7; }}
.decision.underweight, .decision.sell {{ background: #efd3cd; }}
.rail {{
  border-left: 1.2pt solid var(--ink);
  padding-left: 7mm;
  display: grid;
  align-content: start;
  gap: 5mm;
}}
.metric {{
  border-top: 1pt solid var(--line);
  padding-top: 3mm;
}}
.metric span {{
  display: block;
  color: var(--muted);
  font-size: 7.5pt;
  text-transform: uppercase;
  letter-spacing: 0.09em;
}}
.metric strong {{
  display: block;
  font-family: var(--mono);
  font-size: 13pt;
  margin-top: 1mm;
}}
.model-map {{
  margin-top: 4mm;
  border-top: 1pt solid var(--ink);
  padding-top: 4mm;
}}
.model-map h2 {{
  margin: 0 0 3mm;
  font-size: 9pt;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}
.model-map div {{
  display: grid;
  grid-template-columns: 0.9fr 1fr;
  gap: 3mm;
  padding: 1.35mm 0;
  border-top: 0.5pt solid var(--line);
}}
.model-map span {{
  color: var(--muted);
  font-size: 7.5pt;
}}
.model-map strong {{
  font-family: var(--mono);
  font-size: 7.3pt;
  font-weight: 600;
  word-break: break-word;
}}
.content {{
  padding-top: 9mm;
}}
h1 {{
  font-size: 18pt;
  letter-spacing: -0.035em;
  margin: 0 0 6mm;
}}
h2 {{
  break-before: page;
  border-top: 1.4pt solid var(--ink);
  padding-top: 5mm;
  margin: 0 0 5mm;
  font-size: 19pt;
  line-height: 1;
  letter-spacing: -0.04em;
}}
h2:first-child {{
  break-before: auto;
}}
h3 {{
  font-size: 12pt;
  margin: 6mm 0 2mm;
  letter-spacing: -0.02em;
}}
p {{
  margin: 0 0 3mm;
  max-width: 178mm;
}}
ul {{
  margin: 0 0 4mm 5mm;
  padding: 0;
}}
li {{
  margin-bottom: 1.8mm;
}}
strong {{
  font-weight: 760;
}}
code {{
  font-family: var(--mono);
  font-size: 8.8pt;
  background: rgba(17,17,17,0.06);
  padding: 0.4mm 1mm;
  border-radius: 1.5mm;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 4mm 0 6mm;
  font-size: 8.7pt;
}}
th, td {{
  border-top: 0.7pt solid var(--line);
  padding: 2mm 1.8mm;
  text-align: left;
  vertical-align: top;
}}
th {{
  font-family: var(--mono);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 7.5pt;
}}
tr:last-child td {{
  border-bottom: 0.7pt solid var(--line);
}}
.footer {{
  margin-top: 10mm;
  padding-top: 4mm;
  border-top: 1pt solid var(--line);
  font-family: var(--mono);
  font-size: 7.4pt;
  color: var(--muted);
}}
</style>
</head>
<body>
<main class="report-shell">
  <section class="cover">
    <div>
      <div class="kicker">TradingAgents Benchmark Run</div>
      <h1 class="title">{html.escape(manifest.get("ticker", "UNKNOWN"))}<br>Research Packet</h1>
      <p class="subtitle">{html.escape(manifest.get("description", ""))}</p>
      <div class="decision {decision_class}">{html.escape(decision)}</div>
    </div>
    <aside class="rail">
      <div class="metric"><span>Analysis date</span><strong>{html.escape(str(manifest.get("analysis_date", "n/a")))}</strong></div>
      <div class="metric"><span>Provider</span><strong>{html.escape(str(manifest.get("provider", "n/a")))}</strong></div>
      <div class="metric"><span>Run set</span><strong>{html.escape(str(manifest.get("run_set", manifest.get("model_set", "n/a"))))}</strong></div>
      <div class="metric"><span>LLM calls</span><strong>{_format_int(int(cost.get("total_calls") or 0))}</strong></div>
      <div class="metric"><span>Total tokens</span><strong>{_format_int(int(cost.get("total_tokens") or 0))}</strong></div>
      <div class="metric"><span>Estimated cost</span><strong>{_format_usd(float(cost.get("total_estimated_cost_usd") or 0))}</strong></div>
      <div class="metric"><span>Run ID</span><strong>{html.escape(str(manifest.get("run_id", run_dir.name)))}</strong></div>
      <div class="model-map">
        <h2>Role Routing</h2>
        {_model_map_html(model_map)}
      </div>
    </aside>
  </section>
  <section class="content">
    {body_html}
    <div class="footer">Generated from {html.escape(str(run_dir))}. Research-only output; no broker execution instruction.</div>
  </section>
</main>
</body>
</html>
"""


def build_report_stem(manifest: dict[str, Any], fallback: str) -> str:
    parts = [
        str(manifest.get("ticker") or fallback),
        str(manifest.get("provider") or "provider"),
        str(manifest.get("run_set") or manifest.get("model_set") or "benchmark"),
        "tradingagents_report",
    ]
    stem = "_".join(parts)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_")


def render_run_report(run_dir: pathlib.Path, output_dir: pathlib.Path | None = None) -> tuple[pathlib.Path, pathlib.Path]:
    run_dir = run_dir.expanduser().resolve()
    if output_dir is None:
        output_dir = run_dir
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _read_json(run_dir / "manifest.json")
    stem = build_report_stem(manifest, run_dir.name)
    html_path = output_dir / f"{stem}.html"
    pdf_path = output_dir / f"{stem}.pdf"
    html_path.write_text(build_report_html(run_dir), encoding="utf-8")

    if not CHROME_PATH.exists():
        raise SystemExit(f"Google Chrome not found at {CHROME_PATH}; HTML written to {html_path}")
    subprocess.run(
        [
            str(CHROME_PATH),
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        check=True,
    )
    return html_path, pdf_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render TradingAgents benchmark run directories as A4 PDF reports.")
    parser.add_argument("run_dirs", nargs="+", type=pathlib.Path)
    parser.add_argument("--output-dir", type=pathlib.Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    for run_dir in args.run_dirs:
        html_path, pdf_path = render_run_report(run_dir, args.output_dir)
        print(pdf_path)
        print(html_path)
    return 0
