# 交接 · 2026-09-14 · zip Record 原样入库 + Cardio Recovery 升舱

> **Language / 语言**：[English](handoff-2026-09-14-zip-passthrough-and-cardio-recovery.en.md) · 中文（本文）

> 写给接替的 coding agent · **P21a/P21b 已编码；P21c 未开**  

**状态：M1-P21a DONE（含对话读路径 v1.27）· M1-P21b DONE（夹具样本）· P21c TODO。** 本机账本仍无 recovery 行，需 zip 回灌。未改 prefs / Find device_verified / ingest POST keys。

---

## 0. 一句话

zip 白名单是导入器历史实现，不是 Loop 契约。未知 HK `Record` 应先**原样**进 `wearable_data`；对话与事实卡在**未注册**前必须 fail-closed。Cardio Recovery 不得靠 Loop 审批「发明列」。Loop A 只给**已存在**的 catalog metric 加叫法。

---

## 1. 磁盘现状（2026-09-14 已核对）

| 层 | 现状 |
|----|------|
| 健康 App | 浏览 → 心脏 → **Cardio Recovery**（中文常见 **有氧恢复**）；旧名 Heart Rate Recovery |
| HealthKit / zip XML | `HKQuantityTypeIdentifierHeartRateRecoveryOneMinute`（运动结束后 1 分钟心率下降，bpm，正值） |
| zip 导入 | `pha/data_importer.py` `_SUPPORTED_RECORD_TYPES`；`Record@type` 不在集合则不调用 `_consume_record` |
| ingest / 捷径 | FR-1.4 与 `shortcut_health_find_catalog.json` 无此类型；Find 标签**未**真机抄录 |
| 注册表 | 无 `cardio_recovery*` / `heart_rate_recovery*` |
| Intent Catalog | 无该 metric key；Loop A 人审对「未知 metric」= 拒绝 |
| 本机账本 | `wearable_data` 无 `*recover*` / `HeartRateRecovery` 行 |
| 对话 | 缺行后用 HRV/VO2max 推测 — **禁止**作为验收金标 |

已在白名单内的类型（步数、心率、RHR、HRV SDNN、睡眠、消耗、血氧、呼吸率、VO2max、腕温/体温）**继续走现有类型化路径**，P21a 不得双重写入。

---

## 2. 三层边界（不得打通）

```text
L0  zip / ingest 样本    →  P21a 原样 wearable_data
L1  日表 + Registry      →  P21b 才有 metric_id / temporal / 基线 / 发卡
L2  catalog 点名         →  已注册走日表；未注册走 L0 唯一命中写入本轮 Manifest
L3  Loop A 别名          →  仅挂已有 catalog key；永不改 registry / 导入器
```

对话点名**不是**每问一次升舱一次。升舱只为日表、事实卡、捷径、中文别名。

对照 [`wearable-metric-registry-v1.md`](wearable-metric-registry-v1.md) §2：新 Raw 形态要一次 L1 PR + 一行 Registry。对照 Loop SOP 铁律 5：**Loop 不改路由/registry**。

---

## 3. 任务卡（编码时再改 §8 状态）

| ID | 做什么 | 不做什么 |
|----|--------|----------|
| **M1-P21a** | zip 中**未**走类型化分支的 `Record` 以 HK `type` 字符串写入 `wearable_data`（value/unit/start/source/`sample_id` 幂等） | 不自动加日表列；不 `fact_card.eligible`；不改 prefs；不猜捷径 Find 名；不弱化 Numerics；不开 M2 |
| **M1-P21b** | 以库内真实 `HeartRateRecoveryOneMinute` 样本为准，注册 `metric_id` + 日聚合 + catalog key；对话点名只取该列 | 无样本则不做「空注册表行」充数；禁止人群范围（无 sourced 指南）；禁止用 HRV/VO2max 顶；无因果声称 |
| **M1-P21c** | 真机抄录「查找健康样本」字面量后，才进 Find 总表 + ingest 别名 + 增量捷径 | 禁止用健康 App 标题 / SDK 名猜 Find（catalog `never_use_find_labels` 同类） |

