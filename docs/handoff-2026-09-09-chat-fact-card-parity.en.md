# Handoff · 2026-09-09 · Chat ↔ Fact Card interpretation parity

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-09-chat-fact-card-parity.md)

> Status: **encoded · offline selfcheck green · on-device 8788 accepted** (Waves A–F; H10–H13/H10E/H13E skip-LLM; H9-zh chat+interpret; H9E audit passed. Transcript: proactive change-log 16:51)
> Change class: Harness **P1** (includes one P0 config-source-of-truth convergence)
> Governing: [`pha-pm-constitution.md`](pha-pm-constitution.md) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) · [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) · [`wearable-metric-registry-v1.md`](wearable-metric-registry-v1.md)
> Predecessor: [`handoff-2026-09-09-proactive-memory-sharing.md`](handoff-2026-09-09-proactive-memory-sharing.md) (P13/P14 DONE)

---

## 0. Start passphrase and required reading (coding agent first reply must output)

```text
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read
```

Read order: `.cursor/rules/pha-mandatory-reads.mdc` global 1–8 → `wearable-metric-registry-v1.md` → `harness-tier0-fuse-v2.2.6.1.md` → this document.

Hard red lines (this track entire duration):

- TurnEvidencePlan before LLM; Profile locks only after Harness Arbiter.
- Any user-visible number must ⊆ Numerics Manifest; the LLM does not write numbers.
- **Must not** add Python-internal phrase / metric / label hardcode tables; all lexicons, clusters, labels go into JSON sources of truth (Registry / Intent Catalog).
- Must not add special-case branches to green H9–H13 goldens; use catalog + Arbiter + session anchors.
- fail-closed: if not found, say not found; **forbid** silently switching time grain or metric.
- Each Wave independent feature flag, rollbackable; same PR updates change-log and selfcheck.

---

## 1. Telemetry evidence (Constitution §2 · ticket from pain)

### 1.1 On-device contrast (same model `qwen3:14b`, same prompt, same ledger)

| Item | iOS proactive card (`fact_card_interpret`) | Mac web chat (`wearable_only`) |
|---|---|---|
| Metrics entering T0 | User-checked 9 + each 90d baseline/percentile | Two lines: `今日HRV 32.83ms`, `今日睡眠 8.22h` |
| Sleep substages | Deep / REM / core / awake all visible | Invisible; asked three times still only total duration |
| Resting HR | Present (Registry `temporal.daily_lagged`, takes 09-08 value and labels the date) | Absent (chat side point-day is strict same-day; 09-09 RHR empty) |
| “Is there really no sleep data today? Please verify” | — | Deterministic template: `今日睡眠：8.22h` (never entered LLM) |
| “How much core sleep? Deep? Awake in sleep?” | — | Silently switched to 90d: `睡眠均值 7.34h`, and answered none of the three substages |
| Output structure | Chinese, status assessment → related → training advice | English headings `Trend review / Related markers / Recommendations` |

### 1.2 Ledger check (`data/pha_storage.db` · `wearable_daily` · read-only)

```text
2026-09-09  sleep_hours=8.2167  sleep_deep_hours=0.4667  sleep_rem_hours=2.45
            sleep_core_hours=5.3  awake_duration_hours=0.7833  hrv_sdnn_ms=32.83
            resting_heart_rate_bpm=NULL  steps=67
2026-09-08  resting_heart_rate_bpm=62.0  sleep_hours=6.2  sleep_deep_hours=0.9 ...
```

Conclusion: **data sharing is fine** (both ends read the same SQLite). Differences all arise on the chat-side “metric resolve → fetch → route → template” chain.

### 1.3 Root-cause location (code level)

| # | Root cause | Location |
|---|---|---|
| R1 | Chat-side metric lexicon `wearable_bundle.schema.json` has only 9 catalog keys (`sleep` is total duration only), vs Registry 17 rows (including `sleep_deep/rem/core/awake/in_bed`) — **dual-catalog drift** | `storage/schemas/wearable_bundle.schema.json` vs `storage/registry/wearable_metric_registry.json` |
| R2 | `get_health_data` only recognizes catalog keys; `_metric_value` is an if-chain; Registry `l1.field` is unused on the chat-side fetch | `pha/health_data.py:80-110, 269-293` |
| R3 | catalog key ↔ registry id ↔ zh/en label ternary mapping written separately in **7** Python places | `numerics_manifest._wearable_entries.label_map` / `_focus_to_cat`; `grounded_answer_composer._WAREHOUSE_FOCUS_LABELS_BY_CAT` / `_REGISTRY_TO_WAREHOUSE_LABELS` / `_WAREHOUSE_FOCUS_LABEL_EN` / `_missing_grain_summary.metric_zh`; `wearable_metric_probe._CATALOG_TO_REGISTRY`; `wearable_compare_table_v1._CATALOG_PRIMARY_METRIC` / `_SLEEP_FOCUS_METRIC_IDS` |
| R4 | Registry `intent_hints` already contain “深睡/核心睡眠/睡眠清醒”, but only feed `infer_single_metric_focus_ids` (cap 2 ids); three asked together → fall back to catalog `sleep` single key → skip-LLM only total duration | `wearable_compare_table_v1.infer_single_metric_focus_ids` · `grounded_answer_composer.try_warehouse_metric_focus_skip` |
| R5 | Follow-up with no date words `grain.source == default` → 90d mean; session anchor has no “time grain” dimension | `wearable_time_grain.resolve_wearable_time_grain` · `session_turn_focus` (only profile/metric/goal/domains) |
| R6 | “OK to train?” class hits `_EXERCISE_ADVICE_ONLY_RE` → `_deterministic_exercise_advisory` fixed copy (does not look at data); or lands `wearable_only` three-step medical soul | `wearable_compare_table_v1:1010, 1482` · `chat_turn_slots.py:60-70` soul select |
| R7 | `fact_card_interpret` TASK/soul/T0 assembly only fires on `profile == "fact_card_interpret"` string; chat cannot reuse | `chat_turn_slots.py:66, 295, 300, 342, 418` |

