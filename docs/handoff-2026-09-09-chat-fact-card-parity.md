# Handoff · 2026-09-09 · 对话框与主动事实卡「解读一致性」(Chat ↔ Fact Card Parity)

> 状态：**已编码 · 离线 selfcheck 绿 · 真机 8788 验收过**（Wave A–F；H10–H13/H10E/H13E skip-LLM；H9-zh 对话+interpret；H9E 审计过。转录：proactive change-log 16:51）
> 变更等级：Harness **P1**（含一个 P0 配置真源收敛）
> 上位法：[`pha-pm-constitution.md`](pha-pm-constitution.md) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) · [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) · [`wearable-metric-registry-v1.md`](wearable-metric-registry-v1.md)
> 前序：[`handoff-2026-09-09-proactive-memory-sharing.md`](handoff-2026-09-09-proactive-memory-sharing.md)（P13/P14 已 DONE）

---

## 0. 开工口令与必读（coding agent 首条回复必须输出）

```text
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read
```

必读顺序：`.cursor/rules/pha-mandatory-reads.mdc` 全局 1–8 → `wearable-metric-registry-v1.md` → `harness-tier0-fuse-v2.2.6.1.md` → 本文。

硬红线（本轨道全程有效）：

- TurnEvidencePlan 先于 LLM；Profile 只在 Harness Arbiter 之后锁定。
- 任何用户可见数字必须 ⊆ Numerics Manifest；LLM 不写数字。
- **不得**新增 Python 内的 phrase / metric / label 硬编码表；一切词表、簇、标签进 JSON 真源（Registry / Intent Catalog）。
- 不得为让 H9–H13 黄金用例变绿加特例分支；用 catalog + Arbiter + 会话锚点。
- fail-closed：查不到就说查不到，**禁止**沉默改换时间粒度或指标。
- 每个 Wave 独立 feature flag、可回滚；同 PR 更新 change-log 与 selfcheck。

---

## 1. Telemetry 证据（宪法 §2 · 因痛起案）

### 1.1 真机对照（同一模型 `qwen3:14b`、同一 prompt、同一账本）

| 项 | iOS 主动卡（`fact_card_interpret`） | Mac 网页对话（`wearable_only`） |
|---|---|---|
| 进入 T0 的指标 | 用户勾选 9 项 + 各自 90d 基线/百分位 | `今日HRV 32.83ms`、`今日睡眠 8.22h` 两条 |
| 睡眠分项 | 深睡 / REM / 核心 / 清醒 全部可见 | 不可见；追问三次仍只回总时长 |
| 静息心率 | 有（Registry `temporal.daily_lagged`，取 09-08 值并标注日期） | 无（对话侧点日严格同日，09-09 RHR 为空） |
| 「今天的睡眠数据没有吗？请核实」 | — | 确定性模板：`今日睡眠：8.22h`（未进 LLM） |
| 「核心睡眠是多少？深睡是多少？睡眠清醒是多少？」 | — | 沉默改为 90d：`睡眠均值 7.34h`，且三项分项一个都没答 |
| 输出结构 | 中文，状态评估 → 关联 → 训练建议 | 英文标题 `Trend review / Related markers / Recommendations` |

### 1.2 账本核对（`data/pha_storage.db` · `wearable_daily` · 只读）

```text
2026-09-09  sleep_hours=8.2167  sleep_deep_hours=0.4667  sleep_rem_hours=2.45
            sleep_core_hours=5.3  awake_duration_hours=0.7833  hrv_sdnn_ms=32.83
            resting_heart_rate_bpm=NULL  steps=67
2026-09-08  resting_heart_rate_bpm=62.0  sleep_hours=6.2  sleep_deep_hours=0.9 ...
```

结论：**数据共享无问题**（两端读同一 SQLite）。差异全部产生在对话侧的「指标解析 → 取数 → 路由 → 模板」链路。

### 1.3 根因定位（代码级）

| # | 根因 | 位置 |
|---|---|---|
| R1 | 对话侧指标词表 `wearable_bundle.schema.json` 只有 9 个 catalog key（`sleep` 仅总时长），与 Registry 17 行（含 `sleep_deep/rem/core/awake/in_bed`）**双目录漂移** | `storage/schemas/wearable_bundle.schema.json` vs `storage/registry/wearable_metric_registry.json` |
| R2 | `get_health_data` 只认 catalog key，`_metric_value` 是 if 链，Registry `l1.field` 未被对话侧取数使用 | `pha/health_data.py:80-110, 269-293` |
| R3 | catalog key ↔ registry id ↔ 中英文标签 三元映射在 **7 处** Python 各写一份 | `numerics_manifest._wearable_entries.label_map` / `_focus_to_cat`；`grounded_answer_composer._WAREHOUSE_FOCUS_LABELS_BY_CAT` / `_REGISTRY_TO_WAREHOUSE_LABELS` / `_WAREHOUSE_FOCUS_LABEL_EN` / `_missing_grain_summary.metric_zh`；`wearable_metric_probe._CATALOG_TO_REGISTRY`；`wearable_compare_table_v1._CATALOG_PRIMARY_METRIC` / `_SLEEP_FOCUS_METRIC_IDS` |
| R4 | Registry `intent_hints` 已含「深睡/核心睡眠/睡眠清醒」，但只喂给 `infer_single_metric_focus_ids`（上限 2 个 id），三项同问 → 退回 catalog `sleep` 单键 → skip-LLM 只出总时长 | `wearable_compare_table_v1.infer_single_metric_focus_ids` · `grounded_answer_composer.try_warehouse_metric_focus_skip` |
| R5 | 无日期词的追问 `grain.source == default` → 90d 均值；会话锚点没有「时间粒度」维度 | `wearable_time_grain.resolve_wearable_time_grain` · `session_turn_focus`（只有 profile/metric/goal/domains） |
| R6 | 「适合训练吗」类问题命中 `_EXERCISE_ADVICE_ONLY_RE` → `_deterministic_exercise_advisory` 固定文案（不看数据）；或落 `wearable_only` 三段式医学 soul | `wearable_compare_table_v1:1010, 1482` · `chat_turn_slots.py:60-70` soul 选择 |
| R7 | `fact_card_interpret` 的 TASK/soul/T0 组装只对 `profile == "fact_card_interpret"` 字符串生效，对话无法复用 | `chat_turn_slots.py:66, 295, 300, 342, 418` |

