# Wearable Metric Registry v1 — 运维与扩展手册

> **状态**：**已编码**（Wave 3d-δ-c · `pha-v2.3.23`）  
> **配置真源**：[`storage/registry/wearable_metric_registry.json`](../storage/registry/wearable_metric_registry.json)  
> **加载模块**：`pha/wearable_metric_registry.py`  
> **上位法**：[`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md) · [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md)

---

## 1. 解决什么问题

| 用户期待 | PHA 裁定 |
|----------|----------|
| 对话里说「我要看 X 指标」 | **意图映射**到 `metric_id`（配置/Registry），**禁止** LLM 写 SQL |
| 后台自动把 Raw 变成 90d 基线 | 仅当 **L1 管道 + Registry 行** 已存在；对话可**触发**已注册 `ingest_module` |
| 新增指标不要每次改 Python 列表 | **日列已存在** → 只改 JSON；**新 Raw 形态** → 一次 L1 PR + 一行 Registry |

Gemini 所称「已完全 Registry 化」在 **δ-c 之前**仅存在于 Spec；自 **v2.3.23** 起，`build_wearable_compare_table_v1` 的日指标列表、锻炼条件行、中文标签与 Fallback 脚注均从 JSON 读取。

---

## 2. 三层边界（维护成本最低）

```text
L0  解析器（每种 Apple/HK 类型 · 一次性代码）
      import / backfill_workouts / sleep segment …
         │
L1  日事实（wearable_daily 列 · workout_sessions · …）
         │  ← Registry: l1.kind + field + rollup
         │
L2  CompareTable（mean/range/verdict · 纯确定性）
         │  ← Registry: compare.* + snapshot.parser
         │
L3  LLM 叙事（只引用 Tier0 表 · Audit 拦截）
```

**写代码**：新 `l1.kind`（例如未来 `hk_respiratory_detail`）。  
**只改配置**：`wearable_daily` 已有列，打开 `comparable_90d` 或加 `intent_hints`。

---

## 3. Registry 字段速查

| 字段 | 用途 |
|------|------|
| `metric_id` | 与 OCR / Compare 行 / Audit token 对齐 |
| `l1.kind` | `wearable_daily` · `workout_sessions` |
| `l1.field` | 数仓列名（日表） |
| `compare.comparable_90d` | 是否尝试 90d 基线 |
| `compare.snapshot_only_if_no_baseline` | 有截图无数仓时仍出 `snapshot_only` 行（深睡/REM） |
| `compare.conditional_row` | 仅 intent/截图命中时出锻炼行 |
| `ui.label_zh` / `intent_hints` | LLM 表与 Audit 段内匹配 |
| `ui.footer_when_snapshot_only` | Fallback 脚注（禁止硬编码 metric 名） |
| `ingest.module` | 关联 `ingest_modules[].module_id` |
| `fact_card.eligible` | 是否允许出现在事实卡勾选列表 |
| `fact_card.enabled_default` | 无用户偏好时的默认勾选（默认 ≠ 不可改） |
| `fact_card.ingest_key` | 对应 `POST /ingest/healthkit` 的 `metric_type`（可空） |
| `fact_card.unit` / `higher_is_better` | 完整卡展示与分档方向 |
| `fact_card.daily_key` | ingest 按日历日一条 UPSERT |
| `fact_card.shortcut_health_type` / `shortcut_stat` / `shortcut_unit` | 捷径 **Find Health Samples 选择器标签**（不是 HealthKit SDK 名、也不是健康 App 浏览页标题）。活动消耗必须是 `Active Calories`，禁止 `Active Energy`。`shortcut_stat` = Sum/Average；`shortcut_unit` = kcal / count/min |
| `fact_card.shortcut_skip_reason` | 有 ingest_key 但捷径故意不同步（须写原因，禁止默默映射） |
| `fact_card.include_when_selected` | 用户勾了所列 metric_id 时，本行也进捷径（HRV SDNN 在勾了 RMSSD 时同步） |
| `fact_card.shortcut_sleep_value` | Sleep Analysis 分期标签（`Asleep Deep` 等）。有此字段的行进「PHA 同步睡眠」，不进数量捷径 |
| `fact_card.reveal_when_selected` | 勾了所列指标时，完整卡多显示本行（睡眠分期） |
| `fact_card.display_fallback_metric_id` | 本行无数时改展示另一列，且用那一列做基线；标签跟过去，禁止把 SDNN 标成 RMSSD |

### `no_baseline_reason`（Spec 枚举 · 行级 reason_code 待 ε+）

见 [`stage3d-delta-wearable-fact-pipeline-spec.md` §2.2](stage3d-delta-wearable-fact-pipeline-spec.md)。

---

## 4. 增量同步 API（非 per-metric 硬编码）

| 端点 | 说明 |
|------|------|
| `GET /data/sync-modules` | 列出 Registry 中 `ingest_modules` |
| `POST /data/upload` | **唯一推荐**：全量 import（Apple export 为全量快照） |
| `POST /data/sync-module/{module_id}` | **已下线**（410） |
| `POST /data/backfill-workouts` | **已下线**（410） |

新增模块时：实现 L0 解析 + 在 JSON 增加 `ingest_modules` 条目 + 在 `main.data_sync_module` 接线 **一次**，不要新增 `/data/backfill-xxx` 专用路径。

---

## 5. 标准作业：新增指标

### A. 仅纳入对比（列已有）

1. 在 `wearable_metric_registry.json` 的 `metrics` 追加一条（`l1.kind=wearable_daily`）。  
2. 跑 `scripts/pha_wearable_registry_selfcheck.py` + `pha_wearable_compare_table_selfcheck.py`。  
3. bump `build_marker` · 重启。

### B. 新 Raw → 新日列（如未来 SpO2 夜间明细）

1. L0：`data_importer` / 聚合器（一次性）。  
2. Registry 一行。  
3. golden_compare / 真机 gate。

### C. 用户对话新话术

1. 扩 `intent_hints` 或 Catalog 映射（**不写 SQL**）。  
2. 若 `metric_id` 未注册 → 统一回复「当前版本暂未纳入可对比指标」。

---

## 6. 当前注册表快照（2026-06-01）

与 JSON 同步；**勿**在本表单独维护第二份名单。

| metric_id | l1 | comparable | 备注 |
|-----------|-----|------------|------|
| sleep_time_asleep | daily | ✅ | |
| hrv_rmssd_ms | daily | ✅ | |
| resting_heart_rate_bpm | daily | ✅ | |
| spo2_percent | daily | ✅ | 无 OCR 则省略行 |
| respiratory_rate | daily | ✅ | 3d-ε |
| sleep_deep / sleep_rem | daily | ✅ | 无数仓时 `snapshot_only` |
| workout_* | workout_sessions | ✅ 条件行 | 需 `hk_workout` 增量或全量导入 |

---

## 7. 后续波次（未做）

| 项 | 说明 |
|----|------|
| Dashboard 下拉 | 读 `GET /data/sync-modules` 替代写死「锻炼」按钮文案 |
| `reason_code` 入 CompareRow | 与 Spec §2.2 完全对齐 |
| 对话 Discover→Promote | 与 `dynamic_slot_registry` 联动（仅元数据，非 SQL 生成） |
| 授权截图区间端点 | 3d-ε+ 减少 `compare_table_numeric_drift` Fallback |

---

## 8. 验收

```bash
cd agent-harness
python scripts/pha_wearable_registry_selfcheck.py
python scripts/pha_wearable_compare_table_selfcheck.py
./scripts/pha_restart_accept.sh
```

`/health` 的 `pha_build` 应为 `pha-v2.3.23-wave3d-delta-c-metric-registry`。
