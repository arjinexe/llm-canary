import json
from pathlib import Path


def generate_html_report(result_file: Path, output_path: Path):
    with open(result_file) as f:
        data = json.load(f)

    results = data["results"]
    pass_rate = data["pass_rate"]
    run_at = data["run_at"]
    model = data["model"]
    provider = data["provider"]

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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>llm-canary — {model}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0a0e1a;color:#e2e8f0;font-family:'IBM Plex Sans',sans-serif}}
  header{{padding:48px 64px 32px;border-bottom:1px solid #1e2d45}}
  .mono{{font-family:'IBM Plex Mono',monospace}}
  h1{{font-size:28px;font-weight:300;color:#f1f5f9;margin-bottom:6px}}
  .meta{{font-size:13px;color:#64748b}}
  .stats{{display:flex;gap:24px;padding:28px 64px;border-bottom:1px solid #1e2d45}}
  .stat{{background:#111827;border:1px solid #1e2d45;border-radius:8px;padding:18px 24px}}
  .stat-label{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:6px}}
  .stat-value{{font-size:32px;font-weight:600;font-family:'IBM Plex Mono',monospace}}
  .bar-wrap{{padding:20px 64px;border-bottom:1px solid #1e2d45}}
  .bar-bg{{background:#1e2d45;border-radius:4px;height:5px}}
  .bar-fill{{height:5px;border-radius:4px;background:{bar_color};width:{pass_rate}%}}
  .badge{{display:inline-block;background:{bar_color}22;color:{bar_color};border:1px solid {bar_color}44;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;padding:3px 10px;border-radius:20px;margin-top:10px}}
  .table-wrap{{padding:20px 64px 64px;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  thead th{{text-align:left;padding:8px 14px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#64748b;border-bottom:1px solid #1e2d45;font-weight:400}}
  tbody tr{{border-bottom:1px solid #111827}}
  tbody tr:hover{{background:#111827}}
  tbody td{{padding:11px 14px;vertical-align:middle}}
  code{{font-family:'IBM Plex Mono',monospace;font-size:11px;background:#1e2d45;padding:2px 5px;border-radius:3px;color:#94a3b8}}
  footer{{padding:20px 64px;border-top:1px solid #1e2d45;text-align:center;font-size:12px;color:#334155;font-family:'IBM Plex Mono',monospace}}
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
