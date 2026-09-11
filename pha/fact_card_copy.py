"""Fact-card chrome + rule copy. Git default is English; zh-CN is the other locale."""

from __future__ import annotations

from typing import Any, Optional

from pha.fact_card_locale import normalize_fact_card_locale

GROUP_EN = {
    "睡眠": "Sleep",
    "心脏": "Heart",
    "活动": "Activity",
    "呼吸与血氧": "Respiration & SpO2",
    "体能": "Fitness",
    "其他": "Other",
}

_EN: dict[str, str] = {
    "disclaimer": "Educational reference, not medical advice, and not a substitute for a physician.",
    "none": "none",
    "today": "Today",
    "not_today": "Not today",
    "coverage": "coverage {present}/{total}",
    "calendar": "Calendar day {day}",
    "as_of": "as of {day}",
    "facts": "Facts",
    "assessment": "Assessment",
    "advice_label": "Advice:",
    "composite": "Card composite: {label}",
    "interpret_h2": "AI interpretation (experimental) · not medical advice",
    "interpret_fine": "The local model runs only after you tap the button; it is not in the notification and does not replace the rules above.",
    "generate": "Generate interpretation",
    "retry": "Retry",
    "idle": "Not generated yet. Tap the button below to call the local model.",
    "pending": "Generating — you can leave and refresh later.",
    "model_unavailable": "Local model did not respond",
    "exclusive_scope_empty": "No named metrics from this assessment are on today's card, so no interpretation was generated.",
    "audit_rejected_toks": "The model wrote numbers that are not on the card ({toks}); the whole paragraph was discarded. You can retry.",
    "audit_rejected": "Not generated (failed audit)",
    "audit_hint_after_fail": "Interpretation may only cite numbers on this card. Population commons may use integers; do not invent decimals.",
    "audit_cat_value": "off-card measurement: {toks}",
    "audit_cat_date": "off-card date: {toks}",
    "audit_cat_window": "window not on card: {toks}",
    "audit_cat_forgery": "personal data inside a reference-standard block",
    "model_meta": "Model {model} · generated {at}",
    "bg_brief_used": "Referenced {n} background note(s) from your chats (not a numeric source)",
    "assessment_prompt_head": "User assessment request · outline for this turn, not a numeric source",
    "followup_continue_topic": "Continue with {tok}",
    "followup_look_at_metric": "Look at {mk}",
    "bg_brief_title": "User background · self-reported · not a numeric source",
    "bg_brief_lead": "The following is self-reported context from your chats. When this slot is present, fold specific items into advice wording using the words that appear in this slot. Do not skip it; do not replace those items with vague category labels alone; do not cite as data; do not restate or give doses; do not invent a numbered cautions list. Correlational wording only; no definitive causal claims.",
    "bg_brief_omitted": "[amount omitted]",
    "bg_brief_rel_week": "within the last week",
    "bg_brief_rel_month": "within the last month",
    "bg_brief_rel_earlier": "earlier",
    "bg_brief_cat_supplement": "Supplements",
    "bg_brief_cat_medication": "Medications",
    "bg_brief_cat_sleep_lifestyle": "Sleep / lifestyle",
    "bg_brief_cat_symptom": "Symptoms",
    "bg_brief_cat_general": "General",
    "bg_brief_split_marks": "morning|noon|evening|bedtime",
    "bg_brief_item_seps": " + |、|/|) |） ",
    "bg_brief_item_glue": " · ",
    "bg_brief_table_headers": "time|item|details|logic",
    "bg_brief_note_caps": "supplement:6|medication:4|sleep_lifestyle:3|symptom:3|general:2",
    "bg_brief_row_caps": "supplement:20|medication:6|sleep_lifestyle:4|symptom:4|general:2",
    "bg_lineage_stub_marks": "today's value|percentile|baseline nights|baseline days",
    "metrics_h2": "Metrics I want to see",
    "metrics_help": "Checkboxes only control what this card shows and assesses. Shortcuts sync the priority pack. Refresh after changing checks; new values appear after the next shortcut run. Rebuild shortcuts only when the pack version changes. A zip import overwrites same-day shortcut rows; re-import export.zip about once a quarter.",
    "prompt_h3": "My assessment request",
    "prompt_help": "Interpretation may only cite numbers on this card. Population commons may use integers; decimals and personal claims must match the card. Max {max} characters.",
    "prompt_ph": "e.g. Focus on sleep, plain tone, don't scare me",
    "save": "Save and refresh full card",
    "language": "Language",
    "language_help": "Language only; dates follow the language. There is no separate date-format option.",
    "empty_metrics": "No metrics selected. Check items at the bottom of this card.",
    "hero_kicker": "Today vs your baseline",
    "setup_h2": "Finish setup on this iPhone",
    "setup_lead": "This is not the chat box. After HealthKit reaches your Mac, numbers and the three-band assessment appear with no typing. Local model is optional, behind the button below.",
    "setup_1": "Mac and iPhone on the same Wi-Fi (not cellular). iPhone Settings → Privacy & Security → Local Network → turn on Shortcuts.",
    "setup_2": "Run「PHA Daily」once (Allow Access on every Health Find). Older installs:「PHA 同步睡眠」, then「PHA 同步健康」, then「PHA 事实卡通知」.",
    "setup_3": "This page should fill in. If Safari cannot connect, the Mac is not reachable on this Wi-Fi.",
    "setup_4": "Shortcuts → Automation → Time of Day → PHA Daily. Turn on Run Immediately.",
    "latest": "{day}, latest",
    "until": "as of {hm}",
    "hk_ok": "Latest HealthKit sample row: {metric} @ {at}.",
    "hk_none": "No HealthKit rows in the ledger yet. Health-app values will not appear here.",
    "sync_ok": "Last sync ok: {at} · {kind}{extra}",
    "sync_fail": "Last sync failed: {at} · {kind} · {err}",
    "sync_empty": "Last sync: {at} · {kind} · Health app has no samples yet (not written; not a sync failure)",
    "sync_plain": "Last sync: {at}",
    "sync_none": "No shortcut receipt yet (run PHA Sync Sleep / Health to see the last success or failure).",
    "pack_stale": " Shortcut pack is stale (device {got}, current {expected}). Regenerated on the Mac and replace PHA Sync Health.",
    "wake": " · wake day {day}",
    "asleep": " · asleep {hours}h",
    "fail": "failed",
    "hint_sleep": "Synced by the sleep shortcut",
    "hint_quantity": "Synced by the health shortcut",
    "hint_history": "No shortcut sync yet; history only",
    "window_90d": "last 90 days, {n} {unit}",
    "window_365d": "last 12 months, {n} {unit}",
    "window_all": "all history (since {since}), {n} {unit}",
    "window_short": "personal history {n}/7 {unit}",
    "unit_night": "nights",
    "unit_day": "days",
    "comp_none": "not combined",
    "comp_easy": "easier",
    "comp_good": "favorable",
    "comp_typical": "similar",
    "ref_within": "within the reference range",
    "ref_below": "below the reference range",
    "ref_above": "above the reference range",
    "ref_note": "common suggested range",
    "ref_text": "【参考标准】{title} {span}, today you are {shown}{unit} {status}（来源：{source}，请自行查证，非医疗建议）",
    "summary_stale": "Not today. ",
    "summary_none": "No metrics selected. ",
    "summary_sparse": "Selected metrics are not counted in daily coverage. ",
    "summary_cover": "{n} of {total} selected metrics have data.",
    "summary_prior": "{n} prior-day value(s)",
    "summary_partial": "{n} in progress",
    "summary_join": ", including {bits}.",
    "summary_missing": "{labels} have no record and are not backfilled. ",
    "summary_dir": "{label} is {dir} your {phrase} level. ",
    "dir_below": "below",
    "dir_above": "above",
    "dir_typical": "near",
    "summary_no_hist": "{label} has no history; no band yet. ",
    "summary_hist_short": "{label} personal history {n}/7 days; no band yet. ",
    "summary_comp": "Card composite: {label}.",
    "advice_empty_sel": "Select metrics at the bottom of the full card.",
    "advice_sparse": "Sparse metrics show the latest reading only and do not count toward daily coverage.",
    "advice_empty": "No numbers for the selected metrics, so there is no assessment.",
    "advice_coverage": "Sync the missing items first, then assess recovery.",
    "advice_below": "Some metrics are below your personal baseline; consider an easier day.",
    "advice_short": "Some metrics have fewer than 7 history days; numbers only, no band yet.",
    "advice_typical": "Metrics with data are roughly similar to or better than your personal baseline.",
    "advice_missing": "No record in this metric's freshness window; an older number is not used instead.",
    "advice_partial": "{label}{until}cumulative, in progress (not missing), no band.",
    "advice_unknown_none": "{label} has no history; no band yet.",
    "advice_unknown_n": "{label} personal history {n}/7 days; no band yet.",
    "advice_below_line": "{label} is below your {phrase} level.{easy}",
    "advice_above_line": "{label} is above your {phrase} level.{easy}",
    "advice_typical_line": "{label} is near your {phrase} median.",
    "easy_tail": " Consider an easier day.",
    "sleep_verify": "{label} {shown}{unit}, clearly {dir} your {phrase} level — check this night in the Health app",
    "notif_title": "PHA fact card · {day}",
    "notif_empty": "No wearable daily rows. Open the full card. {disclaimer}",
    "notif_stamp": "As of {as_of}",
    "notif_not_today": " (not today)",
    "notif_cover": "{stamp} · {present}/{total} with data{extra}{verify}\nOpen the full card for the list and assessment. {disclaimer}",
    "loop_h2": "Loop approvals (ops)",
    "loop_lead": "Weekly harvest found alias proposals. Approve applies them on this Mac only (data/loop_local_aliases.json) — repo catalog unchanged. Reject dismisses this item.",
    "loop_none": "No pending Loop approvals.",
    "loop_local_active": "Active on this Mac: {n} local alias(es).",
    "loop_item": "{n} alias(es)",
    "loop_approve": "Approve · apply on this Mac",
    "loop_reject": "Reject",
    "loop_empty_aliases": "(no alias lines)",
    "title": "PHA fact card · {day}",
    "h1": "PHA fact card",
}