---

## 2. 设计自审：原建议 vs 共识（已修正项）

| 原建议 | 风险 | 修正后的做法 |
|---|---|---|
| 「补中文触发词：深睡、REM…」 | 若写进 Python = phrase 硬编码 | 词已在 Registry `intent_hints`；**不加词，修管道**（Wave B） |
| 「睡眠簇展开」 | 若用 `_SLEEP_FOCUS_METRIC_IDS` 之类 frozenset = 硬编码 | Registry 新增 `catalog.cluster` 字段，簇成员由 JSON 声明（Wave A） |
| 「新增训练准备度意图 + 触发词」 | 若加 regex = 违反「禁止逐句 if-else 扩规则」 | 3F `goal_markers.daily_readiness` 进 `health_intent_catalog.json`；Arbiter 加一行策略；`_EXERCISE_ADVICE_ONLY_RE` 退役为 fallback（Wave C） |
| 「schema 由 registry 派生」 | `wearable_bundle.schema.json` 是 signed evidence asset，有 `contract` | 生成脚本只重写 `catalog.trigger_keywords / core_hint_keywords / metrics.*`，保留 `contract` 并 bump `schema_version`；selfcheck 断言零漂移（Wave A） |
| 「标签统一」 | `今日睡眠`/`睡眠均值` 是审计 token，改字会让黄金用例与旧缓存失配 | Registry 新增 `catalog.label_zh/label_en`；**冻结测试**：派生标签 == 现有 9 键硬编码标签，逐字相等（Wave B） |
| 「网页加一键重新解读」 | `_PROFILE_FOLLOWUPS` 本身是 Python 硬编码，不应再扩 | follow_ups 进 catalog `follow_ups` 段，payload 走既有 chip 协议（Wave E） |
| 「给 `wearable_only` 开 `USER_BACKGROUND_BRIEF`」 | 与 `USER_CONTEXT_BRIEF` 重叠、扩大 P14 范围 | 只给新 profile 开（与卡片同构）；`wearable_only` 不动 |
| 「对话侧改用 Registry `temporal` 取昨日 RHR」 | 会让「今日静息心率」标签指向昨日数值，违反 T0 定账语义 | 新 profile 直接继承卡片（卡片已按 anchor 标日）；`wearable_only` 保持严格同日 + fail-closed 提示（Wave B/E） |

自审结论：修正后无 Python 硬编码新增、无消费者侧特例分支、不削弱 TurnEvidencePlan / Numerics 审计 / Harness Veto、LLM 不写数字、每 Wave 有 flag 与回滚。

---

## 3. 目标与非目标

**目标**

1. 对话侧与事实卡使用**同一指标真源**（Registry），词表 / 簇 / 标签 / 列名不再各写一份。
2. 「今天睡眠数据」类问题返回**整簇**且逐项 fail-closed。
3. 「今天状态 / 能否训练」类问题在对话框得到与主动卡**同质**的解读（同 T0 组装、同 TASK、同 soul、同背景摘要、同审计）。
4. 无日期词的弱追问可继承上一轮的点日粒度（会话锚点新增维度）。
5. 用户能看到「本轮进入解读的指标 / 当日可用但未选的指标」。

**非目标**

- 不改 iOS 卡片 UI、不改 ingest、不改 `fact_card_interpret` 的缓存键与审计策略。
- 不触碰 `wearable_screenshot_review` / 附件车道。
- 不让 LLM 参与指标选择或 SQL。
- 不做「身体年龄」等新合成指标。

---

## 4. 架构：Registry 单一真源 → 全部派生

```text
storage/registry/wearable_metric_registry.json   (唯一真源；新增 catalog.* 字段)
   │
   ├─(生成)→ storage/schemas/wearable_bundle.schema.json  catalog.trigger_keywords / core_hint_keywords / metrics.canonical|core
   ├─(运行时读)→ pha/health_data.py       metric key 解析、列名、单位、hrv fallback
   ├─(运行时读)→ pha/numerics_manifest.py  点日/区间标签（今日X / X均值）
   ├─(运行时读)→ pha/grounded_answer_composer.py  焦点标签、EN 标签、缺失文案
   ├─(运行时读)→ pha/wearable_metric_probe.py / wearable_compare_table_v1.py  catalog→registry、簇、簇主指标
   └─(运行时读)→ pha/fact_card*.py         （已是 Registry 消费者，不变）

rules/health_intent_catalog.json                  goal_markers.daily_readiness · follow_ups
rules/harness_profile_registry.generated.json     新 profile wearable_daily_review（--write 重生）
```

### 4.1 Registry 新增字段（每个 `metrics[]` 行）

```json
"catalog": {
  "key": "sleep",                 // 对话侧 catalog key（与 wearable_bundle 同名空间）；同簇多行可共用 key
  "cluster": "sleep",             // 簇 id；无簇则省略
  "cluster_primary": true,        // 簇主指标（每簇恰好一行 true）
  "expand_on_cluster_query": true,// 命中 key/簇任一成员时是否整簇取数
  "label_zh": "睡眠",             // 审计标签词干：点日 = "{今日|当日}"+label；区间 = label+"均值"
  "label_en": "sleep",            // EN 词干：点日 "Today's {label_en}" / "{label_en} that day"；区间 "Mean {label_en}"
  "mean_suffix_zh": "均值"        // 可选；默认"均值"，activity_kcal 现为"日均"，须显式声明以保证冻结相等
}
```

约束（进 `pha_wearable_registry_selfcheck.py`）：