**顺序强制：a → b → c。** c 可晚于 b；无 a 的样本则 b 不得标 DONE。

M1 事实卡里程碑保持 **DONE**。本切片是账本补全，不重开 M1，不提前 M2。

---

## 4. P21a 实施方案（原样入库）

### 4.1 产品契约

- 目标：export.zip 里出现过的数量型 `Record`，Mac 账本要能按类型找回，而不是静默丢弃。
- 「原样」= 保留 Apple 的 `type`、`value`、`unit`、`startDate`/`endDate`、`sourceName`；**不**在 L0 把未知类型映射成 HRV/RHR/VO2max。
- 睡眠 `HKCategoryTypeIdentifierSleepAnalysis`、已类型化的数量型、以及已有 Workout 路径：**不改语义**，仍走现有分支。
- 未知 **Category**（非睡眠）默认仍跳过，直至另开卡；本刀范围 = 带数值的 `Record`（`value` 可解析为有限浮点）。无法解析的 value fail-closed 跳过该条，不编数。

### 4.2 建议落点（编码时）

- `pha/data_importer.py`：`type in _SUPPORTED_RECORD_TYPES` → 现有 `_consume_record`；else 若为可解析数量 Record → `WearableDataBatchWriter.add_sample(metric_type=HK_type_string, …)`。
- `sample_id` 继续用现有 zip 幂等键风格（含 type + start + source），重复导入 `INSERT OR IGNORE` / 现有 UPSERT，禁止复制行。
- `metric_type` 存储 **完整 HK identifier**（如 `HKQuantityTypeIdentifierHeartRateRecoveryOneMinute`），禁止 Python 药名/指标名对照表把「Cardio Recovery」写死成别的列。
- 日表重建：未注册类型 **不得** 擅自 mean/sum 进 `wearable_daily` 已有列。P21a 验收只查 `wearable_data`。
- zip 覆盖（FR-1.8）：passthrough 行与类型化行同一套 `xml_max` 日覆盖；不另发明 overlay。
- 体积：passthrough 只吸收**当前白名单之外**的数量 Record。心率已在白名单，不会因本刀再写一份。导入前后行数、RSS 写入 telemetry（宪法第二条），超红线再单独立卡（例如高频未注册类型抽稀），**禁止**为此加业务硬编码例外表。

### 4.3 对话读路径（v1.27）

先 catalog。未命中则查 `wearable_data` 里未升舱的 `HKQuantityTypeIdentifier*`，用 HK id 派生针（去前缀、CamelCase 拆词）做最长唯一匹配：库里有且唯一命中 → 写入本轮 Numerics Manifest 反馈；没有或不唯一或中文名对不上派生词 → fail-closed。**禁止**用 HRV/VO2max 顶台。不自动加日列、不改 prefs、不猜 Find。Cardio Recovery 已升舱后仍走 catalog，不走 L0 派生针。

### 4.4 验收（P21a）

- 夹具 XML：一条 `HeartRateRecoveryOneMinute` + 一条已支持类型（如 VO2max）→ 前者进 `wearable_data` 且 `metric_type` 为完整 HK id；后者仍走旧列。
- 夹具：未知类型非法 value → 不写行。
- 再导入同一 `sample_id` 不倍增。
- 问「walking steadiness」且夹具有 `AppleWalkingSteadiness` 行：Manifest 含该样本，不上 HRV/VO2max。
- 问「步行稳定性」（对不上 HK 派生词）且无 catalog 别名：fail-closed，无替身数字。
- 问「Cardio recovery」：走已升舱 catalog，exclusive，不上 HRV/VO2max。
- 相关 selfcheck 绿；**不**改 `data/fact_card_prefs.json`。
- FR-1.4 v1.27 已写明对话读路径。

---

## 5. P21b 实施方案（Cardio Recovery 升舱）

触发：P21a 后本机或夹具中 **确实有** `HKQuantityTypeIdentifierHeartRateRecoveryOneMinute` 行。

### 5.1 注册表（只改 JSON + 必要日列，禁止 Python 指标名表）

建议 `metric_id`：`cardio_recovery_1min_bpm`（英文键；UI `label_en=Cardio Recovery`，`label_zh=有氧恢复`）。