---

## 2. Design self-review: original suggestion vs consensus (already corrected)

| Original suggestion | Risk | Corrected approach |
|---|---|---|
| “Add Chinese trigger words: 深睡, REM…” | If written in Python = phrase hardcode | Words already in Registry `intent_hints`; **do not add words, fix the pipe** (Wave B) |
| “Sleep cluster expand” | If using `_SLEEP_FOCUS_METRIC_IDS`-class frozenset = hardcode | Registry adds `catalog.cluster`; cluster members declared in JSON (Wave A) |
| “New training-readiness intent + trigger words” | If adding regex = violates “forbid expanding rules with per-sentence if-else” | 3F `goal_markers.daily_readiness` into `health_intent_catalog.json`; Arbiter adds one policy row; `_EXERCISE_ADVICE_ONLY_RE` retired to fallback (Wave C) |
| “schema derived from registry” | `wearable_bundle.schema.json` is a signed evidence asset with `contract` | Generate script only rewrites `catalog.trigger_keywords / core_hint_keywords / metrics.*`, keeps `contract` and bumps `schema_version`; selfcheck asserts zero drift (Wave A) |
| “Unify labels” | `今日睡眠`/`睡眠均值` are audit tokens; changing words would mismatch goldens and old cache | Registry adds `catalog.label_zh/label_en`; **freeze test**: derived labels == existing 9-key hardcoded labels, character-for-character (Wave B) |
| “Web one-tap re-interpret” | `_PROFILE_FOLLOWUPS` itself is Python hardcode; should not expand | follow_ups into catalog `follow_ups` section; payload uses existing chip protocol (Wave E) |
| “Open `USER_BACKGROUND_BRIEF` for `wearable_only`” | Overlaps `USER_CONTEXT_BRIEF`, expands P14 scope | Open only on the new profile (isomorphic with the card); `wearable_only` untouched |
| “Chat side uses Registry `temporal` to take yesterday’s RHR” | Would make “today’s resting HR” label point at yesterday’s value, violating T0 ledger semantics | New profile inherits the card directly (card already labels the day by anchor); `wearable_only` keeps strict same-day + fail-closed hint (Wave B/E) |

Self-review conclusion: after correction, no new Python hardcode, no consumer-side special-case branches, TurnEvidencePlan / Numerics audit / Harness Veto not weakened, LLM does not write numbers, each Wave has a flag and rollback.

---

## 3. Goals and non-goals

**Goals**

1. Chat side and fact card use **the same metric source of truth** (Registry); lexicons / clusters / labels / column names no longer each written once.
2. “Today’s sleep data” class questions return the **whole cluster** and per-item fail-closed.
3. “Today’s status / can I train” class questions get **same-kind** interpretation in chat as the proactive card (same T0 assembly, same TASK, same soul, same background brief, same audit).
4. Weak follow-ups with no date words may inherit the previous turn’s point-day grain (session anchor adds a dimension).
5. The user can see “metrics that entered interpretation this turn / available same-day but not selected”.

**Non-goals**

- Do not change iOS card UI, ingest, or `fact_card_interpret` cache key and audit policy.
- Do not touch `wearable_screenshot_review` / attachment lanes.
- Do not let the LLM participate in metric selection or SQL.
- Do not add new synthetic metrics such as “body age”.

---

## 4. Architecture: Registry single source of truth → all derived

```text
storage/registry/wearable_metric_registry.json   (sole source of truth; add catalog.* fields)
   │
   ├─(generate)→ storage/schemas/wearable_bundle.schema.json  catalog.trigger_keywords / core_hint_keywords / metrics.canonical|core
   ├─(runtime read)→ pha/health_data.py       metric key resolve, column names, units, hrv fallback
   ├─(runtime read)→ pha/numerics_manifest.py  point-day/span labels (今日X / X均值)
   ├─(runtime read)→ pha/grounded_answer_composer.py  focus labels, EN labels, missing copy
   ├─(runtime read)→ pha/wearable_metric_probe.py / wearable_compare_table_v1.py  catalog→registry, cluster, cluster primary
   └─(runtime read)→ pha/fact_card*.py         (already a Registry consumer, unchanged)

rules/health_intent_catalog.json                  goal_markers.daily_readiness · follow_ups
rules/harness_profile_registry.generated.json     new profile wearable_daily_review (--write regenerate)
```

### 4.1 New Registry fields (each `metrics[]` row)

```json
"catalog": {
  "key": "sleep",                 // chat-side catalog key (same namespace as wearable_bundle); multiple rows in a cluster may share a key
  "cluster": "sleep",             // cluster id; omit if no cluster
  "cluster_primary": true,        // cluster primary (exactly one true per cluster)
  "expand_on_cluster_query": true,// whether to fetch the whole cluster when any member of the key/cluster hits
  "label_zh": "睡眠",             // audit-label stem: point-day = "{今日|当日}"+label; span = label+"均值"
  "label_en": "sleep",            // EN stem: point-day "Today's {label_en}" / "{label_en} that day"; span "Mean {label_en}"
  "mean_suffix_zh": "均值"        // optional; default "均值"; activity_kcal currently "日均", must declare explicitly to keep freeze equal
}
```

Constraints (into `pha_wearable_registry_selfcheck.py`):