- `catalog.key` 集合 ⊇ 现有 bundle `metrics.canonical` 9 键；`cluster_primary` 每簇唯一；`label_zh` 在同 key 内唯一或与 key 主行一致。
- **双语强制**：凡有 `catalog.key` 的行，`catalog.label_zh` 与 `catalog.label_en` 必须同时非空；`intent_hints` 必须同时含 ≥1 个 CJK token 与 ≥1 个 Latin token（selfcheck 断言）。顺带补齐 `ui.label_en`，让 `wearable_metric_registry._METRIC_LABEL_EN_FALLBACK` 可删（见 §10）。
- 派生 `wearable_bundle.schema.json` 与仓库内文件逐字节相等（除 `schema_version`/`contract.revision`）。
- 派生标签冻结：对 9 个旧键，`{点日,区间}×{zh,en}` 标签必须等于 Wave B 之前的硬编码值（测试内嵌旧表快照，**仅测试文件可含该快照**）。

首批填值（与现网标签逐字对齐）：

| metric_id | key | cluster | primary | label_zh | label_en | 备注 |
|---|---|---|---|---|---|---|
| sleep_time_asleep | sleep | sleep | ✅ | 睡眠 | sleep | |
| sleep_deep | sleep | sleep | | 深睡 | deep sleep | |
| sleep_rem | sleep | sleep | | REM | REM | |
| sleep_core | sleep | sleep | | 核心睡眠 | core sleep | |
| sleep_awake | sleep | sleep | | 睡眠清醒 | awake in sleep | |
| sleep_in_bed | sleep | sleep | | 在床 | in bed | `expand_on_cluster_query:false`（默认不展开，避免噪声） |
| hrv_sdnn_ms | hrv | cardiac | ✅ | HRV | HRV | |
| hrv_rmssd_ms | hrv | cardiac | | — | — | `catalog.hidden:true`，仅作 `display_fallback` 来源 |
| resting_heart_rate_bpm | rhr | cardiac | | 静息心率 | resting HR | |
| steps | steps | activity | ✅ | 步数 | steps | |
| active_energy | activity_kcal | activity | | 活动消耗 | active kcal | `mean_suffix_zh:"日均"` |
| spo2_percent | spo2 | — | | 血氧 | SpO2 | |
| respiratory_rate | respiratory_rate | — | | 呼吸率 | respiratory rate | |
| vo2max | vo2max | — | | VO2max | VO2max | |
| wrist_temp | wrist_temp | — | | 手腕体温 | wrist temp | 现网点日标签为「手腕体温」，非 `ui.label_zh` 的「睡眠腕温」，故 `catalog.label_zh` 单列 |
| workout_* | — | — | | | | 无 catalog key（不进 get_health_data） |

---

## 5. 分 Wave 设计

### Wave A（P0 · 配置真源收敛 · 无行为变化）

**改动**

1. `wearable_metric_registry.json`：按 §4.1 增补 `catalog.*`；bump `version`。
2. `pha/wearable_metric_registry.py` 新增只读访问器（英文名，纯函数、有 lru_cache）：
   - `catalog_key_for(metric_id) -> str|None`
   - `metric_ids_for_catalog_key(key) -> tuple[str,...]`（registry 文件顺序）
   - `cluster_members(cluster_id, *, expand_only=True) -> tuple[str,...]`
   - `cluster_primary_metric_id(cluster_id) -> str|None`
   - `cluster_of(metric_id) -> str|None`
   - `catalog_labels(metric_id) -> CatalogLabels(point_zh, span_zh, point_en, span_en, that_day_zh, that_day_en)`
   - `catalog_keys_canonical() -> tuple[str,...]` / `catalog_keys_core()`（core = `fact_card.enabled_default` 且有 key 的主行，去重）
   - `bundle_trigger_keywords() -> list[dict]`（由 `intent_hints` × `catalog.key` 生成，字段同现 schema：`token/metric_id/zh`）
3. 新脚本 `scripts/pha_wearable_bundle_schema_generate.py [--write]`：读 Registry，重写 bundle schema 的 `catalog.trigger_keywords`、`catalog.core_hint_keywords`、`metrics.canonical`、`metrics.core`；其余字段原样保留；`--check` 模式返回非 0 表示漂移。
4. `scripts/pha_wearable_registry_selfcheck.py` 增加 §4.1 三条约束 + `--check` 调用。
5. `scripts/run_selfchecks.sh` / `selfcheck_manifest.json` 登记。

**验收**：`pha_wearable_registry_selfcheck.py` 绿；`pha_wearable_bundle_schema_generate.py --check` 零漂移；`pha_catalog_registry_selfcheck.py`、`pha_dch_selfcheck.py` 仍绿（signed asset 未被破坏）。

**回滚**：Registry 新字段是加法，删字段即回滚；无运行时消费者。

---

### Wave B（P0 · 对话侧取数与标签改为 Registry 驱动 · 簇展开 · 逐项 fail-closed）

Flag：`PHA_WEARABLE_REGISTRY_CATALOG`（默认 `1`，置 `0` 走旧硬编码路径直至 B.2 删除）。

**B.1 `pha/health_data.py`**

- `METRIC_ALIASES` / `CORE_WEARABLE_METRICS` / `EXTENSION_WEARABLE_METRICS`：保留常量名（外部引用多），但值改为 Registry 派生：`ALLOWED_METRICS = catalog_keys ∪ registry metric_ids（l1.kind == wearable_daily）`。
- `_partition_requested_metrics`：先查 `METRIC_ALIASES`，再查 Registry `metric_id`，再查 `catalog.key`。
- `_metric_value(row, metric)`：
  - 若 `metric` 是 registry id → `getattr(row, l1.field)`；若为 None 且行有 `fact_card.display_fallback_metric_id` → 取 fallback 列（覆盖现有 hrv SDNN→RMSSD 特判）。
  - 若 `metric` 是 catalog key → 取该 key 的 `cluster_primary` 行（或唯一行）按上一条求值。
  - 删除 if 链。
- `_metric_unit(metric)`：Registry `fact_card.unit`（无则 `snapshot.unit`）。
- `get_health_data(..., metrics)` 返回的 `summaries` 键：**保持 catalog key** 作为向后兼容主键；新增 registry id 键时以 `registry:` 前缀区分？—— **否决**：改为 `summaries` 键统一使用 **registry metric_id**，并在 `HealthDataResult` 增 `catalog_key_of: dict[str,str]`；所有消费者（manifest、summary block、analytics）经访问器映射。coding agent 需 grep `.summaries` 全部消费者并逐一切换；`pha_stage3c_wearable_selfcheck.py`、`pha_wearable_p15_selfcheck.py` 是回归网。

