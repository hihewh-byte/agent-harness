# 交接 · 40+40 评测审计落地方案（v1.15 · M1-P19）

> **Language / 语言**：[English](handoff-2026-09-10-eval-audit-solution.en.md) · 中文（本文）

> 写给接替的 coding / 真机验收 agent · 2026-09-10  
> 维护者授权：把三方案审计写成最终解决方案并开工。  
> 首条实施回复必须输出：

```text
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read
```

真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.15** · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) §15–§16 · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md)  
前序：[`handoff-2026-09-09-outline-and-context-lookup.md`](handoff-2026-09-09-outline-and-context-lookup.md)（P17/P18 已关账）

**禁止**：must 覆盖 / 缺行重试；用 iOS prefs ∩ 裁对话簇展开；Python 指标名 / 黄金一句 if；翻转 Data > Context；提前 P15；弱化 Numerics；未改本文档与 PRD/RFC 先改 TASK。

---

## 0. 因痛起案（宪法第二条）

2026-09-09 解读 40 + 2026-09-10 对话 40（`qwen3:14b` · 8788）：

| # | 现场 | 不是什么 | 架构缺口 |
|---|------|----------|----------|
| A | 黄金句解读从 RHR 起笔，只写点名四项；活动消耗/血氧 0/20 | 分类器错（仍是 emphasis） | TASK 没要求第 1 句 overall；模型把「重点看」执行成 exclusive |
| B | 冒烟 `tier0_budget_exceeded`；Manifest KV 尾缺，FACT_CARD_CONTEXT 六行仍在 | 卡没数 | 默认 T0 预算 4500；soul+T0 超 `SYSTEM_CONTENT_MAX_CHARS` 时 `_cap_system_content` **尾切**（Manifest 在最后） |
| C | 黄金句对话 SSE 出现 `workout_heart_rate_range_bpm` / `workout_count_recent` | 用户勾了锻炼项 | `workout` 簇 `intent_hints` 含光秃「运动/training」；「运动训练/力量训练」是 daily_readiness 大纲词，不是锻炼指标 |
| D | 评测 `selected_gap` 用「勾选有值就必须点到」 | PRD 回归红灯 | 与已冻结 emphasis「可同段带过、不做扫全卡」不一致。痛点真实，金标用错 |

三方案原文审计（编码前已驳回/改写，见对话 2026-09-10）：

| 方案 | 裁决 | 本卡落地 |
|---|---|---|
| 1 勾选 must + 缺行重试 + 修 Tier0 | **部分驳回** | **只修 Tier0**：卡上已有行 KV 不得被尾截断。must/重试不做 |
| 2 第 1 句 overall、句中无 metric label | **有条件通过** | 只改英文 TASK；exclusive 不得要求整体起笔；验收走 catalog 分档家族 |
| 3 发卡 ⊆ 勾选 ∩ scope | **原文驳回，改写后立** | `wearable_daily_review` SSE ⊆ 本轮 FACT_CARD_CONTEXT 的 metric 行；睡眠簇仍可因「睡眠各项」展开；训练词不把 `workout_*` 塞进 scope |

---

## 1. 冻结口径

1. **emphasis ≠ cover-card。** 不得把「可同段带过」改成「有值必须点到」。不得生成后缺行再跑一轮 LLM。
2. **Tier0 生存权。** harness 硬约束第 2 条：TASK / FACT_CARD_CONTEXT 指标行 / NUMERICS_MANIFEST KV **不得被尾截断挤掉**。事实卡 profile **不得**走 `format_manifest_tier0_block` 默认 600 字砍 KV。超限先压 FACT_CARD_CONTEXT 的 advice/summary（min 仍保留 values），再报 ERROR；禁止 `_cap_system_content` 砍 T0。
3. **结构句只进 TASK。** Python 不解析评估要求里的指标 id（v4 §4.3）。不得焊死某一中文黄金句。
4. **发卡真源是本轮卡，不是 infer 兜底。** 有 `FACT_CARD_CONTEXT` 时，SSE `metrics_in_scope` / entries ⊆ 该卡 `enabled_metric_ids`（含本轮因簇展开而并入卡的行）。无卡才允许 `infer_wearable_metric_ids`。
5. **训练词 ≠ 锻炼簇。** Registry `workout_*` 的 `intent_hints` 只收点名锻炼指标的说法（锻炼心率、锻炼次数…）。`goal_markers.daily_readiness` 的「训练/力量训练/运动类型」只升舱 profile / 进大纲，不取 `workout_*` 数。
6. **红线不变。** 不翻转 Data > Context；不开 P15；不为黄金一句写 if；不弱化 Numerics。

---

## 2. 任务卡 M1-P19

| 项 | 内容 |
|---|---|
| ID | **M1-P19** |
| Flag | 无新 flag。大纲仍 `PHA_ASSESSMENT_OUTLINE`；簇展开仍 `PHA_WEARABLE_CLUSTER_EXPAND` |
| Harness 类别 | **P1**（TASK 契约 + Tier0 生存权 + Registry hints + 发卡范围） |
| 不做 | must 覆盖、缺行重试、prefs∩、P15、C3 brief 切片（仍是 Data>Context 既定代价，另卡） |

验收（离线 selfcheck，断言走枚举/registry，禁止某一中文 prompt equals）：

| ID | 场景 | 通过 |
|---|---|---|
| P19-T | emphasis TASK 含 Sentence 1 = overall、无 metric id/中文指标名；exclusive TASK **不含** overall 起笔句 | `pha_p19_selfcheck` |
| P19-K | 含 daily_readiness 训练词、不含锻炼心率/次数点名 → `infer_wearable_metric_ids` **不含** `workout_*`；点名「锻炼心率范围」仍含 | 同上 |
| P19-S | 「睡眠的各项」仍展开 sleep 簇（深/REM/核心/清醒） | 同上 |
| P19-C | 有 fact_card payload 时 SSE `metrics_in_scope` ⊆ 卡 `enabled_metric_ids`，即使用户句含「运动训练」 | 同上 |
| P19-B | `fact_card_interpret` 大卡：组装后 T0 含全部 Manifest 数值；无「系统提示已熔断截断」砍 T0；`protect_tier0` 路径不尾切 | 同上 |

真机（本卡不挡关账，维护者另排）：黄金句解读第 1 句谈整体再点名；对话发卡无 `workout_*`。

---

## 3. 回滚

- TASK emphasis 结构句：git revert `harness_plan.py` 对应段（缓存键 `_interpret_prompt_rev` 会自动变）。
- Tier0：revert `harness_tier0_assembly.py` / `chat_message_stack.py`。
- workout hints：revert registry + `pha_wearable_bundle_schema_generate.py --write`。
- 发卡：revert `grounded_answer_composer.py`。

---

## 4. 明确不做（本卡）

- 勾选有值 must 覆盖 / 缺行重试
- Apple Readiness 0–10 抄进通知或 TASK
- C3「药物对 HRV」灌 brief（不翻转 Data > Context）
- 提前编译 CHB / P15
- 把评测 `selected_gap` 金标写进产品