- `catalog.key` set ⊇ existing bundle `metrics.canonical` 9 keys; `cluster_primary` unique per cluster; `label_zh` unique within the same key or consistent with the key’s primary row.
- **Bilingual mandatory**: every row with `catalog.key` must have both `catalog.label_zh` and `catalog.label_en` non-empty; `intent_hints` must contain ≥1 CJK token and ≥1 Latin token (selfcheck asserts). Also fill `ui.label_en` so `wearable_metric_registry._METRIC_LABEL_EN_FALLBACK` can be deleted (see §10).
- Derived `wearable_bundle.schema.json` byte-equal to the in-repo file except `schema_version`/`contract.revision`.
- Derived-label freeze: for the 9 old keys, `{point-day,span}×{zh,en}` labels must equal the hardcoded values before Wave B (test embeds the old-table snapshot; **only the test file may contain that snapshot**).

First-batch fills (character-for-character with live labels):

| metric_id | key | cluster | primary | label_zh | label_en | Notes |
|---|---|---|---|---|---|---|
| sleep_time_asleep | sleep | sleep | ✅ | 睡眠 | sleep | |
| sleep_deep | sleep | sleep | | 深睡 | deep sleep | |
| sleep_rem | sleep | sleep | | REM | REM | |
| sleep_core | sleep | sleep | | 核心睡眠 | core sleep | |
| sleep_awake | sleep | sleep | | 睡眠清醒 | awake in sleep | |
| sleep_in_bed | sleep | sleep | | 在床 | in bed | `expand_on_cluster_query:false` (default not expand, avoid noise) |
| hrv_sdnn_ms | hrv | cardiac | ✅ | HRV | HRV | |
| hrv_rmssd_ms | hrv | cardiac | | — | — | `catalog.hidden:true`, only a `display_fallback` source |
| resting_heart_rate_bpm | rhr | cardiac | | 静息心率 | resting HR | |
| steps | steps | activity | ✅ | 步数 | steps | |
| active_energy | activity_kcal | activity | | 活动消耗 | active kcal | `mean_suffix_zh:"日均"` |
| spo2_percent | spo2 | — | | 血氧 | SpO2 | |
| respiratory_rate | respiratory_rate | — | | 呼吸率 | respiratory rate | |
| vo2max | vo2max | — | | VO2max | VO2max | |
| wrist_temp | wrist_temp | — | | 手腕体温 | wrist temp | Live point-day label is “手腕体温”, not `ui.label_zh` “睡眠腕温”, so `catalog.label_zh` is a separate column |
| workout_* | — | — | | | | No catalog key (not in get_health_data) |

---

## 5. Per-Wave design

### Wave A (P0 · config source-of-truth convergence · no behavior change)

**Changes**

1. `wearable_metric_registry.json`: add `catalog.*` per §4.1; bump `version`.
2. `pha/wearable_metric_registry.py` add read-only accessors (English names, pure functions, lru_cache):
   - `catalog_key_for(metric_id) -> str|None`
   - `metric_ids_for_catalog_key(key) -> tuple[str,...]` (registry file order)
   - `cluster_members(cluster_id, *, expand_only=True) -> tuple[str,...]`
   - `cluster_primary_metric_id(cluster_id) -> str|None`
   - `cluster_of(metric_id) -> str|None`
   - `catalog_labels(metric_id) -> CatalogLabels(point_zh, span_zh, point_en, span_en, that_day_zh, that_day_en)`
   - `catalog_keys_canonical() -> tuple[str,...]` / `catalog_keys_core()` (core = `fact_card.enabled_default` and has a key; primary rows, deduped)
   - `bundle_trigger_keywords() -> list[dict]` (from `intent_hints` × `catalog.key`; fields same as current schema: `token/metric_id/zh`)
3. New script `scripts/pha_wearable_bundle_schema_generate.py [--write]`: read Registry, rewrite bundle schema `catalog.trigger_keywords`, `catalog.core_hint_keywords`, `metrics.canonical`, `metrics.core`; keep other fields; `--check` non-zero means drift.
4. `scripts/pha_wearable_registry_selfcheck.py` adds §4.1 three constraints + `--check` call.
5. `scripts/run_selfchecks.sh` / `selfcheck_manifest.json` register.

**Acceptance**: `pha_wearable_registry_selfcheck.py` green; `pha_wearable_bundle_schema_generate.py --check` zero drift; `pha_catalog_registry_selfcheck.py`, `pha_dch_selfcheck.py` still green (signed asset not broken).

**Rollback**: Registry new fields are additive; delete the fields; no runtime consumers.

---

### Wave B (P0 · chat-side fetch and labels become Registry-driven · cluster expand · per-item fail-closed)

Flag: `PHA_WEARABLE_REGISTRY_CATALOG` (default `1`; set `0` takes the old hardcoded path until B.2 deletes it).

**B.1 `pha/health_data.py`**

- `METRIC_ALIASES` / `CORE_WEARABLE_METRICS` / `EXTENSION_WEARABLE_METRICS`: keep constant names (many external refs), but values become Registry-derived: `ALLOWED_METRICS = catalog_keys ∪ registry metric_ids (l1.kind == wearable_daily)`.
- `_partition_requested_metrics`: look up `METRIC_ALIASES` first, then Registry `metric_id`, then `catalog.key`.
- `_metric_value(row, metric)`:
  - If `metric` is a registry id → `getattr(row, l1.field)`; if None and the row has `fact_card.display_fallback_metric_id` → take the fallback column (covers the existing hrv SDNN→RMSSD special).
  - If `metric` is a catalog key → take that key’s `cluster_primary` row (or the only row) and evaluate as above.
  - Delete the if-chain.
- `_metric_unit(metric)`: Registry `fact_card.unit` (else `snapshot.unit`).
- `summaries` keys returned by `get_health_data(..., metrics)`: **keep catalog key** as backward-compat primary? add registry-id keys with `registry:` prefix? — **rejected**: change `summaries` keys to unified **registry metric_id**, and add `catalog_key_of: dict[str,str]` on `HealthDataResult`; all consumers (manifest, summary block, analytics) map via accessors. Coding agent must grep all `.summaries` consumers and switch one by one; `pha_stage3c_wearable_selfcheck.py`, `pha_wearable_p15_selfcheck.py` are the regression net.