**B.2 簇展开（`pha/intent_gates.py` + `pha/catalog_dch.py`）**

- `infer_wearable_metrics(msg)` 返回值语义不变（catalog keys），但新增 `infer_wearable_metric_ids(msg) -> list[str]`（registry ids）：
  1. `_hint_match_metric_ids(msg)`（Registry `intent_hints`，已存在，迁入 `wearable_metric_registry.py` 公开为 `hint_match_metric_ids`）。
  2. 对每个命中的 catalog key / 簇成员：若簇 `expand_on_cluster_query` 且 flag `PHA_WEARABLE_CLUSTER_EXPAND=1`（默认 1）→ 加入 `cluster_members(cluster)`。
  3. 若为空且 `default_if_wearable_query` → `catalog_keys_core()` 对应主行。
- `_STAGE_HINT_RE`、`_WORKOUT_HINT_RE`（`wearable_metric_probe.py`）退役：`睡眠分期/分期` **与英文 `sleep stage`/`sleep stages`** 一起加入 `sleep_deep`/`sleep_rem` 的 `intent_hints`（JSON），workout 词已在 `intent_hints`（中英俱有）。
- `_COMPARE_ALL_METRICS_RE`（zh-only：所有指标|各项指标|整体…）迁入 catalog `broad_compare.tokens` 并补英文（`all metrics`, `every metric`, `overall`, `compare all`）；Python 只读 catalog。
- `_CATALOG_TO_REGISTRY`、`_CATALOG_PRIMARY_METRIC`、`_SLEEP_FOCUS_METRIC_IDS`、`_WORKOUT_FOCUS_METRIC_IDS`、`_SINGLE_METRIC_FOCUS_MAX` → 由 `cluster_*` 访问器替代；`_is_allowed_focus_pair` 改为「同簇即允许」，上限改为「≤ 该簇成员数」。

**B.3 点日取数：`get_health_data` 用 registry ids**

- `numerics_manifest._wearable_entries`：`metrics = infer_wearable_metric_ids(msg)`；`label_map` 删除，改 `catalog_labels(mid)`；`_focus_to_cat` 删除。
- `harness_plan.build_wearable_90d_summary_block`：同上；默认 `["hrv","activity_kcal"]` 改为 `catalog_keys_core()` 主行中 `metrics.core` 顺序前两位（由 Registry 派生，非字面量）。

**B.4 焦点 skip-LLM 路径逐项 fail-closed（`grounded_answer_composer.py`）**

- `_WAREHOUSE_FOCUS_LABELS_BY_CAT` / `_REGISTRY_TO_WAREHOUSE_LABELS` / `_WAREHOUSE_FOCUS_LABEL_EN` / `_missing_grain_summary.metric_zh|en` 删除，改 `catalog_labels`。
- `is_warehouse_metric_focus_turn`：条件改为 `requested_ids = infer_wearable_metric_ids(msg)`，且 `requested_ids` 全部属于**同一簇**（或单指标）→ True。三项睡眠分项同问 → True（同簇）。
- `_filter_manifest_to_metric_focus(manifest, msg)` 改签名为 `(manifest, requested_ids)`：按 `catalog_labels(mid).point_zh|span_zh` 过滤。
- `build_manifest_metric_focus_summary` 新增参数 `missing_ids: list[str]`；对 `requested_ids − manifest 命中 ids`，每项追加一行：
  - zh：`库内没有 {anchor} 的{label_zh}记录，不会用其他日期或其他指标的数字代替。`
  - en：`No verified {label_en} in your records for {anchor}. Not filled from another date or metric.`
  - 若 `manifest` 为空且 `missing_ids` 非空 → 只输出缺失行（不再返回空串让 LLM 兜底）。
- `try_warehouse_metric_focus_skip`：不再以 `len(infer_wearable_metrics)==1` 判定；以 §B.4 第二条判定；构造 `requested_ids` 一次并贯穿。

**B.5 冻结与删除**

- 冻结测试（`pha_numerics_manifest_selfcheck.py`）：9 旧键 × 4 标签逐字等于旧值。
- B.1–B.4 完成且 flag=1 下全部 selfcheck 绿后，同 PR 删除旧硬编码表与 flag `0` 分支（保留 flag 读取一个版本以便紧急回滚 = 读取 `0` 时抛 `RuntimeError("legacy path removed; rollback by git")` 并在 change-log 写明回滚 commit）。

**Harness report 新字段**（`harness_report_v11`）：

```json
"wearableMetricResolution": {
  "requestedCatalogKeys": ["sleep"],
  "requestedMetricIds": ["sleep_time_asleep","sleep_deep","sleep_rem","sleep_core","sleep_awake"],
  "clusterExpanded": ["sleep"],
  "grain": {"start":"2026-09-09","end":"2026-09-09","source":"explicit_today"},
  "missingForGrain": ["sleep_in_bed"]
}
```

**验收**：黄金 H10 / H12 / H13（§8）；`pha_grounded_composer_selfcheck.py`、`pha_wearable_metric_probe_selfcheck.py`、`pha_numerics_manifest_selfcheck.py`、`pha_stage3c_wearable_selfcheck.py`、`pha_e2e_wearable_focus_battery.py` 绿；`pha_fact_card_selfcheck.py` 不受影响仍绿。

**回滚**：`PHA_WEARABLE_REGISTRY_CATALOG=0`（B.5 前）；B.5 后 git revert 单 PR。

---

### Wave C（P1 · `daily_readiness` 目标 + 新 profile `wearable_daily_review` 复用事实卡管线）

Flag：`PHA_DAILY_READINESS_PROFILE`（默认 `0`，验收后翻 `1`）。

**C.1 Intent Catalog（`rules/health_intent_catalog.json`）**