_ZH: dict[str, str] = {
    "disclaimer": "教育参考，非医疗建议，不能替代医师诊治。",
    "none": "无",
    "today": "当日",
    "not_today": "非今日",
    "coverage": "覆盖 {present}/{total}",
    "calendar": "日历日 {day}",
    "as_of": "截至 {day}",
    "facts": "事实",
    "assessment": "评估",
    "advice_label": "建议：",
    "composite": "卡级综合：{label}",
    "interpret_h2": "AI 解读（实验）· 非医疗建议",
    "interpret_fine": "仅在你点按钮后调用本机模型；不进通知，不替代上方规则评估。",
    "generate": "生成解读",
    "retry": "重试",
    "idle": "尚未生成。点下方按钮才会调用本机模型。",
    "pending": "生成中，可先关掉，稍后刷新。",
    "model_unavailable": "本机模型未响应",
    "exclusive_scope_empty": "点名指标不在今日卡上，未生成解读。",
    "audit_rejected_toks": "模型写了卡上没有的数字（{toks}），已整段丢弃，可重试",
    "audit_rejected": "未生成（审计未通过）",
    "audit_hint_after_fail": "解读只能引用卡上的数字；一般常识可写整数，不要写小数。",
    "audit_cat_value": "卡上没有的测量值：{toks}",
    "audit_cat_date": "不在卡上的日期：{toks}",
    "audit_cat_window": "卡上没有的窗口：{toks}",
    "audit_cat_forgery": "参考标准块里写了你的数据",
    "model_meta": "模型 {model} · 生成于 {at}",
    "bg_brief_used": "已参考你在对话中自述的 {n} 条背景（不作为数值来源）",
    "assessment_prompt_head": "【用户评估要求 · 本轮解读大纲，不是数值来源】",
    "followup_continue_topic": "继续聊{tok}",
    "followup_look_at_metric": "看看{mk}",
    "bg_brief_title": "用户背景 · 自述 · 非数字源",
    "bg_brief_lead": "以下为用户在对话中的自述背景。本槽在场时，须按槽内已有字面把具体自述项写入建议措辞；不得整槽丢弃，不得只用笼统类别词代替槽内具体项，不得引用为数值，不得复述或给出剂量，不要另起编号注意事项清单。只用相关/伴随措辞，禁止强因果断言。",
    "bg_brief_omitted": "〔数值略〕",
    "bg_brief_rel_week": "近一周内",
    "bg_brief_rel_month": "近一月内",
    "bg_brief_rel_earlier": "更早",
    "bg_brief_cat_supplement": "补剂",
    "bg_brief_cat_medication": "用药",
    "bg_brief_cat_sleep_lifestyle": "睡眠 / 作息",
    "bg_brief_cat_symptom": "症状",
    "bg_brief_cat_general": "一般",
    "bg_brief_split_marks": "上午|中午|晚上|睡前",
    "bg_brief_item_seps": " + |、|/|) |） ",
    "bg_brief_item_glue": " · ",
    "bg_brief_table_headers": "时间|项目|具体内容|核心逻辑",
    "bg_brief_note_caps": "supplement:6|medication:4|sleep_lifestyle:3|symptom:3|general:2",
    "bg_brief_row_caps": "supplement:20|medication:6|sleep_lifestyle:4|symptom:4|general:2",
    "bg_lineage_stub_marks": "今日值|百分位|基线夜数|基线天数",
    "metrics_h2": "我要看哪些指标",
    "metrics_help": "勾选只决定卡上显示与评估；数据由捷径按优先级包同步。改勾选后刷新即可；新勾选项的当日值在下一次捷径运行后出现。只有注册表新增健康类型（捷径包版本变化）时才需要重新生成捷径。zip 导入会覆盖同日捷径增量，建议每季度回灌一次 export.zip。",
    "prompt_h3": "我的评估要求",
    "prompt_help": "解读只能引用卡上的数字；一般常识可写整数，个人小数必须与卡一致。最多 {max} 字。",
    "prompt_ph": "例如：重点看睡眠，语气平实，别吓人",
    "save": "保存并刷新完整卡",
    "language": "语言",
    "language_help": "只选语言；日期按语言显示，没有单独的日期格式选项。",
    "empty_metrics": "未选择指标。到本页底部勾选要看的项。",
    "hero_kicker": "今日相对你自己",
    "setup_h2": "在这台 iPhone 上完成开通",
    "setup_lead": "这不是对话框。健康数据进到你的 Mac 之后，数字和三档评估会直接出现，不用打字。本机模型是可选的，在下方按钮后面。",
    "setup_1": "Mac 与 iPhone 连同一 Wi-Fi（不要用蜂窝）。iPhone 设置 → 隐私与安全性 → 本地网络 → 打开「快捷指令」。",
    "setup_2": "跑一次「PHA Daily」（健康 Find 每一项都点允许）。旧安装：先「PHA 同步睡眠」，再「PHA 同步健康」，再「PHA 事实卡通知」。",
    "setup_3": "本页应出现数字。若 Safari 连不上，说明手机打不到这台 Mac。",
    "setup_4": "快捷指令 → 自动化 → 特定时间 → PHA Daily，打开「立即运行」。",
    "latest": "{day}，最近一次",
    "until": "截至 {hm}",
    "hk_ok": "最近一次 HealthKit 样本行：{metric} @ {at}。",
    "hk_none": "账本里还没有 HealthKit 入库行。健康 App 有数也不会出现在这张卡上。",
    "sync_ok": "上次同步成功：{at} · {kind}{extra}",
    "sync_fail": "上次同步失败：{at} · {kind} · {err}",
    "sync_empty": "上次同步：{at} · {kind} · 健康 App 尚无该项样本（未写入，不是同步失败）",
    "sync_plain": "上次同步：{at}",
    "sync_none": "尚无捷径同步回执（跑过「PHA 同步睡眠 / 健康」后这里会显示上次成功或失败）。",
    "pack_stale": " 捷径包已过期（设备 {got}，当前 {expected}），请在 Mac 重新生成并替换「PHA 同步健康」。",
    "wake": " · 醒来日 {day}",
    "asleep": " · 入睡 {hours}h",
    "fail": "失败",
    "hint_sleep": "由睡眠捷径同步",
    "hint_quantity": "由健康捷径同步",
    "hint_history": "暂无捷径同步，仅展示历史",
    "window_90d": "近 90 日 {n} {unit}",
    "window_365d": "近 12 个月 {n} {unit}",
    "window_all": "全部历史（自 {since}）{n} {unit}",
    "window_short": "个人历史 {n}/7 {unit}",
    "unit_night": "夜",
    "unit_day": "天",
    "comp_none": "不综合",
    "comp_easy": "偏轻松",
    "comp_good": "偏好",
    "comp_typical": "持平",
    "ref_within": "在范围内",
    "ref_below": "低于参考范围",
    "ref_above": "高于参考范围",
    "ref_note": "常见建议范围",
    "ref_text": "【参考标准】{title} {span}，你今日 {shown}{unit} {status}（来源：{source}，请自行查证，非医疗建议）",
    "summary_stale": "不是今日。",
    "summary_none": "未选择任何指标。",
    "summary_sparse": "已选指标不计入每日覆盖率。",
    "summary_cover": "已选{total}项中{n}项有数。",
    "summary_prior": "{n}项为前一日值",
    "summary_partial": "{n}项进行中",
    "summary_join": "，其中{bits}。",
    "summary_missing": "{labels}无记录，不顶。",
    "summary_dir": "{label}{dir}你{phrase}的水平。",
    "dir_below": "低于",
    "dir_above": "高于",
    "dir_typical": "接近",
    "summary_no_hist": "{label}无历史，暂不分档。",
    "summary_hist_short": "{label}个人历史 {n}/7 天，暂不分档。",
    "summary_comp": "卡级综合：{label}。",
    "advice_empty_sel": "到完整卡底部勾选要看的指标。",
    "advice_sparse": "稀疏指标只展示最近一次读数，不参与每日覆盖率。",
    "advice_empty": "库内无已选指标数字，无法评估。",
    "advice_coverage": "先把缺项同步进库，有数后再做恢复向评估。",
    "advice_below": "有指标低于个人基线，可考虑偏轻松安排。",
    "advice_short": "有指标历史不足 7 天，只展示数字、暂不分档。",
    "advice_typical": "有数指标相对个人基线大致持平或偏好。",
    "advice_missing": "该指标时效窗口内无记录，不用更早的数字代替。",
    "advice_partial": "{label}{until}累计，进行中（不是缺失），不分档。",
    "advice_unknown_none": "{label}无历史，暂不分档。",
    "advice_unknown_n": "{label}个人历史 {n}/7 天，暂不分档。",
    "advice_below_line": "{label}低于你{phrase}的水平。{easy}",
    "advice_above_line": "{label}高于你{phrase}的水平。{easy}",
    "advice_typical_line": "{label}接近你{phrase}的中位。",
    "easy_tail": "可考虑偏轻松安排。",
    "sleep_verify": "{label} {shown}{unit}，明显{dir}你{phrase}的水平，请到健康 App 核对这一夜的数据",
    "notif_title": "PHA 事实卡 · {day}",
    "notif_empty": "库内无穿戴日行。打开完整卡。{disclaimer}",
    "notif_stamp": "截至{as_of}",
    "notif_not_today": "（非今日）",
    "notif_cover": "{stamp} · {present}/{total}有数{extra}{verify}\n打开完整卡看清单与评估。{disclaimer}",
    "loop_h2": "Loop 审批（运维）",
    "loop_lead": "周更 harvest 发现别名提案。同意后只写入本机 data/loop_local_aliases.json，本机对话立刻可用；不改仓库 catalog。拒绝即关闭本条。",
    "loop_none": "当前没有待审的 Loop 提案。",
    "loop_local_active": "本机已生效：{n} 条本地别名。",
    "loop_item": "{n} 个别名",
    "loop_approve": "同意 · 本机生效",
    "loop_reject": "拒绝",
    "loop_empty_aliases": "（无别名行）",
    "title": "PHA 事实卡 · {day}",
    "h1": "PHA 事实卡",
}


