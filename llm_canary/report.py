import json
from pathlib import Path


def _build_history_chart(results_dir: Path, provider: str, model: str) -> str:
    """Return an inline SVG sparkline of the last 10 pass rates, or '' if not enough data."""
    safe_model = model.replace("/", "-").replace(":", "-")
    files = sorted(results_dir.glob(f"*_{provider}_{safe_model}.json"))

    records = []
    for f in files[-10:]:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            records.append({
                "date": data.get("run_at", "")[:10],
                "rate": data.get("pass_rate", 0),
            })
        except (json.JSONDecodeError, OSError):
            continue

    if len(records) < 2:
        return ""

    W, H = 300, 60
    pad = 8
    n = len(records)
    rates = [r["rate"] for r in records]
    min_r = max(0, min(rates) - 5)
    max_r = min(100, max(rates) + 5)
    rng = max_r - min_r or 1

    def x(i):
        return pad + i * (W - 2 * pad) / (n - 1)

    def y(v):
        return H - pad - (v - min_r) / rng * (H - 2 * pad)

    points = " ".join(f"{x(i):.1f},{y(r):.1f}" for i, r in enumerate(rates))

    # Color based on last value
    last = rates[-1]
    color = "#22c55e" if last >= 90 else ("#f59e0b" if last >= 70 else "#ef4444")

    labels = ""
    for i, rec in enumerate(records):
        cx, cy = x(i), y(rec["rate"])
        labels += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="{color}"/>'
            f'<title>{rec["date"]}: {rec["rate"]}%</title>'
        )

    return f"""
<div style="margin-top:8px">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:6px">
    Pass Rate Trend (last {n} runs)
  </div>
  <svg width="{W}" height="{H}" style="overflow:visible">
    <polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.5"
      stroke-linejoin="round" stroke-linecap="round" opacity="0.8"/>
    {labels}
    <line x1="{pad}" y1="{y(70):.1f}" x2="{W-pad}" y2="{y(70):.1f}"
      stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>
  </svg>
</div>"""


def generate_html_report(result_file: Path, output_path: Path, results_dir: Path = None):
    with open(result_file) as f:
        data = json.load(f)

    results = data["results"]
    pass_rate = data["pass_rate"]
    run_at = data["run_at"]
    model = data["model"]
    provider = data["provider"]

    if results_dir is None:
        results_dir = result_file.parent

    rows = ""
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        score_color = "#22c55e" if r["score"] >= 0.85 else ("#f59e0b" if r["score"] >= 0.5 else "#ef4444")
        err = f'<span style="color:#ef4444;font-size:11px">{r.get("error","")}</span>' if r.get("error") else ""
        preview = r.get("response_preview", "")[:120].replace("<", "&lt;").replace(">", "&gt;")
        rows += f"""<tr>
          <td>{icon}</td>
          <td><code>{r.get("suite","")}</code></td>
          <td>{r["name"]}</td>
          <td>{r["eval_type"]}</td>
          <td style="color:{score_color};font-weight:600">{r["score"]:.2f}</td>
          <td>{r["latency_s"]}s</td>
          <td style="font-size:11px;color:#94a3b8;max-width:280px;overflow:hidden">{preview}{err}</td>
        </tr>"""

    bar_color = "#22c55e" if pass_rate == 100 else ("#f59e0b" if pass_rate >= 70 else "#ef4444")
    status = "all passing" if pass_rate == 100 else ("degraded" if pass_rate >= 70 else "critical")

    history_chart = _build_history_chart(results_dir, provider, model)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>llm-canary — {model}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0a0e1a;color:#e2e8f0;font-family:'IBM Plex Sans',sans-serif}}
  header{{padding:48px 64px 32px;border-bottom:1px solid #1e2d45}}
  .mono{{font-family:'IBM Plex Mono',monospace}}
  h1{{font-size:28px;font-weight:300;color:#f1f5f9;margin-bottom:6px}}
  .meta{{font-size:13px;color:#64748b}}
  .stats{{display:flex;gap:24px;padding:28px 64424px;flex-wrap:wrap;padding:28px 64px;border-bottom:1px solid #1e2d45}}
  .stat{{background:#111827;border:1px solid #1e2d45;border-radius:8px;padding:18px 24px}}
  .stat-label{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:6px}}
  .stat-value{{font-size:32px;font-weight:600;font-family:'IBM Plex Mono',monospace}}
  .bar-wrap{{padding:20px 64px;border-bottom:1px solid #1e2d45}}
  .bar-bg{{background:#1e2d45;border-radius:4px;height:5px}}
  .bar-fill{{height:5px;border-radius:4px;background:{bar_color};width:{pass_rate}%;transition:width .4s ease}}
  .badge{{display:inline-block;background:{bar_color}22;color:{bar_color};border:1px solid {bar_color}44;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;padding:3px 10px;border-radius:20px;margin-top:10px}}
  .table-wrap{{padding:20px 64px 64px;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  thead th{{text-align:left;padding:8px 14px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#64748b;border-bottom:1px solid #1e2d45;font-weight:400}}
  tbody tr{{border-bottom:1px solid #111827}}
  tbody tr:hover{{background:#111827}}
  tbody td{{padding:11px 14px;vertical-align:middle}}
  code{{font-family:'IBM Plex Mono',monospace;font-size:11px;background:#1e2d45;padding:2px 5px;border-radius:3px;color:#94a3b8}}
  footer{{padding:20px 64px;border-top:1px solid #1e2d45;text-align:center;font-size:12px;color:#334155;font-family:'IBM Plex Mono',monospace}}
  @media(max-width:640px){{
    header,footer,.stats,.bar-wrap,.table-wrap{{padding-left:20px;padding-right:20px}}
  }}
</style>
</head>
<body>
<header>
  <div class="mono" style="font-size:12px;color:#64748b;margin-bottom:14px">llm-canary</div>
  <h1>Model Health Report</h1>
  <div class="meta mono">{provider} / {model} &nbsp;·&nbsp; {run_at[:16].replace("T"," ")} UTC</div>
</header>
<div class="stats">
  <div class="stat"><div class="stat-label">Pass Rate</div><div class="stat-value mono" style="color:{bar_color}">{pass_rate}%</div></div>
  <div class="stat"><div class="stat-label">Total</div><div class="stat-value mono">{data["total"]}</div></div>
  <div class="stat"><div class="stat-label">Passed</div><div class="stat-value mono" style="color:#22c55e">{data["passed"]}</div></div>
  <div class="stat"><div class="stat-label">Failed</div><div class="stat-value mono" style="color:#ef4444">{data["failed"]}</div></div>
</div>
<div class="bar-wrap">
  <div class="bar-bg"><div class="bar-fill"></div></div>
  <span class="badge mono">{status}</span>
  {history_chart}
</div>
<div class="table-wrap">
  <table>
    <thead><tr><th></th><th>Suite</th><th>Test</th><th>Eval</th><th>Score</th><th>Latency</th><th>Response</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<footer class="mono">github.com/arjinexe/llm-canary</footer>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