```json
"goal_markers": {
  "holistic_assessment": {
    "tokens": ["综合", "整体", "评估", "各项指标", "全面", "大健康", "身体年龄",
               "overall", "comprehensive", "assessment", "all my metrics", "how am i doing", "body age"],
    "notes": "同 PR 补齐英文 token（3F 原表 zh-only，见 §10）"
  },
  "daily_readiness": {
    "tokens": ["训练", "力量训练", "高强度", "运动强度", "运动类型", "恢复", "准备度", "身体状态", "今天状态",
               "适合运动", "能不能练", "可以锻炼", "strength training", "readiness", "recovery",
               "train today", "workout today", "can i train", "high intensity"],
    "anti_tokens": ["化验", "血脂", "LDL", "lipid"],
    "domain": "wearable",
    "precedence_over": ["holistic_assessment"],
    "notes": "当日训练/恢复准备度评估；数值来源 = 事实卡 T0；不引入新指标"
  }
}
```

- `pha/goal_classifier.classify_goal`：在 `holistic_assessment` 判定**之前**检查 `daily_readiness`（若 `precedence_over` 声明且 `anti_tokens` 未命中且 `message_has_lab_marker` 为 False）。`GoalClassification("daily_readiness", 1.0, "catalog")`。
- 显式 metric token 仍优先？—— **否**：H9 同时含显式 metric（HRV/静息心率/睡眠）与 readiness 词。规则改为：显式 metric + readiness 词 → `daily_readiness`（metric 作为 `focus_metric_ids` 附带，供 C.3 turn-local 指标并集）；显式 metric 无 readiness 词 → `metric_specific`（原行为）。此优先级写进 catalog `goal_markers.daily_readiness.wins_over_explicit_metric: true`，不写死在 Python。

**C.2 Harness Arbiter（`pha/harness_arbiter.py`）新增策略行**

| goal_class | existence_probe | 行为 | authoritative_profile | arbiter_reason |
|---|---|---|---|---|
| `daily_readiness` | wearable ✓ | 升舱 | `wearable_daily_review` | `goal_readiness_daily` |
| `daily_readiness` | wearable ✗ | clarify `data_gap` | `clarify` | `goal_clarify_data_gap` |
| episodic `focus_goal=daily_readiness` + 弱问句 | wearable ✓ | 续 goal | `wearable_daily_review` | `episodic_goal_continue` |

flag 关闭时 `daily_readiness` 视作 `metric_specific`（完全旧行为）。

**C.3 新 profile `wearable_daily_review`（`pha/harness_plan.py`）**

```text
profile            = "wearable_daily_review"
slots_tier0        = ["TASK", "USER_ASSESSMENT_PROMPT", "FACT_CARD_CONTEXT", "NUMERICS_MANIFEST"]
slots_tier1        = ["USER_BACKGROUND_BRIEF"]
forbidden          = 同 fact_card_interpret（_FACT_CARD_INTERPRET_FORBIDDEN）
tools_allowed      = []
task_text          = fact_card_interpret_task_text(locale)   # 复用 5 条规则；第 5 条已含 USER_BACKGROUND_BRIEF
legacy_question_type = WEARABLE
memory_write_policy  = "chat"        # 与 fact_card_interpret（none）不同：对话自述要进记忆（P13 规则）
```

- `USER_ASSESSMENT_PROMPT` = **本轮用户消息原文**（对话问题即评估大纲；与卡片语义一致）。
- `FACT_CARD_CONTEXT` / `NUMERICS_MANIFEST`：复用 `load_fact_card` + `build_fact_card_numerics_manifest`。
- `resolve_profile_override` 与 registry `--write` 登记新 profile；`profile_slot_invariants` 补：含 `FACT_CARD_CONTEXT` 的 profile 必含 `NUMERICS_MANIFEST` 与 `USER_ASSESSMENT_PROMPT`。

**C.4 事实卡 turn-local 指标集**

- `pha/fact_card.load_fact_card(user_id, *, reference=None, enabled_metric_ids=None, locale=None)` 增加透传到 `compose_fact_card(enabled_metric_ids=..., locale=...)`；`compose_fact_card` 新增 `locale` 参数，**为空时**才回退 `load_fact_card_locale(user_id)`（现状是无条件读 iOS 卡片偏好，见 §10-F1）。对话侧必须传本轮 `response_locale`，否则英文用户会在 `FACT_CARD_CONTEXT` 里拿到中文 label/window 文案，触发 `apply_english_locale_leak_guard` 把整段解读替换成确定性兜底，造成中英文质量不对等。
- 对话侧：`ids = load_enabled_metric_ids(uid) ∪ {m ∈ infer_wearable_metric_ids(msg) | registry.fact_card.eligible}`；**只影响本轮**，不写 prefs。
- `reference`：若 `resolve_wearable_time_grain(msg).is_point_day()` → 该日；否则 `effective_query_reference_date()`。非点日区间问题（「近 90 天状态」）不属于 `daily_readiness`，由 `anti/precedence` 与 grain 联合排除：grain 非点日且非默认 → 归 `metric_specific`。

**C.5 去字符串特判（`pha/chat_turn_slots.py`）**

将 `plan.profile == "fact_card_interpret"` 的 5 处判断改为槽位判断：

- soul 选择（:66）→ `"FACT_CARD_CONTEXT" in plan.slots_tier0` → `PHA_FACT_CARD_SOUL_MINIMAL`
- background_block 置空（:295）、recalled_snippets 置空（:300）→ 同条件
- manifest 组装（:342）→ 同条件；`card` 为空时 `load_fact_card(uid, reference=..., enabled_metric_ids=...)`（参数由 ctx 携带）
- TASK 选择（:418）→ 同条件
- `USER_BACKGROUND_BRIEF` 分支（:451）已按 `slots_tier1` 判断，无需改。
- `USER_ASSESSMENT_PROMPT` 槽头（:445）现为 zh 字面量 `【用户评估要求 · 本轮解读大纲，不是数值来源】`：改为 `card_copy(locale, "assessment_prompt_head")`，在 `fact_card_copy.py` 补 zh/en 两条；iOS 卡片路径同时受益（消除 en 卡片 system prompt 里的 CJK 槽头）。

**C.6 退役固定文案**

- `_EXERCISE_ADVICE_ONLY_RE` 与 `_deterministic_exercise_advisory`：flag=1 时不再作为主路径；仅当 `wearable_daily_review` 因 `model_unavailable` 失败时作为 fail-closed 兜底，且文案改为**不含任何强度结论**（「模型暂不可用，以下为当日已定账数字：…」+ manifest 焦点行）。flag=0 保持原状。

