"""Mobile HTML for the full fact card. Numbers come from the JSON card only."""

from __future__ import annotations

import json
from html import escape
from typing import Any, Optional
from urllib.parse import urlencode

from pha.fact_card_copy import card_copy, group_label, js_copy
from pha.fact_card_interpret import humanize_interpret_failure
from pha.fact_card_locale import (
    DEFAULT_LOCALE,
    format_card_datetime,
    format_card_day,
    format_clock_hm,
    numeric_band_label,
    resolve_fact_card_locale,
)
from pha.fact_card_prefs import ASSESSMENT_PROMPT_MAX


def _q(user_id: str, token: Optional[str]) -> str:
    params = {"user_id": user_id}
    if token:
        params["token"] = token
    return urlencode(params)


def _interpret_status_html(
    interp: Optional[dict[str, Any]],
    *,
    locale: str,
    timezone_name: str = "",
) -> str:
    if not interp or not interp.get("status"):
        return f'<p class="fine" id="interp-status">{escape(card_copy(locale, "idle"))}</p>'
    status = str(interp.get("status") or "")
    if status == "pending":
        return (
            f'<p class="fine" id="interp-status">{escape(card_copy(locale, "pending"))}</p>'
        )
    if status == "failed":
        msg = humanize_interpret_failure(interp, locale=locale)
        return f'<p class="warn" id="interp-status">{escape(msg)}</p>'
    if status == "done":
        text = escape(str(interp.get("text") or ""))
        model = escape(str(interp.get("model") or ""))
        at = format_card_datetime(
            interp.get("generated_at"),
            locale=locale,
            timezone_name=timezone_name,
        )
        return (
            f'<div id="interp-status"><p class="interp-body">{text}</p>'
            f'<p class="fine">{escape(card_copy(locale, "model_meta", model=model, at=at))}</p></div>'
        )
    return '<p class="fine" id="interp-status"></p>'