def is_en_locale(locale: Optional[str]) -> bool:
    return normalize_fact_card_locale(locale) == "en-US"


def format_audit_violations(violations: list[Any], *, locale: Optional[str] = None) -> str:
    """Dedupe and group audit tokens for UI (no raw repeated SpO2 '2' spam)."""
    values: list[str] = []
    dates: list[str] = []
    windows: list[str] = []
    forgery = False
    other: list[str] = []
    seen: set[str] = set()
    for raw in violations or []:
        item = str(raw)
        if item in seen:
            continue
        seen.add(item)
        if item == "t0_forgery_in_t1_block":
            forgery = True
            continue
        if ":" not in item:
            other.append(item)
            continue
        kind, tok = item.split(":", 1)
        if kind == "unauthorized_value":
            values.append(tok)
        elif kind == "unauthorized_date":
            dates.append(tok)
        elif kind == "unauthorized_window":
            windows.append(tok)
        else:
            other.append(tok if tok else item)
    parts: list[str] = []
    if values:
        parts.append(card_copy(locale, "audit_cat_value", toks="、".join(values[:6])))
    if dates:
        parts.append(card_copy(locale, "audit_cat_date", toks="、".join(dates[:4])))
    if windows:
        parts.append(card_copy(locale, "audit_cat_window", toks="、".join(windows[:4])))
    if forgery:
        parts.append(card_copy(locale, "audit_cat_forgery"))
    if other:
        parts.append("、".join(other[:4]))
    return "；".join(parts)


def card_copy(locale: Optional[str], key: str, **kwargs: Any) -> str:
    bag = _EN if is_en_locale(locale) else _ZH
    template = bag.get(key) or _EN.get(key) or _ZH.get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template


def js_copy(locale: Optional[str]) -> dict[str, str]:
    keys = (
        "idle",
        "pending",
        "model_unavailable",
        "exclusive_scope_empty",
        "audit_rejected_toks",
        "audit_rejected",
        "audit_hint_after_fail",
        "model_meta",
        "bg_brief_used",
        "generate",
        "retry",
    )
    return {k: card_copy(locale, k) for k in keys}


def group_label(group_zh: str, locale: Optional[str]) -> str:
    raw = (group_zh or "").strip() or "其他"
    if is_en_locale(locale):
        return GROUP_EN.get(raw, raw)
    return raw