**C.7 语言**

- `fact_card_interpret_task_text(locale)` 以 `response_locale` 调用；EN 请求出 EN、ZH 请求出 ZH；`apply_english_locale_leak_guard` 现有逻辑照旧。验收：ZH 问题回复中不得出现 `Trend review|Related markers|Recommendations` 标题（加入 `pha_response_language_selfcheck.py`）。

**Tier0 预算**：与 `fact_card_interpret` 同构（9 指标 + 背景摘要已在 `SYSTEM_CONTENT_MAX_CHARS=12000` 下验收）。对话多轮历史在 user/assistant 消息，不占 system。验收：harness report 无 `tier0_budget_exceeded|cap_system_truncated`（9 指标 + 5 睡眠分项 = 最多 14 行时也须通过；若超限，优先裁 `USER_BACKGROUND_BRIEF` 再报 WARN，**不得**裁 T0）。

**验收**：黄金 H9；`pha_goal_arbiter_selfcheck.py`、`pha_harness_profile_registry_selfcheck.py`、`pha_chat_turn_routing_selfcheck.py`、`pha_harness_report_v11_selfcheck.py` 绿；in-process 验收 6 轮（沿用 P14 的验收脚本方式）审计全过。

**回滚**：flag=0。

---

### Wave D（P1 · 会话锚点新增时间粒度维度）

Flag：`PHA_EPISODIC_GRAIN_ANCHOR`（默认 `0`）。

- `pha/session_turn_focus.py`：`SessionTurnFocus` 增 `focus_grain_start: str`、`focus_grain_end: str`、`focus_grain_aggregation: str`（迁移加列，默认 `''`）。写入时机：本轮 `grain.source != "default"`。
- `pha/wearable_time_grain.resolve_wearable_time_grain(msg, *, reference, episodic=None)`：当 `source == "default"` 且 `episodic.focus_grain_*` 非空 且 **`infer_wearable_metric_ids(msg)` 非空（Registry 双语 hints，语言中立）且无时间词** → 返回锚点粒度，`source="episodic_anchor"`。
  - **不得**以 catalog `anaphora.tokens`（现为 zh-only：那/这个/继续…）或 `weak_followup.close_tokens`（是致谢收尾词，不是弱问句）作为继承条件，否则中英文行为不一致。若要用指代词，须先在同 PR 为 `anaphora` 补 `tokens_en`（that / this / same / continue / previous）。
- 过期：锚点仅在同 session、且距写入 ≤ catalog `episodic_grain_ttl_turns`（默认 6）内有效；用户显式时间词永远覆盖。
- Harness report：`episodic.focusGrain`。

**验收**：黄金 H11 两态（flag 0/1）；`pha_health_episodic_selfcheck.py`、`pha_stage3c_wearable_selfcheck.py` 绿。

---

### Wave E（P2 · 表现层对齐）

1. `build_fact_card_event`（SSE `fact_card`）增字段：
   - `label_display`：按 `response_locale` 取 `catalog_labels(mid).point_zh|point_en`（现 `label` 字段是 zh 审计 token，en 用户看到中文卡片；`label` 保留不动以兼容）；
   - `metrics_in_scope`：本轮进入 T0 的 registry ids；
   - `available_not_selected`：当日（或该 grain）账本有值、`fact_card.eligible` 但未进 T0 的 ids（Registry 驱动的存在性探针，复用 `catalog_existence`，不新建探针）；
   - `background_notes_used`：与卡片 `_decorate_interpretation` 同名字段。
2. follow_ups 进 catalog：`health_intent_catalog.json` 新增 `follow_ups.by_profile.{wearable_daily_review,wearable_only}`，每条 chip 必须同时有 `label_zh` / `label_en`（沿用 `session_anchor_labels` / `session_anchor_labels_en` 的既有双语惯例）；`_PROFILE_FOLLOWUPS`（现 zh-only）改为读 catalog 并按 `response_locale` 选 label（保留 Python 常量作 catalog 缺失兜底一个版本）。`build_follow_ups_event` 里 `f"继续聊{tok}"` / `f"看看{mk}"` 两处 zh 字面量改为 `card_copy(locale, ...)`。新增 chip：`{"id":"metric_scope_cluster","label_zh":"加入全部睡眠分项重新解读","label_en":"Re-run with all sleep stages","payload":{"action":"metric_scope","metric_ids":[...簇成员...]}}`，payload 在下一轮作为 C.4 的 turn-local 并集。
3. Web 对话渲染「引用背景 N 条」小字，复用 `fact_card_copy.bg_brief_used`。

**验收**：`pha_e2e_combined_review_sse_selfcheck.py` 扩 SSE 字段断言。

---

### Wave F（P3 · 回归与治理）

- 黄金用例 H9–H13 写入 `docs/harness-eval-set-v1.md` 与 `scripts/pha_e2e_wearable_focus_battery.py`（fixture 用 §1.2 两行数据种子，不依赖真机 DB）。
- `docs/wearable-metric-registry-v1.md` §3 字段速查补 `catalog.*`；§5 新增「D. 新增对话词表：只改 `intent_hints`，跑 `--check`」。
- `docs/harness-change-log.md`、`docs/pha-ios-proactive-change-log.md` 登记；`prd-pha-ios-proactive-agent-v1.md` 新增 FR「对话框解读与事实卡同源」。
- `rules/harness_profile_registry.generated.json` `--write` 重生并提交。

---

## 6. 黄金用例（H9–H13 · 来自 §1.1 真机转录）

固定夹具：`wearable_daily` 两行 = §1.2；用户 fact-card prefs = 默认 5 项（sleep_time_asleep, hrv_sdnn_ms, resting_heart_rate_bpm, steps, active_energy）。

