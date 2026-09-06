"""Mobile HTML for the full fact card. Numbers come from the JSON card only."""

from __future__ import annotations

from html import escape
from typing import Any, Optional
from urllib.parse import urlencode

from pha.fact_card import DISCLAIMER


def _q(user_id: str, token: Optional[str]) -> str:
    params = {"user_id": user_id}
    if token:
        params["token"] = token
    return urlencode(params)


def render_fact_card_html(
    card: dict[str, Any],
    *,
    prefs: dict[str, Any],
    token: Optional[str] = None,
) -> str:
    user_id = str(card.get("user_id") or prefs.get("user_id") or "default")
    facts = card.get("facts") or {}
    assessment = card.get("assessment") or {}
    summary = assessment.get("summary") or {}
    as_of = facts.get("as_of") or "无"
    calendar_day = facts.get("calendar_day") or ""
    stale = bool(facts.get("stale"))
    stale_label = "非今日" if stale else "当日"
    present = summary.get("coverage_present")
    total = summary.get("coverage_total")
    metrics_html = []
    for item in facts.get("metrics") or []:
        label = escape(str(item.get("label") or item.get("metric") or ""))
        value = item.get("value")
        unit = str(item.get("unit") or "")
        if value is None:
            shown = "无"
        elif unit == "count":
            shown = escape(str(int(value)))
        else:
            shown = escape(f"{value}{unit}")
        band = escape(str(item.get("band") or ""))
        metrics_html.append(
            f'<li class="metric"><span class="k">{label}</span>'
            f'<span class="v">{shown}</span><span class="b">{band}</span></li>'
        )
    if not metrics_html:
        metrics_html.append('<li class="metric empty">未选择指标</li>')

    advice_html = []
    for item in assessment.get("advice") or []:
        advice_html.append(
            f"<li>{escape(str(item.get('text') or ''))}</li>"
        )

    checks = []
    for row in prefs.get("catalog") or []:
        mid = escape(str(row.get("metric_id") or ""))
        label = escape(str(row.get("label") or row.get("metric_id") or ""))
        checked = " checked" if row.get("selected") else ""
        ingest = row.get("ingest_key")
        hint = f' <em>ingest {escape(str(ingest))}</em>' if ingest else ""
        checks.append(
            f'<label class="pick"><input type="checkbox" name="metric_id" '
            f'value="{mid}"{checked}><span>{label}{hint}</span></label>'
        )

    qs = _q(user_id, token)
    token_field = (
        f'<input type="hidden" name="token" value="{escape(token)}">' if token else ""
    )
    eval_text = escape(str(summary.get("text") or ""))
    advice_text = escape(str(summary.get("advice") or ""))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>PHA 事实卡 · {escape(str(calendar_day))}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      margin: 0; padding: 20px 16px 48px;
      font: 17px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f1419; color: #f4f1ea;
    }}
    h1 {{ font-size: 1.35rem; margin: 0 0 6px; }}
    .meta, .fine {{ color: #b9b3a7; font-size: .92rem; }}
    .card {{
      background: #1b222b; border-radius: 16px; padding: 16px 16px 8px;
      margin: 14px 0;
    }}
    .metric {{
      display: grid; grid-template-columns: 1fr auto auto; gap: 8px;
      padding: 12px 0; border-bottom: 1px solid #2c3642;
    }}
    .metric:last-child {{ border-bottom: 0; }}
    .k {{ font-weight: 600; }}
    .v {{ font-variant-numeric: tabular-nums; }}
    .b {{ color: #8f8778; font-size: .85rem; }}
    ul {{ list-style: none; margin: 0; padding: 0; }}
    .pick {{
      display: flex; align-items: center; gap: 10px;
      padding: 12px 0; border-bottom: 1px solid #2c3642;
    }}
    .pick input {{ width: 20px; height: 20px; }}
    button {{
      width: 100%; margin-top: 16px; padding: 14px;
      border: 0; border-radius: 12px; font-size: 1rem;
      background: #e8d5a3; color: #1a1408; font-weight: 650;
    }}
    .warn {{ color: #f0c36d; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>PHA 事实卡</h1>
  <p class="meta">日历日 {escape(str(calendar_day))} · 截至 {escape(str(as_of))}
    · <span class="{'warn' if stale else ''}">{stale_label}</span>
    · 覆盖 {escape(str(present))}/{escape(str(total))}</p>
  <section class="card">
    <h2>事实</h2>
    <ul>{''.join(metrics_html)}</ul>
  </section>
  <section class="card">
    <h2>评估</h2>
    <p>{eval_text}</p>
    <p><strong>建议：</strong>{advice_text}</p>
    <ul>{''.join(advice_html)}</ul>
    <p class="fine">{escape(DISCLAIMER)}</p>
  </section>
  <section class="card">
    <h2>我要看哪些指标</h2>
    <p class="fine">从注册表勾选，不是写死五项。未入库的项会显示「无」，不会编数。</p>
    <form method="post" action="/proactive/fact-card/prefs?{qs}">
      {token_field}
      {''.join(checks)}
      <button type="submit">保存并刷新完整卡</button>
    </form>
  </section>
</body>
</html>
"""


__all__ = ["render_fact_card_html"]