**B.2 Cluster expand (`pha/intent_gates.py` + `pha/catalog_dch.py`)**

- `infer_wearable_metrics(msg)` return semantics unchanged (catalog keys), but add `infer_wearable_metric_ids(msg) -> list[str]` (registry ids):
  1. `_hint_match_metric_ids(msg)` (Registry `intent_hints`, already exists; move into `wearable_metric_registry.py` public as `hint_match_metric_ids`).
  2. For each hit catalog key / cluster member: if the cluster `expand_on_cluster_query` and flag `PHA_WEARABLE_CLUSTER_EXPAND=1` (default 1) → add `cluster_members(cluster)`.
  3. If empty and `default_if_wearable_query` → primary rows corresponding to `catalog_keys_core()`.
- `_STAGE_HINT_RE`, `_WORKOUT_HINT_RE` (`wearable_metric_probe.py`) retire: `睡眠分期/分期` **and English `sleep stage`/`sleep stages`** together into `sleep_deep`/`sleep_rem` `intent_hints` (JSON); workout words already in `intent_hints` (zh+en).
- `_COMPARE_ALL_METRICS_RE` (zh-only: 所有指标|各项指标|整体…) moves into catalog `broad_compare.tokens` and add English (`all metrics`, `every metric`, `overall`, `compare all`); Python only reads catalog.
- `_CATALOG_TO_REGISTRY`, `_CATALOG_PRIMARY_METRIC`, `_SLEEP_FOCUS_METRIC_IDS`, `_WORKOUT_FOCUS_METRIC_IDS`, `_SINGLE_METRIC_FOCUS_MAX` → replaced by `cluster_*` accessors; `_is_allowed_focus_pair` becomes “same cluster is allowed”; cap becomes “≤ that cluster’s member count”.

**B.3 Point-day fetch: `get_health_data` uses registry ids**

- `numerics_manifest._wearable_entries`: `metrics = infer_wearable_metric_ids(msg)`; delete `label_map`, use `catalog_labels(mid)`; delete `_focus_to_cat`.
- `harness_plan.build_wearable_90d_summary_block`: same; default `["hrv","activity_kcal"]` becomes the first two of `metrics.core` order among `catalog_keys_core()` primary rows (Registry-derived, not literals).

**B.4 Focus skip-LLM path per-item fail-closed (`grounded_answer_composer.py`)**

- Delete `_WAREHOUSE_FOCUS_LABELS_BY_CAT` / `_REGISTRY_TO_WAREHOUSE_LABELS` / `_WAREHOUSE_FOCUS_LABEL_EN` / `_missing_grain_summary.metric_zh|en`; use `catalog_labels`.
- `is_warehouse_metric_focus_turn`: condition becomes `requested_ids = infer_wearable_metric_ids(msg)`, and all `requested_ids` belong to **the same cluster** (or a single metric) → True. Three sleep substages asked together → True (same cluster).
- `_filter_manifest_to_metric_focus(manifest, msg)` signature becomes `(manifest, requested_ids)`: filter by `catalog_labels(mid).point_zh|span_zh`.
- `build_manifest_metric_focus_summary` adds param `missing_ids: list[str]`; for `requested_ids − manifest hit ids`, append one line per:
  - zh: `库内没有 {anchor} 的{label_zh}记录，不会用其他日期或其他指标的数字代替。`
  - en: `No verified {label_en} in your records for {anchor}. Not filled from another date or metric.`
  - If `manifest` empty and `missing_ids` non-empty → output only missing lines (no longer return empty string for the LLM to fall back).
- `try_warehouse_metric_focus_skip`: no longer judge by `len(infer_wearable_metrics)==1`; use B.4 second condition; construct `requested_ids` once and thread through.

**B.5 Freeze and delete**

- Freeze test (`pha_numerics_manifest_selfcheck.py`): 9 old keys × 4 labels character-for-character equal to old values.
- After B.1–B.4 done and all selfchecks green under flag=1, same PR deletes old hardcoded tables and the flag `0` branch (keep reading the flag one version for emergency rollback = reading `0` raises `RuntimeError("legacy path removed; rollback by git")` and the change-log names the rollback commit).

**Harness report new field** (`harness_report_v11`):

```json
"wearableMetricResolution": {
  "requestedCatalogKeys": ["sleep"],
  "requestedMetricIds": ["sleep_time_asleep","sleep_deep","sleep_rem","sleep_core","sleep_awake"],
  "clusterExpanded": ["sleep"],
  "grain": {"start":"2026-09-09","end":"2026-09-09","source":"explicit_today"},
  "missingForGrain": ["sleep_in_bed"]
}
```

**Acceptance**: goldens H10 / H12 / H13 (§8); `pha_grounded_composer_selfcheck.py`, `pha_wearable_metric_probe_selfcheck.py`, `pha_numerics_manifest_selfcheck.py`, `pha_stage3c_wearable_selfcheck.py`, `pha_e2e_wearable_focus_battery.py` green; `pha_fact_card_selfcheck.py` unaffected still green.

**Rollback**: `PHA_WEARABLE_REGISTRY_CATALOG=0` (before B.5); after B.5 git revert the single PR.

---

### Wave C (P1 · `daily_readiness` goal + new profile `wearable_daily_review` reuses the fact-card pipe)

Flag: `PHA_DAILY_READINESS_PROFILE` (default `0`, flip to `1` after acceptance).

**C.1 Intent Catalog (`rules/health_intent_catalog.json`)**