| ID | 轮次输入 | 期望（flag 全开） |
|---|---|---|
| H9 | 「请分析今天的HRV，静息心率和睡眠数据是否适合高强度的力量训练？」 | goal=`daily_readiness`；profile=`wearable_daily_review`；T0 含 HRV/睡眠/RHR（RHR anchor 为 09-08 且标注）；回复 zh；无英文段标题；audit passed；report 无 tier0 截断 |
| H10 | 「今天的睡眠数据没有吗？请核实」 | skip-LLM 允许；输出 5 行：睡眠 8.22h、深睡 0.47h、REM 2.45h、核心睡眠 5.3h、睡眠清醒 0.78h（全部 anchor 2026-09-09）；不出现 90d 均值 |
| H11 | 「核心睡眠是多少？深睡是多少？睡眠清醒是多少？」 | D 开：三行点日值；D 关：三行 90d 均值（**不是**总时长均值） |
| H12 | 「请列出今天的睡眠相关的数据」 | 同 H10 + 若 `sleep_in_bed` 被显式索要且为空 → 一行「库内没有 2026-09-09 的在床记录」 |
| H13 | 「今天静息心率多少？」 | 「库内没有 2026-09-09 的静息心率记录，不会用其他日期或其他指标的数字代替。」 |

**英文镜像用例（H9E–H13E · 与 zh 用例一一对应，必须同时绿）**

| ID | 输入 | 期望（与 zh 镜像的差异只允许是语言） |
|---|---|---|
| H9E | "Based on today's HRV, resting heart rate and sleep, is high-intensity strength training appropriate?" | goal=`daily_readiness`；profile=`wearable_daily_review`；T0 行集合 == H9；回复 en；**不触发** `locale_fallback_applied`；audit passed |
| H10E | "Is there really no sleep data for today? Please verify." | 5 行 == H10（值/anchor 相同），label 用 `label_en` |
| H11E | "How much core sleep, deep sleep and awake time?" | D 开：三行点日值（继承 09-09）；D 关：三行 90d 均值 |
| H12E | "List today's sleep-related data" | == H12 en 版；缺失行用 en 模板 |
| H13E | "What was my resting heart rate today?" | "No verified resting HR in your records for 2026-09-09. Not filled from another date or metric." |

判定方式：selfcheck 对每对 (Hn, HnE) 断言 `goalClass`、`arbiterReason`、`profile`、`wearableMetricResolution.requestedMetricIds`、manifest `(metric_id, value, anchor)` 集合、`audit.passed`、`skip_llm` **完全相等**；仅 `response_locale` 与文本不同。任何一对不等 = 红灯。

反向用例（防止过拟合）：

- 「近 90 天睡眠怎么样」→ 仍 `wearable_only` 区间均值（簇展开后为 5 行均值）。
- 「我的血脂适合训练吗」→ `anti_tokens` 命中 → 不进 `daily_readiness`。
- 「HRV 32 正常吗」→ `metric_specific`，原路径。

---

## 7. 可观测与 Telemetry

- `harness_report.goalClass` 增枚举 `daily_readiness`；`arbiterReason` 增 `goal_readiness_daily`。
- `wearableMetricResolution`（§B）。
- `episodic.focusGrain`（§D）。
- 结构化日志事件（英文键）：`wearable_cluster_expanded`、`focus_missing_for_grain`、`readiness_profile_selected`、`grain_anchor_inherited`。

---

## 8. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| `summaries` 键从 catalog key 改为 registry id 波及面大 | 高 | B.1 提供 `catalog_key_of` 双向映射；grep 全量消费者；`pha_stage3c_wearable_selfcheck.py` + `pha_wearable_p15_selfcheck.py` 为回归网；flag 双路径直到 B.5 |
| 审计标签漂移导致旧缓存/黄金失配 | 高 | 冻结测试逐字相等；`wrist_temp`、`activity_kcal` 特例通过 Registry 字段声明而非代码 |
| 簇展开让 skip-LLM 输出变长 | 中 | `expand_on_cluster_query` 每行可关；`sleep_in_bed` 默认不展开 |
| `daily_readiness` 与 `holistic_assessment` 抢路由 | 中 | catalog 显式 `precedence_over` + `anti_tokens` + lab marker 排除；反向用例入 selfcheck |
| 新 profile T0 超预算 | 中 | 与 fact_card_interpret 同构；验收要求 14 行无截断；超限只裁 Tier1 |
| signed asset schema 被生成器破坏 | 中 | 生成器只改白名单字段；`pha_catalog_registry_selfcheck.py` 守门 |
| 粒度锚点把「昨天」错误继承到无关新话题 | 中 | 仅弱问句/纯指标问句继承；TTL；显式时间词覆盖；report 可见 |

---

## 9. 业界范式对照（宪法 §1 · Wave 补丁级简表）

| 本方案 | 业界对应 | 取舍 |
|---|---|---|
| Registry 单真源 → 生成词表/列名/标签 | Typed tool/schema registry 一处定义、多处生成（OpenAI function schema、Vercel AI SDK tool defs） | 生成而非运行时反射，保持确定性与可 diff |
| 逐项 fail-closed 缺失行 | Grounded generation 的 explicit-null / abstain | 在 Harness 层做，不靠 prompt |
| GoalClassifier 加目标类 + Arbiter 策略表 | Intent → policy table 路由（Rasa policies / Dialogflow intents） | 保持声明式 JSON，不引入 LLM 路由 |
| 会话粒度锚点 | 对话槽位继承（slot carry-over） | 仅继承时间槽，有 TTL 与显式覆盖 |
| 对话复用卡片 T0 组装 | 同一 evidence builder 供多 surface（BFF pattern） | 复用管线而非复制 prompt |

---

## 10. 中英文一致性审查（2026-09-09 复审 · 已并入各 Wave）

审查原则：**同一账本 + 同一问题（仅语言不同）→ 同一 profile、同一 T0 集合、同一审计结论、同一 skip/LLM 决策；只允许文本语言不同。** 语言差异只能出现在「渲染层」（label / 模板 / chip 文案），不得出现在「决策层」（路由 / 取数 / 粒度 / 审计）。

### 10.1 方案本身的双语保证

