import html
import json
from pathlib import Path
from typing import Any, Dict


def write_html_report(run: Dict[str, Any], output_path: Path) -> None:
    output_path.write_text(_render(run), encoding="utf-8")


def _render(run: Dict[str, Any]) -> str:
    data_json = html.escape(json.dumps(run), quote=True)
    suite_name = html.escape(run["suite_name"])
    base_url   = html.escape(run["base_url"])
    env        = html.escape(run["environment"])
    generated  = html.escape(run["generated_at"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{suite_name} — API Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    /* ── Kinetic Flow Design Tokens ─────────────────────────────────────── */
    :root {{
      --surface:           #f9f9ff;
      --surface-low:       #f0f3ff;
      --surface-container: #e7eeff;
      --surface-high:      #dee8ff;
      --surface-highest:   #d8e3fb;
      --on-surface:        #111c2d;
      --on-surface-var:    #3c4a3d;
      --outline:           #6c7b6c;
      --outline-var:       #bbcbba;
      --inverse-surface:   #263143;

      --primary:           #006d34;
      --on-primary:        #ffffff;
      --primary-container: #00d26a;
      --on-primary-cont:   #005426;

      --secondary:         #0058be;
      --on-secondary:      #ffffff;
      --secondary-cont:    #2170e4;
      --on-secondary-cont: #fefcff;

      --tertiary:          #9f4200;
      --tertiary-cont:     #ff9f6d;

      --error:             #ba1a1a;
      --on-error:          #ffffff;
      --error-container:   #ffdad6;
      --on-error-cont:     #93000a;
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
      background: var(--surface);
      color: var(--on-surface);
      min-height: 100vh;
      font-size: 14px;
      line-height: 1.6;
    }}

    /* ── Background decoration ─────────────────────────────────────────── */
    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background-image: radial-gradient(rgba(0,88,190,.03) 1.5px, transparent 1.5px);
      background-size: 28px 28px;
      pointer-events: none;
      z-index: 0;
    }}

    /* ── Hero ──────────────────────────────────────────────────────────── */
    .hero {{
      position: relative;
      background: linear-gradient(135deg, #006d34 0%, #0058be 100%);
      padding: 40px min(6vw, 72px) 80px;
      overflow: hidden;
      color: #fff;
    }}
    .hero::after {{
      content: '';
      position: absolute;
      inset: 0;
      background: radial-gradient(ellipse at 80% -20%, rgba(255,255,255,.18), transparent 55%);
      pointer-events: none;
    }}
    .hero-inner {{
      position: relative;
      z-index: 1;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 20px;
      max-width: 1260px;
      margin: 0 auto;
    }}
    .hero h1 {{
      font-size: clamp(26px, 4vw, 48px);
      font-weight: 800;
      letter-spacing: -0.5px;
      line-height: 1.1;
      margin-bottom: 8px;
    }}
    .hero-sub {{
      font-size: 15px;
      opacity: .88;
      max-width: 680px;
    }}
    .hero-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(255,255,255,.15);
      border: 1px solid rgba(255,255,255,.28);
      border-radius: 10px;
      padding: 9px 14px;
      font-size: 13px;
      font-weight: 600;
      white-space: nowrap;
      backdrop-filter: blur(6px);
    }}

    /* ── Main content ──────────────────────────────────────────────────── */
    .wrap {{
      position: relative;
      z-index: 1;
      max-width: 1260px;
      margin: 0 auto;
      padding: 0 min(4vw, 40px) 60px;
    }}

    /* ── Metric cards ──────────────────────────────────────────────────── */
    .metrics {{
      display: grid;
      grid-template-columns: repeat(5, minmax(130px, 1fr));
      gap: 14px;
      margin-top: -48px;
      margin-bottom: 28px;
    }}
    .metric {{
      background: #fff;
      border: 1.5px solid var(--surface-high);
      border-radius: 14px;
      padding: 18px 20px;
      box-shadow: 0 4px 24px rgba(0,88,190,.08), 0 1px 4px rgba(0,0,0,.04);
    }}
    .metric-label {{
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--outline);
      margin-bottom: 10px;
    }}
    .metric-value {{
      font-size: 32px;
      font-weight: 800;
      line-height: 1;
      color: var(--on-surface);
    }}
    .metric-value.pass {{ color: var(--primary); }}
    .metric-value.fail {{ color: var(--error); }}
    .metric-sub {{
      font-size: 11px;
      color: var(--outline);
      margin-top: 4px;
    }}

    /* ── Panels ────────────────────────────────────────────────────────── */
    .panel {{
      background: #fff;
      border: 1.5px solid var(--surface-high);
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0,88,190,.06), 0 1px 4px rgba(0,0,0,.03);
      padding: 24px;
      overflow: hidden;
    }}
    .panel-title {{
      font-size: 15px;
      font-weight: 700;
      color: var(--on-surface);
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .panel-title::before {{
      content: '';
      display: inline-block;
      width: 3px;
      height: 16px;
      border-radius: 2px;
      background: var(--secondary);
    }}

    /* ── Grid layout ───────────────────────────────────────────────────── */
    .grid-2 {{
      display: grid;
      grid-template-columns: 1.2fr .8fr;
      gap: 18px;
      margin-bottom: 18px;
    }}

    /* ── Tables ────────────────────────────────────────────────────────── */
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--outline);
      padding: 8px 10px 10px;
      border-bottom: 1.5px solid var(--surface-container);
      text-align: left;
    }}
    tbody td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--surface-low);
      vertical-align: top;
    }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr:hover td {{ background: var(--surface-low); }}

    /* ── Status pill ───────────────────────────────────────────────────── */
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .04em;
      white-space: nowrap;
    }}
    .status.pass {{ background: #d6f5e3; color: #005426; }}
    .status.fail {{ background: var(--error-container); color: var(--on-error-cont); }}
    .status::before {{
      content: '';
      width: 6px; height: 6px;
      border-radius: 50%;
    }}
    .status.pass::before {{ background: var(--primary); }}
    .status.fail::before {{ background: var(--error); }}

    /* ── Method badge ──────────────────────────────────────────────────── */
    .method {{
      display: inline-block;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 600;
      border-radius: 5px;
      padding: 2px 6px;
      margin-right: 5px;
    }}
    .method-GET    {{ background: #d6f5e3; color: #005426; }}
    .method-POST   {{ background: #e7eeff; color: #004395; }}
    .method-PUT    {{ background: #fff3e0; color: #7b3100; }}
    .method-DELETE {{ background: var(--error-container); color: var(--on-error-cont); }}
    .method-PATCH  {{ background: #f3e8ff; color: #5b0fa8; }}

    /* ── Progress bar ──────────────────────────────────────────────────── */
    .bar {{
      height: 8px;
      border-radius: 999px;
      background: var(--surface-container);
      overflow: hidden;
      min-width: 80px;
      margin-bottom: 4px;
    }}
    .bar span {{
      display: block;
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--primary), var(--primary-container));
    }}
    .bar.fail span {{ background: linear-gradient(90deg, var(--error), #ff6b6b); }}

    /* ── Timing bars ───────────────────────────────────────────────────── */
    .timing-row {{
      margin-bottom: 18px;
    }}
    .timing-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 7px;
      font-size: 13px;
    }}
    .timing-head strong {{ font-weight: 600; }}
    .timing-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--outline);
    }}

    /* ── Detail accordion ──────────────────────────────────────────────── */
    .detail-block {{
      border: 1.5px solid var(--surface-high);
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 12px;
    }}
    .detail-block:last-child {{ margin-bottom: 0; }}
    .detail-summary {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 16px;
      cursor: pointer;
      background: var(--surface-low);
      user-select: none;
      list-style: none;
      font-weight: 600;
      font-size: 14px;
      transition: background .15s;
    }}
    .detail-summary::-webkit-details-marker {{ display: none; }}
    .detail-summary:hover {{ background: var(--surface-container); }}
    .detail-chevron {{
      margin-left: auto;
      font-size: 11px;
      color: var(--outline);
      transition: transform .2s;
    }}
    details[open] .detail-chevron {{ transform: rotate(180deg); }}
    .detail-body {{
      padding: 16px;
      border-top: 1.5px solid var(--surface-high);
    }}
    .meta-pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 14px;
    }}
    .pill {{
      display: inline-block;
      background: var(--surface-container);
      color: var(--on-surface-var);
      border: 1px solid var(--surface-high);
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 11px;
      font-weight: 600;
    }}
    .mono {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      word-break: break-all;
    }}
    .endpoint-text {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--outline);
    }}
    .case-name {{ font-weight: 600; }}

    /* ── Footer ────────────────────────────────────────────────────────── */
    footer {{
      text-align: center;
      padding: 32px 20px;
      color: var(--outline);
      font-size: 12px;
      border-top: 1px solid var(--surface-high);
      margin-top: 20px;
    }}
    footer strong {{ color: var(--secondary); }}

    /* ── Responsive ────────────────────────────────────────────────────── */
    @media (max-width: 960px) {{
      .metrics {{ grid-template-columns: repeat(3, 1fr); margin-top: -36px; }}
      .grid-2  {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 600px) {{
      .metrics {{ grid-template-columns: repeat(2, 1fr); }}
      .hero {{ padding: 28px 20px 72px; }}
      thead th:nth-child(4), tbody td:nth-child(4),
      thead th:nth-child(5), tbody td:nth-child(5) {{ display: none; }}
    }}
  </style>
</head>
<body>

  <header class="hero">
    <div class="hero-inner">
      <div>
        <h1>API Quality Report</h1>
        <p class="hero-sub">{suite_name} &mdash; tested against <strong>{base_url}</strong>. Functionality, reliability, response time, and assertion coverage in one run.</p>
      </div>
      <div class="hero-badge">🌍 {env} &nbsp;|&nbsp; 🕐 {generated}</div>
    </div>
  </header>

  <main class="wrap" id="app" data-run="{data_json}"></main>

  <footer>Generated by <strong>FlowForge</strong> &amp; Maintained by Varun PK</footer>

  <script>
    const run = JSON.parse(document.getElementById('app').dataset.run);
    const summary = run.summary;
    const app = document.getElementById('app');
    const allPass = summary.failed === 0;

    /* ── helpers ───────────────────────────────────────────────────────── */
    function esc(v) {{
      return String(v ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    }}
    function status(ok) {{
      return `<span class="status ${{ok?'pass':'fail'}}">${{ok?'PASS':'FAIL'}}</span>`;
    }}
    function methodBadge(m) {{
      return `<span class="method method-${{esc(m)}}">${{esc(m)}}</span>`;
    }}

    /* ── metric card ───────────────────────────────────────────────────── */
    function metricCard(label, value, cls='', sub='') {{
      return `<div class="metric">
        <div class="metric-label">${{label}}</div>
        <div class="metric-value ${{cls}}">${{value}}</div>
        ${{sub ? `<div class="metric-sub">${{sub}}</div>` : ''}}
      </div>`;
    }}

    /* ── case overview row ─────────────────────────────────────────────── */
    function caseRow(item) {{
      const isFail = !item.passed;
      return `<tr>
        <td>${{status(item.passed)}}</td>
        <td>
          <div class="case-name">${{esc(item.name)}}</div>
          <div class="endpoint-text">${{methodBadge(item.method)}}${{esc(item.endpoint)}}</div>
        </td>
        <td>
          <div class="bar${{isFail?' fail':''}}" title="${{item.success_rate}}%"><span style="width:${{Math.min(100,item.success_rate)}}%"></span></div>
          <span class="mono">${{item.success_rate}}%</span>
        </td>
        <td class="mono">${{item.timings.p95}} ms</td>
        <td class="mono">${{item.max_p95_ms ? item.max_p95_ms+' ms' : '—'}}</td>
      </tr>`;
    }}

    /* ── timing bar block ──────────────────────────────────────────────── */
    function timingBlock(item) {{
      const max = Math.max(...run.cases.map(c => c.timings.p95), 1);
      const w = Math.max(4, (item.timings.p95 / max) * 100);
      return `<div class="timing-row">
        <div class="timing-head">
          <strong>${{esc(item.name)}}</strong>
          <span class="timing-val">${{item.timings.p95}} ms p95</span>
        </div>
        <div class="bar"><span style="width:${{w}}%"></span></div>
      </div>`;
    }}

    /* ── detailed evidence block ───────────────────────────────────────── */
    function caseDetails(item) {{
      const iterations = item.iterations.map(iterRow).join('');
      return `<details class="detail-block" ${{!item.passed?'open':''}}>
        <summary class="detail-summary">
          ${{status(item.passed)}}
          ${{methodBadge(item.method)}}
          <span>${{esc(item.name)}}</span>
          <span class="endpoint-text">&nbsp;${{esc(item.endpoint)}}</span>
          <span class="detail-chevron">▼</span>
        </summary>
        <div class="detail-body">
          <div class="meta-pills">
            <span class="pill">🔁 Repeat: ${{item.repeat}}</span>
            <span class="pill">✅ Success: ${{item.success_rate}}%</span>
            <span class="pill">⏱ Avg: ${{item.timings.avg}} ms</span>
            <span class="pill">📈 P95: ${{item.timings.p95}} ms</span>
            ${{item.max_p95_ms ? `<span class="pill">🎯 Target: ${{item.max_p95_ms}} ms</span>` : ''}}
          </div>
          <table>
            <thead><tr><th>#</th><th>Status</th><th>HTTP</th><th>Time</th><th>Assertions</th></tr></thead>
            <tbody>${{iterations}}</tbody>
          </table>
        </div>
      </details>`;
    }}

    function iterRow(it) {{
      const assertions = it.error
        ? `<span class="status fail">ERROR</span> <span class="mono">${{esc(it.error)}}</span>`
        : it.assertions.map(a =>
            `${{status(a.passed)}} <span class="mono">${{esc(a.name)}} — ${{esc(a.message)}}</span>`
          ).join('<br>');
      return `<tr>
        <td class="mono">${{it.iteration}}</td>
        <td>${{status(it.passed)}}</td>
        <td class="mono">${{it.status_code ?? '—'}}</td>
        <td class="mono">${{it.elapsed_ms}} ms</td>
        <td>${{assertions}}</td>
      </tr>`;
    }}

    /* ── render ────────────────────────────────────────────────────────── */
    app.innerHTML = `
      <div class="metrics">
        ${{metricCard('Pass Rate', summary.pass_rate+'%', allPass?'pass':'fail', allPass?'All checks green':'Some checks failed')}}
        ${{metricCard('Passed', summary.passed, 'pass')}}
        ${{metricCard('Failed', summary.failed, summary.failed>0?'fail':'')}}
        ${{metricCard('Avg Response', summary.timings.avg+' ms')}}
        ${{metricCard('P95 Response', summary.timings.p95+' ms')}}
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-title">Case Overview</div>
          <table>
            <thead><tr><th>Status</th><th>API Case</th><th>Reliability</th><th>P95</th><th>Target</th></tr></thead>
            <tbody>${{run.cases.map(caseRow).join('')}}</tbody>
          </table>
        </div>
        <div class="panel">
          <div class="panel-title">Response Time Distribution</div>
          ${{run.cases.map(timingBlock).join('')}}
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">Detailed Evidence</div>
        ${{run.cases.map(caseDetails).join('')}}
      </div>
    `;
  </script>
</body>
</html>"""