```json
"goal_markers": {
  "holistic_assessment": {
    "tokens": ["综合", "整体", "评估", "各项指标", "全面", "大健康", "身体年龄",
               "overall", "comprehensive", "assessment", "all my metrics", "how am i doing", "body age"],
    "notes": "same PR fills English tokens (3F original table zh-only, see §10)"
  },
  "daily_readiness": {
    "tokens": ["训练", "力量训练", "高强度", "运动强度", "运动类型", "恢复", "准备度", "身体状态", "今天状态",
               "适合运动", "能不能练", "可以锻炼", "strength training", "readiness", "recovery",
               "train today", "workout today", "can i train", "high intensity"],
    "anti_tokens": ["化验", "血脂", "LDL", "lipid"],
    "domain": "wearable",
    "precedence_over": ["holistic_assessment"],
    "notes": "same-day training/recovery readiness assessment; numeric source = fact-card T0; no new metrics"
  }
}
```

- `pha/goal_classifier.classify_goal`: check `daily_readiness` **before** `holistic_assessment` (if `precedence_over` declared and `anti_tokens` not hit and `message_has_lab_marker` is False). `GoalClassification("daily_readiness", 1.0, "catalog")`.
- Do explicit metric tokens still win? — **No**: H9 contains both explicit metrics (HRV/resting HR/sleep) and readiness words. Rule becomes: explicit metric + readiness words → `daily_readiness` (metrics attached as `focus_metric_ids` for C.3 turn-local union); explicit metric without readiness words → `metric_specific` (old behavior). This precedence is written into catalog `goal_markers.daily_readiness.wins_over_explicit_metric: true`, not hardcoded in Python.

**C.2 Harness Arbiter (`pha/harness_arbiter.py`) new policy row**

| goal_class | existence_probe | Behavior | authoritative_profile | arbiter_reason |
|---|---|---|---|---|
| `daily_readiness` | wearable ✓ | upgrade | `wearable_daily_review` | `goal_readiness_daily` |
| `daily_readiness` | wearable ✗ | clarify `data_gap` | `clarify` | `goal_clarify_data_gap` |
| episodic `focus_goal=daily_readiness` + weak question | wearable ✓ | continue goal | `wearable_daily_review` | `episodic_goal_continue` |

When the flag is off, `daily_readiness` is treated as `metric_specific` (fully old behavior).

**C.3 New profile `wearable_daily_review` (`pha/harness_plan.py`)**

```text
profile            = "wearable_daily_review"
slots_tier0        = ["TASK", "USER_ASSESSMENT_PROMPT", "FACT_CARD_CONTEXT", "NUMERICS_MANIFEST"]
slots_tier1        = ["USER_BACKGROUND_BRIEF"]
forbidden          = same as fact_card_interpret (_FACT_CARD_INTERPRET_FORBIDDEN)
tools_allowed      = []
task_text          = fact_card_interpret_task_text(locale)   # reuse 5 rules; rule 5 already includes USER_BACKGROUND_BRIEF
legacy_question_type = WEARABLE
memory_write_policy  = "chat"        # different from fact_card_interpret (none): chat self-report must enter memory (P13 rule)
```

- `USER_ASSESSMENT_PROMPT` = **this turn’s user message original** (the chat question is the assessment outline; same semantics as the card).
- `FACT_CARD_CONTEXT` / `NUMERICS_MANIFEST`: reuse `load_fact_card` + `build_fact_card_numerics_manifest`.
- `resolve_profile_override` and registry `--write` register the new profile; `profile_slot_invariants` add: a profile containing `FACT_CARD_CONTEXT` must contain `NUMERICS_MANIFEST` and `USER_ASSESSMENT_PROMPT`.

**C.4 Fact-card turn-local metric set**

- `pha/fact_card.load_fact_card(user_id, *, reference=None, enabled_metric_ids=None, locale=None)` adds pass-through to `compose_fact_card(enabled_metric_ids=..., locale=...)`; `compose_fact_card` adds `locale`; **only when empty** fall back to `load_fact_card_locale(user_id)` (today it unconditionally reads iOS card prefs, see §10-F1). Chat side must pass this turn’s `response_locale`, else an English user gets Chinese label/window copy in `FACT_CARD_CONTEXT`, triggering `apply_english_locale_leak_guard` to replace the whole interpretation with a deterministic fallback — zh/en quality inequality.
- Chat side: `ids = load_enabled_metric_ids(uid) ∪ {m ∈ infer_wearable_metric_ids(msg) | registry.fact_card.eligible}`; **this turn only**, do not write prefs.
- `reference`: if `resolve_wearable_time_grain(msg).is_point_day()` → that day; else `effective_query_reference_date()`. Non-point-day span questions (“last 90 days status”) are not `daily_readiness`; jointly excluded by `anti/precedence` and grain: grain not point-day and not default → `metric_specific`.

**C.5 Remove string specials (`pha/chat_turn_slots.py`)**

Change the 5 `plan.profile == "fact_card_interpret"` checks to slot checks:

- soul select (:66) → `"FACT_CARD_CONTEXT" in plan.slots_tier0` → `PHA_FACT_CARD_SOUL_MINIMAL`
- background_block empty (:295), recalled_snippets empty (:300) → same condition
- manifest assembly (:342) → same; when `card` empty `load_fact_card(uid, reference=..., enabled_metric_ids=...)` (params carried by ctx)
- TASK select (:418) → same
- `USER_BACKGROUND_BRIEF` branch (:451) already judges by `slots_tier1`; no change.
- `USER_ASSESSMENT_PROMPT` slot head (:445) currently zh literal `【用户评估要求 · 本轮解读大纲，不是数值来源】`: change to `card_copy(locale, "assessment_prompt_head")`, add zh/en in `fact_card_copy.py`; iOS card path benefits too (eliminates CJK slot head in en card system prompt).

**C.6 Retire fixed copy**