| 字段 | 建议 |
|------|------|
| `l1.kind` | `wearable_daily`（需新日列则 **一次** aggregator PR，列名英文） |
| 日聚合 | 同日多次训练：默认 **max**（当日最大 1 分钟下降）；卡上写实际 `day` |
| `temporal.kind` | `daily_lagged` 或 `latest`（与健康 App「某次运动后」对齐；编码时以健康 App 展现为准，禁止猜） |
| `fact_card.eligible` | 升舱完成才 `true`；**默认不勾选**（不改现网 prefs） |
| `reference_range` | **不做**，直至有 sourced 指南（同深睡/REM 占比裁定） |
| `catalog.key` | 新 key（如 `cardio_recovery`），**不要**并进 `hrv` / `vo2max` 簇 |

弱因果：建议/解读只用相关、伴随、可观察措辞；禁止「导致 / causes」。

### 5.2 意图与对话

- `intent_hints` / catalog aliases 放 **Cardio Recovery**、有氧恢复、Heart Rate Recovery、心肺恢复等人类叫法；**Loop A 仍不得在无 key 时提案**。
- `infer_wearable_metric_ids("…Cardio recovery…")` → 仅该 `metric_id`。
- skip-LLM / Manifest / 发卡 ⊆ scope；缺行只声明缺失。
- 金标（回归）：同一句「查询库里的 Cardio recovery」在升舱前 fail-closed 无替身数字；升舱后若有值则只引该列，不得展开 HRV/VO2max 专题段（exclusive 点名）。

### 5.3 验收（P21b）

- registry selfcheck；日表列与样本对账（单位 bpm，正值）。
- `pha` 对话/interpret 离线用例：点名 recovery 不出现未点名 HRV/VO2max 精确值。
- 不改 prefs；腕温权限策略不动。

---

## 6. P21c（增量捷径，可延期）

- 真机「查找健康样本」选择器抄录字面量 → `shortcut_health_find_catalog.json` `device_verified`。
- 未验证 = 禁止写捷径（与 VO2 Max vs Cardio Fitness 教训相同）。
- ingest 别名：`cardio_recovery` / HK id → 同一 `metric_id`。
- 增量不得与 zip 最终真值冲突（FR-1.8）。

---

## 7. Loop A 在本切片中的位置

| 允许 | 禁止 |
|------|------|
| P21b catalog key 存在后，周更 harvest 把口语别名提案到该 key | 对话一句新词立刻 `loopapr` |
| 人审后路径 B 本机别名 | 未知 metric 提案；Loop PR 改 importer / registry / daily schema |
| 拒毒性 token | 运行时 LLM 自愈、catalog 自动 merge |

P21a 完成但 P21b 未开时：**不应**出现「把 Cardio recovery 批进白名单」的审批。那是把 Loop 误当成 schema 迁移。

---

## 8. 编码开工口令

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

触及启动再叠 `CONSENSUS_ACK: stability-plan-v2026-06-10 read`。

真源：本文 + PRD v1.24 §8 M1-P21a/b/c + §11 本条。冲突时：**数值诚实与 fail-closed 优先**。

---

## 9. 硬红线（全程）

- TurnEvidencePlan 先于 LLM；用户可见数字 ⊆ Numerics Manifest。
- 禁止 Python 新增 phrase / metric / label / 药名硬编码表；禁止为过测加黄金一句 `if`。
- 禁止 must 覆盖 / 缺行重试 / prefs∩ / 扫全卡推翻 exclusive / 翻转 Data > Context。
- 禁止用「更主动」削弱审计；禁止裸 Ollama。
- 未要求不 commit；本交接对话 **不 git**（除非维护者另说）。
- 未开 M2 / Watch App / APNs / 云。

---

## 10. 回滚

文档-only：删本文引用、§8 三行、§11 本条、change-log 本条，PRD 版本回到 v1.23。  
编码后：P21a 关 passthrough 开关或恢复 `_SUPPORTED_RECORD_TYPES` 门；P21b 删 registry 行与日列迁移脚本（先 dry-run）。