def render_fact_card_html(
    card: dict[str, Any],
    *,
    prefs: dict[str, Any],
    token: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> str:
    user_id = str(card.get("user_id") or prefs.get("user_id") or "default")
    locale = resolve_fact_card_locale(
        prefs_locale=str(prefs.get("locale") or ""),
        accept_language=accept_language,
    )
    timezone_name = str(prefs.get("timezone") or "")
    facts = card.get("facts") or {}
    assessment = card.get("assessment") or {}
    summary = assessment.get("summary") or {}
    as_of_raw = facts.get("as_of")
    calendar_raw = facts.get("calendar_day") or ""
    as_of_shown = format_card_day(as_of_raw, locale=locale) if as_of_raw else card_copy(locale, "none")
    calendar_shown = format_card_day(calendar_raw, locale=locale)
    stale = bool(facts.get("stale"))
    stale_label = card_copy(locale, "not_today" if stale else "today")
    present = summary.get("coverage_present")
    total = summary.get("coverage_total")
    metrics_html = []
    for item in facts.get("metrics") or []:
        label = escape(str(item.get("label") or item.get("metric") or ""))
        value = item.get("value")
        unit = str(item.get("unit") or "")
        if value is None:
            shown = card_copy(locale, "none")
        elif unit == "count":
            shown = escape(str(int(value)))
        else:
            shown = escape(f"{value}{unit}")
        band = escape(
            numeric_band_label(str(item.get("numeric_band") or item.get("band") or ""), locale=locale)
        )
        extras: list[str] = []
        if item.get("partial_day") and item.get("as_of_time"):
            extras.append(card_copy(locale, "until", hm=format_clock_hm(item.get("as_of_time"))))
        elif item.get("freshness") in {"prior_day", "latest"} and item.get("day"):
            extras.append(
                card_copy(
                    locale,
                    "latest",
                    day=format_card_day(item.get("day"), locale=locale),
                )
            )
        if extras:
            shown = f"{shown} · {' · '.join(escape(str(x)) for x in extras)}" if value is not None else shown
        window = item.get("baseline_window")
        n = item.get("baseline_n")
        window_bit = ""
        if window and n is not None:
            window_bit = f'<span class="b">{escape(str(window))}·n={escape(str(n))}</span>'
        ref = item.get("reference") or {}
        ref_line = ""
        if isinstance(ref, dict) and ref.get("text"):
            ref_line = f'<p class="fine ref">{escape(str(ref.get("text")))}</p>'
        metrics_html.append(
            f'<li class="metric"><span class="k">{label}</span>'
            f'<span class="v">{shown}</span><span class="b">{band}</span>{window_bit}'
            f"{ref_line}</li>"
        )
    if not metrics_html:
        metrics_html.append('<li class="metric empty">' + escape(card_copy(locale, "empty_metrics")) + "</li>")

    advice_html = []
    raw_advice = assessment.get("advice") or []
    if isinstance(raw_advice, str):
        raw_advice = []
    for item in raw_advice:
        if not isinstance(item, dict):
            continue
        advice_html.append(
            f"<li>{escape(str(item.get('text') or ''))}</li>"
        )

    checks: list[str] = []
    last_group = None
    for row in prefs.get("catalog") or []:
        mid = escape(str(row.get("metric_id") or ""))
        label = escape(str(row.get("label") or row.get("metric_id") or ""))
        group = str(row.get("group") or group_label("其他", locale))
        if group != last_group:
            checks.append(f"<h3>{escape(group)}</h3>")
            last_group = group
        checked = " checked" if row.get("selected") else ""
        ingest = row.get("ingest_key")
        hint_text = str(row.get("shortcut_hint") or "").strip()
        if hint_text:
            hint = f" <em>{escape(hint_text)}</em>"
        elif row.get("shortcut_sync"):
            hint = " <em>由健康捷径同步</em>"
        elif ingest:
            hint = f' <em>ingest {escape(str(ingest))}</em>'
        else:
            hint = " <em>暂无捷径同步，仅展示历史</em>"
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
    composite = escape(str(summary.get("composite") or ""))
    composite_line = (
        f'<p class="fine">{escape(card_copy(locale, "composite", label=composite))}</p>' if composite else ""
    )
    prompt_raw = str(prefs.get("assessment_prompt") or "")
    prompt_escaped = escape(prompt_raw)
    prompt_max = int(prefs.get("assessment_prompt_max") or ASSESSMENT_PROMPT_MAX)
    interp = card.get("interpretation")
    interpret_block = _interpret_status_html(
        interp if isinstance(interp, dict) else None,
        locale=locale,
        timezone_name=timezone_name,
    )
    interpret_qs_json = json.dumps(qs, ensure_ascii=False)
    interpret_btn = (
        card_copy(locale, "retry")
        if isinstance(interp, dict) and interp.get("status") == "failed"
        else card_copy(locale, "generate")
    )
    hk = facts.get("healthkit") or {}
    if hk.get("reached"):
        hk_ts = format_card_datetime(
            hk.get("last_timestamp"),
            locale=locale,
            timezone_name=timezone_name,
        )
        hk_line = card_copy(
            locale,
            "hk_ok",
            metric=escape(str(hk.get("last_metric"))),
            at=escape(hk_ts),
        )
    else:
        hk_line = card_copy(locale, "hk_none")
    ingest_last = facts.get("ingest_last") or {}
    if ingest_last.get("at"):
        kind = escape(str(ingest_last.get("kind") or ""))
        at = escape(
            format_card_datetime(
                ingest_last.get("at"),
                locale=locale,
                timezone_name=timezone_name,
            )
        )
        if ingest_last.get("ok") is True:
            audit = ingest_last.get("audit") or {}
            extra = ""
            if audit.get("wake_day"):
                extra = card_copy(
                    locale,
                    "wake",
                    day=escape(format_card_day(audit.get("wake_day"), locale=locale)),
                )
            if audit.get("union_asleep_h") is not None:
                extra += card_copy(
                    locale, "asleep", hours=escape(str(audit.get("union_asleep_h")))
                )
            sync_line = card_copy(locale, "sync_ok", at=at, kind=kind, extra=extra)
        elif ingest_last.get("ok") is False:
            err_raw = str(ingest_last.get("error") or card_copy(locale, "fail"))
            err = escape(err_raw)
            if err_raw in {"empty_sample", "empty_samples"}:
                sync_line = card_copy(locale, "sync_empty", at=at, kind=kind)
            else:
                sync_line = card_copy(locale, "sync_fail", at=at, kind=kind, err=err)
        else:
            sync_line = card_copy(locale, "sync_plain", at=at)
        if ingest_last.get("pack_stale"):
            expected = escape(str(ingest_last.get("expected_pack_version") or ""))
            got = escape(str(ingest_last.get("pack_version") or ""))
            sync_line += (
                f'<span class="warn">{escape(card_copy(locale, "pack_stale", got=got, expected=expected))}</span>'
            )
    else:
        sync_line = card_copy(locale, "sync_none")
    zh_checked = " checked" if locale != "en-US" else ""
    en_checked = " checked" if locale == "en-US" else ""
    locale_block = (
        f"<h3>{escape(card_copy(locale, 'language'))}</h3>"
        f'<p class="fine">{escape(card_copy(locale, "language_help"))}</p>'
        f'<label class="pick"><input type="radio" name="locale" value="zh-CN"{zh_checked}>'
        "<span>中文</span></label>"
        f'<label class="pick"><input type="radio" name="locale" value="en-US"{en_checked}>'
        "<span>English</span></label>"
    )
    copy_js = json.dumps(js_copy(locale), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="{escape(locale or DEFAULT_LOCALE)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{escape(card_copy(locale, "title", day=calendar_shown))}</title>
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
    .ref {{ margin: 4px 0 0; grid-column: 1 / -1; }}
    ul {{ list-style: none; margin: 0; padding: 0; }}
    .pick {{
      display: flex; align-items: center; gap: 10px;
      padding: 12px 0; border-bottom: 1px solid #2c3642;
    }}
    .pick input {{ width: 20px; height: 20px; }}
    textarea {{
      width: 100%; box-sizing: border-box; min-height: 96px;
      margin-top: 8px; padding: 12px; border-radius: 12px;
      border: 1px solid #2c3642; background: #12171e; color: #f4f1ea;
      font: inherit;
    }}
    button {{
      width: 100%; margin-top: 16px; padding: 14px;
      border: 0; border-radius: 12px; font-size: 1rem;
      background: #e8d5a3; color: #1a1408; font-weight: 650;
    }}
    button.secondary {{
      background: #2c3642; color: #f4f1ea; font-weight: 600;
    }}
    button:disabled {{ opacity: .55; }}
    .warn {{ color: #f0c36d; font-weight: 600; }}
    .interp-body {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>{escape(card_copy(locale, "h1"))}</h1>
  <p class="meta">{escape(card_copy(locale, "calendar", day=calendar_shown))} · {escape(card_copy(locale, "as_of", day=as_of_shown))}
    · <span class="{'warn' if stale else ''}">{stale_label}</span>
    · {escape(card_copy(locale, "coverage", present=present, total=total))}</p>
  <p class="fine">{sync_line}</p>
  <p class="fine">{hk_line}</p>
  <section class="card">
    <h2>{escape(card_copy(locale, "facts"))}</h2>
    <ul>{''.join(metrics_html)}</ul>
  </section>
  <section class="card">
    <h2>{escape(card_copy(locale, "assessment"))}</h2>
    <p>{eval_text}</p>
    {composite_line}
    <p><strong>{escape(card_copy(locale, "advice_label"))}</strong>{advice_text}</p>
    <ul>{''.join(advice_html)}</ul>
    <p class="fine">{escape(card_copy(locale, "disclaimer"))}</p>
  </section>
  <section class="card" id="ai-interpret">
    <h2>{escape(card_copy(locale, "interpret_h2"))}</h2>
    <p class="fine">{escape(card_copy(locale, "interpret_fine"))}</p>
    {interpret_block}
    <button type="button" class="secondary" id="interpret-btn">{interpret_btn}</button>
  </section>
  <section class="card">
    <h2>{escape(card_copy(locale, "metrics_h2"))}</h2>
    <p class="fine">{escape(card_copy(locale, "metrics_help"))}</p>
    <form method="post" action="/proactive/fact-card/prefs?{qs}">
      {token_field}
      {''.join(checks)}
      {locale_block}
      <h3>{escape(card_copy(locale, "prompt_h3"))}</h3>
      <p class="fine">{escape(card_copy(locale, "prompt_help", max=prompt_max))}</p>
      <textarea name="assessment_prompt" maxlength="{prompt_max}"
        placeholder="{escape(card_copy(locale, "prompt_ph"))}">{prompt_escaped}</textarea>
      <button type="submit">{escape(card_copy(locale, "save"))}</button>
    </form>
  </section>
  <script>
  (function () {{
    var qs = {interpret_qs_json};
    var COPY = {copy_js};
    var btn = document.getElementById("interpret-btn");
    var box = document.getElementById("interp-status");
    if (!btn || !box) return;
    var timer = null;
    var polls = 0;
    var maxPolls = 48;

    function render(data) {{
      if (!data || !data.status) {{
        box.className = "fine";
        box.textContent = COPY.idle;
        return;
      }}
      if (data.status === "pending") {{
        box.className = "fine";
        box.textContent = COPY.pending;
        return;
      }}
      if (data.status === "failed") {{
        box.className = "warn";
        var err = data.error || "failed";
        if (err === "model_unavailable") {{
          box.textContent = COPY.model_unavailable;
          btn.textContent = COPY.retry;
        }} else if (err === "audit_rejected") {{
          var toks = [];
          var vs = data.violations || [];
          for (var i = 0; i < vs.length; i++) {{
            var s = String(vs[i] || "");
            var cut = s.indexOf(":");
            toks.push(cut >= 0 ? s.slice(cut + 1) : s);
          }}
          box.textContent = toks.length
            ? COPY.audit_rejected_toks.replace("{{toks}}", toks.slice(0, 8).join("、"))
            : COPY.audit_rejected;
          btn.textContent = COPY.retry;
        }} else {{
          box.textContent = String(err);
        }}
        return;
      }}
      if (data.status === "done") {{
        box.className = "";
        box.innerHTML = "";
        var p = document.createElement("p");
        p.className = "interp-body";
        p.textContent = data.text || "";
        var meta = document.createElement("p");
        meta.className = "fine";
        meta.textContent = COPY.model_meta
          .replace("{{model}}", data.model || "")
          .replace("{{at}}", data.generated_at_display || data.generated_at || "");
        box.appendChild(p);
        box.appendChild(meta);
        btn.textContent = COPY.generate;
      }}
    }}

    function poll() {{
      polls += 1;
      fetch("/proactive/fact-card/interpret?" + qs, {{ credentials: "same-origin" }})
        .then(function (r) {{ return r.json(); }})
        .then(function (data) {{
          render(data);
          if (data && data.status === "pending" && polls < maxPolls) {{
            timer = setTimeout(poll, 5000);
          }} else {{
            btn.disabled = false;
          }}
        }})
        .catch(function () {{
          box.className = "warn";
          box.textContent = COPY.model_unavailable;
          btn.textContent = COPY.retry;
          btn.disabled = false;
        }});
    }}

    btn.addEventListener("click", function () {{
      btn.disabled = true;
      polls = 0;
      if (timer) clearTimeout(timer);
      box.className = "fine";
      box.textContent = COPY.pending;
      fetch("/proactive/fact-card/interpret?" + qs, {{
        method: "POST",
        credentials: "same-origin"
      }})
        .then(function (r) {{ return r.json(); }})
        .then(function (data) {{
          render(data);
          if (data && data.status === "pending") {{
            timer = setTimeout(poll, 5000);
          }} else {{
            btn.disabled = false;
          }}
        }})
        .catch(function () {{
          box.className = "warn";
          box.textContent = COPY.model_unavailable;
          btn.textContent = COPY.retry;
          btn.disabled = false;
        }});
    }});
  }})();
  </script>
</body>
</html>
"""


__all__ = ["render_fact_card_html"]