- `_EXERCISE_ADVICE_ONLY_RE` and `_deterministic_exercise_advisory`: when flag=1 no longer the main path; only fail-closed fallback when `wearable_daily_review` fails with `model_unavailable`, and copy **contains no intensity conclusion** (“model temporarily unavailable; below are today’s ledgered numbers: …” + manifest focus rows). flag=0 keeps old behavior.

**C.7 Language**

- `fact_card_interpret_task_text(locale)` called with `response_locale`; EN request → EN, ZH request → ZH; existing `apply_english_locale_leak_guard` stays. Acceptance: ZH question replies must not contain `Trend review|Related markers|Recommendations` headings (add to `pha_response_language_selfcheck.py`).

**Tier0 budget**: isomorphic with `fact_card_interpret` (9 metrics + background brief already accepted under `SYSTEM_CONTENT_MAX_CHARS=12000`). Chat multi-turn history is in user/assistant messages, not system. Acceptance: harness report has no `tier0_budget_exceeded|cap_system_truncated` (must also pass at 9 metrics + 5 sleep substages = at most 14 rows; if over, cut `USER_BACKGROUND_BRIEF` first then WARN; **must not** cut T0).

**Acceptance**: golden H9; `pha_goal_arbiter_selfcheck.py`, `pha_harness_profile_registry_selfcheck.py`, `pha_chat_turn_routing_selfcheck.py`, `pha_harness_report_v11_selfcheck.py` green; in-process acceptance 6 rounds (reuse P14 acceptance-script style) audit all pass.

**Rollback**: flag=0.

---

### Wave D (P1 · session anchor adds a time-grain dimension)

Flag: `PHA_EPISODIC_GRAIN_ANCHOR` (default `0`).

- `pha/session_turn_focus.py`: `SessionTurnFocus` adds `focus_grain_start: str`, `focus_grain_end: str`, `focus_grain_aggregation: str` (migration add columns, default `''`). Write when this turn `grain.source != "default"`.
- `pha/wearable_time_grain.resolve_wearable_time_grain(msg, *, reference, episodic=None)`: when `source == "default"` and `episodic.focus_grain_*` non-empty **and `infer_wearable_metric_ids(msg)` non-empty (Registry bilingual hints, language-neutral) and no time words** → return the anchored grain, `source="episodic_anchor"`.
  - **Must not** use catalog `anaphora.tokens` (currently zh-only: 那/这个/继续…) or `weak_followup.close_tokens` (those are thanks-closing words, not weak questions) as inherit conditions, else zh/en behavior disagrees. If anaphora is wanted, the same PR must add `tokens_en` for `anaphora` (that / this / same / continue / previous).
- Expiry: anchor valid only in the same session and within catalog `episodic_grain_ttl_turns` (default 6) of write; user explicit time words always override.
- Harness report: `episodic.focusGrain`.

**Acceptance**: golden H11 two states (flag 0/1); `pha_health_episodic_selfcheck.py`, `pha_stage3c_wearable_selfcheck.py` green.

---

### Wave E (P2 · presentation alignment)

1. `build_fact_card_event` (SSE `fact_card`) adds fields:
   - `label_display`: take `catalog_labels(mid).point_zh|point_en` by `response_locale` (current `label` is a zh audit token; en users see a Chinese card; keep `label` for compat);
   - `metrics_in_scope`: registry ids that entered T0 this turn;
   - `available_not_selected`: ids that have a ledger value that day (or that grain), `fact_card.eligible`, but did not enter T0 (Registry-driven existence probe, reuse `catalog_existence`, do not invent a new probe);
   - `background_notes_used`: same-named field as the card’s `_decorate_interpretation`.
2. follow_ups into catalog: `health_intent_catalog.json` adds `follow_ups.by_profile.{wearable_daily_review,wearable_only}`; each chip must have both `label_zh` / `label_en` (reuse existing bilingual convention of `session_anchor_labels` / `session_anchor_labels_en`); `_PROFILE_FOLLOWUPS` (currently zh-only) reads catalog and picks label by `response_locale` (keep Python constants as catalog-missing fallback one version). In `build_follow_ups_event`, `f"继续聊{tok}"` / `f"看看{mk}"` two zh literals become `card_copy(locale, ...)`. New chip: `{"id":"metric_scope_cluster","label_zh":"加入全部睡眠分项重新解读","label_en":"Re-run with all sleep stages","payload":{"action":"metric_scope","metric_ids":[...cluster members...]}}`; payload next turn as C.4 turn-local union.
3. Web chat renders “cited N background notes” small text, reuse `fact_card_copy.bg_brief_used`.

**Acceptance**: `pha_e2e_combined_review_sse_selfcheck.py` extends SSE field asserts.

---

### Wave F (P3 · regression and governance)

- Goldens H9–H13 into `docs/harness-eval-set-v1.md` and `scripts/pha_e2e_wearable_focus_battery.py` (fixture uses §1.2 two-row data seed, not a live DB).
- `docs/wearable-metric-registry-v1.md` §3 field cheat-sheet adds `catalog.*`; §5 adds “D. Adding a chat lexicon: only change `intent_hints`, run `--check`”.
- `docs/harness-change-log.md`, `docs/pha-ios-proactive-change-log.md` register; `prd-pha-ios-proactive-agent-v1.md` adds FR “chat interpretation same-source as fact card”.
- `rules/harness_profile_registry.generated.json` `--write` regenerate and commit.

---

## 6. Goldens (H9–H13 · from §1.1 on-device transcript)

Fixed fixture: `wearable_daily` two rows = §1.2; user fact-card prefs = default 5 (sleep_time_asleep, hrv_sdnn_ms, resting_heart_rate_bpm, steps, active_energy).