| 决策层组件 | 语言来源 | 结论 |
|---|---|---|
| 指标识别 `infer_wearable_metric_ids` | Registry `intent_hints`（17 行均含 zh+en；selfcheck 强制） | 中立 |
| 簇展开 / 簇主 / 焦点判定 | Registry `catalog.*` 结构字段，无文本 | 中立 |
| 时间粒度 `resolve_wearable_time_grain` | 今天/今日/today/tonight、昨天/昨晚/yesterday/last night、近N天/last N days、近一周/past week（已双语） | 中立 |
| `daily_readiness` goal | catalog tokens 双语 + `anti_tokens` 双语 + `message_has_lab_marker`（读 catalog `lab_markers`，双语） | 中立 |
| Arbiter 策略表 | 只看 goal_class / existence_probe | 中立 |
| 会话粒度锚点（Wave D） | 仅以 registry ids + 无时间词判定 | 中立（见 F3 修正） |
| Numerics 审计 | manifest `(metric, value, anchor)`，metric 为 zh 审计 token 但与显示语言解耦 | 中立 |
| TASK / Soul | `_FACT_CARD_INTERPRET_TASK`、`PHA_FACT_CARD_SOUL_MINIMAL` 均为英文单版本，仅 T1 示例随 locale 切换；输出语言由 `RESPONSE LANGUAGE` 指令决定 | 中立 |

### 10.2 复审发现并已修正的不对等点（F1–F8）

| # | 发现 | 影响 | 修正落点 |
|---|---|---|---|
| F1 | `compose_fact_card` 无条件用 `load_fact_card_locale(user_id)`（iOS 卡片偏好），不看本轮 `response_locale` | en 对话用户拿到 zh label/window 文案的 `FACT_CARD_CONTEXT` → 模型 CJK 泄漏 → `apply_english_locale_leak_guard` 用兜底摘要替换整段 → **en 解读质量系统性低于 zh** | §C.4：`load_fact_card` / `compose_fact_card` 加 `locale` 透传 |
| F2 | `USER_ASSESSMENT_PROMPT` 槽头 zh 字面量 | en system prompt 混入 CJK | §C.5：`card_copy(locale, "assessment_prompt_head")` |
| F3 | Wave D 初稿引用 catalog `weak_followup`（实为致谢收尾词）与 `anaphora`（zh-only） | en 追问无法继承粒度 | §D：改为纯 registry ids + 无时间词判定 |
| F4 | `_PROFILE_FOLLOWUPS`、`继续聊{tok}`、`看看{mk}` zh-only | en 用户看到中文 chip | §E.2：catalog `label_zh/label_en` + `card_copy` |
| F5 | `build_fact_card_event.label` 是 zh 审计 token | en 用户 SSE 数字卡显示中文 | §E.1：新增 `label_display` |
| F6 | `goal_markers.holistic_assessment` zh-only（3F 遗留） | `daily_readiness.precedence_over` 在 en 侧无对手，zh/en 路由结果可能不同 | §C.1：同 PR 补 en tokens |
| F7 | `_COMPARE_ALL_METRICS_RE` zh-only；`_STAGE_HINT_RE` 无 `sleep stages` | en 「compare all metrics」走窄焦点、「sleep stages」不展开分期 | §B.2：迁 catalog / 补 en hints |
| F8 | `_METRIC_LABEL_EN_FALLBACK` Python 硬编码兜底；部分 Registry 行缺 `ui.label_en` | en label 来源分裂 | §4.1：`label_en` 强制非空，删除兜底表 |

### 10.3 已知但不在本轨道修的既有不对等（登记 backlog）

- `apply_english_locale_leak_guard` 只有 en 侧（CJK 泄漏 >12% 即整段替换），zh 侧无对称守卫（英文标题混入 zh 回复不拦）。本方案通过新 profile 的 soul 禁止三段式英文标题 + `pha_response_language_selfcheck.py` 断言缓解；对称的 zh 守卫另立 P2。
- `leftover_s_level_numeric_tokens` 对 zh 单位（毫克/微克）识别弱于 en（mg/mcg）——P14 验收时已发现，属 Numerics 审计单位表问题，另立 P1（审计只能更严不能更松，故必须补 zh 单位而非放宽 en）。
- `_LAB_MARKERS_RE`（`intent_gates.py`，含 肝功能/肾功能/血糖/hba1c）与 catalog `lab_markers`（含 cholesterol/lipids/blood test）两套来源、覆盖不同；本方案只使用 catalog 版；合并另立 P2。

### 10.4 验收口径

- §6 zh/en 镜像用例对对相等（决策层字段集合逐项 `==`）。
- `pha_response_language_selfcheck.py` 新增：新 profile 在 en 下 `locale_fallback_applied == False`；在 zh 下无 `Trend review|Related markers|Recommendations`。
- in-process 验收：H9 与 H9E 各 ≥3 轮真模型运行，audit 全过，且两侧 `wearableMetricResolution` 相同。

---

## 11. 交付清单（每 Wave 一个 PR）

- [ ] PR 首条含 §0 四行 ACK 与 P0/P1/P2 声明（未开 PR，等维护者 commit）
- [x] Registry / Catalog JSON 变更 + 生成脚本 `--check` 零漂移
- [x] 无新增 Python 字面量词表/标签表（reviewer 用 `rg "\"今日|均值|深睡|REM\"" pha/` 抽查，命中只允许出现在测试冻结快照）
- [x] `python scripts/pha_harness_profile_registry_generate.py --write`（Wave C）
- [x] selfcheck 清单绿：`pha_wearable_registry_selfcheck` · `pha_numerics_manifest_selfcheck` · `pha_wearable_metric_probe_selfcheck` · `pha_grounded_composer_selfcheck` · `pha_goal_arbiter_selfcheck` · `pha_harness_profile_registry_selfcheck` · `pha_chat_turn_routing_selfcheck` · `pha_health_episodic_selfcheck` · `pha_response_language_selfcheck` · `pha_fact_card_selfcheck` · `pha_e2e_wearable_focus_battery`（含 `pha_chat_fact_card_parity_selfcheck`）
- [x] `docs/harness-change-log.md` + `docs/pha-ios-proactive-change-log.md` 已写回滚路径与真机转录（未随 PR 提交）
- [x] `./scripts/pha_restart_accept.sh` 真机验收：H10–H13/H10E/H13E skip-LLM；H9-zh 对话+interpret；H9E 审计过。转录见 proactive change-log 16:51