| ID | Turn input | Expected (all flags on) |
|---|---|---|
| H9 | 「请分析今天的HRV，静息心率和睡眠数据是否适合高强度的力量训练？」 | goal=`daily_readiness`; profile=`wearable_daily_review`; T0 contains HRV/sleep/RHR (RHR anchor 09-08 and labeled); reply zh; no English section headings; audit passed; report no tier0 truncation |
| H10 | 「今天的睡眠数据没有吗？请核实」 | skip-LLM allowed; output 5 lines: sleep 8.22h, deep 0.47h, REM 2.45h, core 5.3h, awake 0.78h (all anchor 2026-09-09); no 90d mean |
| H11 | 「核心睡眠是多少？深睡是多少？睡眠清醒是多少？」 | D on: three point-day values; D off: three 90d means (**not** total-duration mean) |
| H12 | 「请列出今天的睡眠相关的数据」 | same as H10 + if `sleep_in_bed` explicitly asked and empty → one line “库内没有 2026-09-09 的在床记录” |
| H13 | 「今天静息心率多少？」 | 「库内没有 2026-09-09 的静息心率记录，不会用其他日期或其他指标的数字代替。」 |

**English mirror cases (H9E–H13E · 1:1 with zh; must be green together)**

| ID | Input | Expected (only language may differ from zh mirror) |
|---|---|---|
| H9E | "Based on today's HRV, resting heart rate and sleep, is high-intensity strength training appropriate?" | goal=`daily_readiness`; profile=`wearable_daily_review`; T0 row set == H9; reply en; **does not** trigger `locale_fallback_applied`; audit passed |
| H10E | "Is there really no sleep data for today? Please verify." | 5 lines == H10 (same values/anchors), labels use `label_en` |
| H11E | "How much core sleep, deep sleep and awake time?" | D on: three point-day values (inherit 09-09); D off: three 90d means |
| H12E | "List today's sleep-related data" | == H12 en version; missing line uses en template |
| H13E | "What was my resting heart rate today?" | "No verified resting HR in your records for 2026-09-09. Not filled from another date or metric." |

Judgment: selfcheck for each pair (Hn, HnE) asserts `goalClass`, `arbiterReason`, `profile`, `wearableMetricResolution.requestedMetricIds`, manifest `(metric_id, value, anchor)` set, `audit.passed`, `skip_llm` **fully equal**; only `response_locale` and text differ. Any pair unequal = red.

Negative cases (prevent overfit):

- 「近 90 天睡眠怎么样」→ still `wearable_only` span mean (5 mean rows after cluster expand).
- 「我的血脂适合训练吗」→ `anti_tokens` hit → not `daily_readiness`.
- 「HRV 32 正常吗」→ `metric_specific`, original path.

---

## 7. Observability and telemetry

- `harness_report.goalClass` adds enum `daily_readiness`; `arbiterReason` adds `goal_readiness_daily`.
- `wearableMetricResolution` (§B).
- `episodic.focusGrain` (§D).
- Structured log events (English keys): `wearable_cluster_expanded`, `focus_missing_for_grain`, `readiness_profile_selected`, `grain_anchor_inherited`.

---

## 8. Risks and mitigations

| Risk | Level | Mitigation |
|---|---|---|
| `summaries` keys from catalog key to registry id has large blast radius | High | B.1 provides `catalog_key_of` bidirectional map; grep all consumers; `pha_stage3c_wearable_selfcheck.py` + `pha_wearable_p15_selfcheck.py` as regression net; flag dual-path until B.5 |
| Audit-label drift mismatches old cache/goldens | High | Freeze test character-for-character; `wrist_temp`, `activity_kcal` specials declared via Registry fields not code |
| Cluster expand makes skip-LLM output longer | Medium | `expand_on_cluster_query` off per row; `sleep_in_bed` default not expand |
| `daily_readiness` vs `holistic_assessment` race | Medium | catalog explicit `precedence_over` + `anti_tokens` + lab marker exclude; negative cases into selfcheck |
| New profile T0 over budget | Medium | isomorphic with fact_card_interpret; acceptance requires 14 rows no truncate; over only cuts Tier1 |
| Signed asset schema broken by the generator | Medium | generator only changes allowlisted fields; `pha_catalog_registry_selfcheck.py` gate |
| Grain anchor wrongly inherits “yesterday” onto an unrelated new topic | Medium | inherit only on weak questions / pure-metric questions; TTL; explicit time words override; report visible |

---

## 9. Industry-pattern contrast (Constitution §1 · Wave patch-level brief table)

| This design | Industry analog | Tradeoff |
|---|---|---|
| Registry single source → generate lexicons/columns/labels | Typed tool/schema registry defined once, generated many places (OpenAI function schema, Vercel AI SDK tool defs) | Generate rather than runtime reflect; keep deterministic and diffable |
| Per-item fail-closed missing lines | Grounded generation explicit-null / abstain | Done at Harness layer, not by prompt |
| GoalClassifier adds a goal class + Arbiter policy table | Intent → policy table routing (Rasa policies / Dialogflow intents) | Keep declarative JSON; no LLM routing |
| Session grain anchor | Dialogue slot carry-over | Inherit only the time slot, with TTL and explicit override |
| Chat reuses card T0 assembly | Same evidence builder for multiple surfaces (BFF pattern) | Reuse the pipe, do not copy the prompt |

---

## 10. zh/en consistency review (2026-09-09 re-review · already merged into each Wave)

Review principle: **same ledger + same question (only language differs) → same profile, same T0 set, same audit conclusion, same skip/LLM decision; only text language may differ.** Language differences may only appear at the “render layer” (label / template / chip copy), never at the “decision layer” (route / fetch / grain / audit).

### 10.1 Bilingual guarantees of the design itself

| Decision-layer component | Language source | Conclusion |
|---|---|---|
| Metric identify `infer_wearable_metric_ids` | Registry `intent_hints` (all 17 rows have zh+en; selfcheck mandatory) | Neutral |
| Cluster expand / primary / focus judge | Registry `catalog.*` structure fields, no text | Neutral |
| Time grain `resolve_wearable_time_grain` | 今天/今日/today/tonight, 昨天/昨晚/yesterday/last night, 近N天/last N days, 近一周/past week (already bilingual) | Neutral |
| `daily_readiness` goal | catalog tokens bilingual + `anti_tokens` bilingual + `message_has_lab_marker` (reads catalog `lab_markers`, bilingual) | Neutral |
| Arbiter policy table | Only looks at goal_class / existence_probe | Neutral |
| Session grain anchor (Wave D) | Only registry ids + no time words | Neutral (see F3 correction) |
| Numerics audit | manifest `(metric, value, anchor)`; metric is a zh audit token but decoupled from display language | Neutral |
| TASK / Soul | `_FACT_CARD_INTERPRET_TASK`, `PHA_FACT_CARD_SOUL_MINIMAL` both English single version; only T1 example switches with locale; output language decided by `RESPONSE LANGUAGE` instruction | Neutral |

### 10.2 Re-review findings already corrected (F1–F8)

| # | Finding | Impact | Correction landing |
|---|---|---|---|
| F1 | `compose_fact_card` unconditionally uses `load_fact_card_locale(user_id)` (iOS card prefs), ignores this turn’s `response_locale` | en chat user gets zh label/window copy in `FACT_CARD_CONTEXT` → model CJK leak → `apply_english_locale_leak_guard` replaces the whole interpretation with a fallback summary → **en interpretation quality systematically below zh** | §C.4: `load_fact_card` / `compose_fact_card` add `locale` pass-through |
| F2 | `USER_ASSESSMENT_PROMPT` slot head zh literal | en system prompt mixed with CJK | §C.5: `card_copy(locale, "assessment_prompt_head")` |
| F3 | Wave D first draft cited catalog `weak_followup` (actually thanks-closing words) and `anaphora` (zh-only) | en follow-up cannot inherit grain | §D: change to pure registry ids + no time words |
| F4 | `_PROFILE_FOLLOWUPS`, `继续聊{tok}`, `看看{mk}` zh-only | en user sees Chinese chips | §E.2: catalog `label_zh/label_en` + `card_copy` |
| F5 | `build_fact_card_event.label` is a zh audit token | en user SSE number card shows Chinese | §E.1: add `label_display` |
| F6 | `goal_markers.holistic_assessment` zh-only (3F leftover) | `daily_readiness.precedence_over` has no counterpart on en side; zh/en route results may differ | §C.1: same PR fill en tokens |
| F7 | `_COMPARE_ALL_METRICS_RE` zh-only; `_STAGE_HINT_RE` has no `sleep stages` | en “compare all metrics” takes a narrow focus; “sleep stages” does not expand stages | §B.2: move to catalog / fill en hints |
| F8 | `_METRIC_LABEL_EN_FALLBACK` Python hardcoded fallback; some Registry rows missing `ui.label_en` | en label source split | §4.1: `label_en` mandatory non-empty; delete fallback table |

### 10.3 Known remaining inequality not on this track (register backlog)

- `apply_english_locale_leak_guard` is en-side only (CJK leak >12% replaces the whole segment); zh side has no symmetric guard (English headings mixed into zh replies not blocked). This design mitigates via the new profile’s soul forbidding three-step English headings + `pha_response_language_selfcheck.py` asserts; a symmetric zh guard is a separate P2.
- `leftover_s_level_numeric_tokens` recognizes zh units (毫克/微克) weaker than en (mg/mcg) — found at P14 acceptance; a Numerics audit unit-table issue; separate P1 (audit may only tighten not relax, so must add zh units rather than relax en).
- `_LAB_MARKERS_RE` (`intent_gates.py`, contains 肝功能/肾功能/血糖/hba1c) vs catalog `lab_markers` (contains cholesterol/lipids/blood test) two sources, different coverage; this design uses only the catalog version; merge is a separate P2.

### 10.4 Acceptance contract

- §6 zh/en mirror pairs equal (decision-layer field sets item-by-item `==`).
- `pha_response_language_selfcheck.py` adds: new profile under en `locale_fallback_applied == False`; under zh no `Trend review|Related markers|Recommendations`.
- In-process acceptance: H9 and H9E each ≥3 real-model runs, audit all pass, and both sides `wearableMetricResolution` identical.

---

## 11. Delivery checklist (one PR per Wave)

- [ ] First PR comment contains §0 four ACK lines and P0/P1/P2 declaration (no PR opened yet; wait for maintainer commit)
- [x] Registry / Catalog JSON changes + generate script `--check` zero drift
- [x] No new Python literal lexicon/label tables (reviewer spot-check `rg "\"今日|均值|深睡|REM\"" pha/`; hits only allowed in test freeze snapshots)
- [x] `python scripts/pha_harness_profile_registry_generate.py --write` (Wave C)
- [x] Selfcheck list green: `pha_wearable_registry_selfcheck` · `pha_numerics_manifest_selfcheck` · `pha_wearable_metric_probe_selfcheck` · `pha_grounded_composer_selfcheck` · `pha_goal_arbiter_selfcheck` · `pha_harness_profile_registry_selfcheck` · `pha_chat_turn_routing_selfcheck` · `pha_health_episodic_selfcheck` · `pha_response_language_selfcheck` · `pha_fact_card_selfcheck` · `pha_e2e_wearable_focus_battery` (includes `pha_chat_fact_card_parity_selfcheck`)
- [x] `docs/harness-change-log.md` + `docs/pha-ios-proactive-change-log.md` already wrote rollback paths and on-device transcript (not committed with a PR)
- [x] `./scripts/pha_restart_accept.sh` on-device acceptance: H10–H13/H10E/H13E skip-LLM; H9-zh chat+interpret; H9E audit passed. Transcript in proactive change-log 16:51
