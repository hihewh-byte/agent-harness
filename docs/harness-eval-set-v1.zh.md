# harness.eval_set / v1

> **Language / 语言**：[English](harness-eval-set-v1.md) · 中文（本文）

> **薄切片（2026-07-13）：** schema + golden 导出 + 离线校验器 + alias fuzz。  
> **尚未包含：** live HTTP runner、全量题库重写。  
> **归属：** Harness Loop · [`packages/harness_loop`](../packages/harness_loop/) · goldens 在 [`evals/goldens/`](../evals/goldens/)。

可移植评测集契约，用于跨域回归与 Loop promote 门禁。
领域题库（PHA `e2e_question_bank_*.json`）仍是丰富源；eval_set 是供 CI / veto / 销售演示使用的
**已导出、已版本化、由 suite 持有** 的子集。

## Schema

```json
{
  "schema": "harness.eval_set/v1",
  "id": "pha.smoke.v0",
  "domain": "pha",
  "version": "0.1.0",
  "description": "…",
  "cases": [ /* EvalCase */ ]
}
```

### EvalCase

| 字段 | 类型 | 必填 | 说明 |
|-------|------|----------|-------|
| `id` | string | yes | 稳定 id，例如 `EN08.t1.steps` |
| `tags` | string[] | no | `loop_a`, `loop_b`, `3h`, `locale`, `bank` |
| `locale` | `en` \| `zh` \| `any` | no | 给 runner 的提示 |
| `turns` | Turn[] | yes | ≥1 |
| `expects` | Expect[] | yes | ≥1；offline 和/或 live |
| `source` | object | no | 回溯到领域题库的出处 |

### Turn

| 字段 | 类型 | 说明 |
|-------|------|-------|
| `role` | `user` \| `assistant` | v1 goldens 只用 `user` |
| `text` | string | 解析后的话语 |
| `attach` | bool | 默认 false |
| `slot` | string | 可选题库 slot id |

### Expect（v1 离线子集）

| `type` | 字段 | 含义 |
|--------|--------|---------|
| `non_empty_turn_text` | — | 用户回合文本非空 |
| `catalog_alias` | `metric`, `alias` | 领域 catalog 必须包含 alias（PHA: health_intent_catalog） |
| `min_turns` | `n` | `len(turns) >= n` |
| `tag_required` | `tag` | case 必须带该 tag（元数据） |
| `live_non_empty_answer` | — | 预留给 live runner（离线忽略） |
| `live_locale` | `locale` | 预留给 live runner（离线忽略） |
| `alias_must_reject` | `metric`, `alias` | 离线：1E gates / classifier 必须拒绝 promote |

## 本仓库中的 Golden sets

| 路径 | 用途 |
|------|---------|
| `evals/goldens/pha_smoke_v0.json` | EN07/EN08 + QS07 smoke + alias `多少步` 离线检查 |
| `evals/goldens/pha_alias_fuzz_v0.json` | Loop A 拒绝语料（OCR/UI junk + 1E-a）+ 精选对照 |

从题库 / fuzz 语料重新生成消息：

```bash
PYTHONPATH=. python scripts/pha_eval_set_export_smoke.py --write
PYTHONPATH=. python scripts/pha_eval_set_export_alias_fuzz.py --write
PYTHONPATH=. python scripts/pha_eval_set_selfcheck.py
PYTHONPATH=. python scripts/pha_eval_set_alias_fuzz_selfcheck.py
```

## 与 Loop 的关系

- Loop A `--full-veto` 日后可通过 `suggested_regression` 消费 eval_set ids。
- Alias fuzz 锁定 `gate_1e_d_ocr_ui_junk`（有毒 `Query→hrv` 类）+ 1E-a 模板。

## PHA 聊天 ↔ 事实卡对等（H9–H13）

离线夹具用例在 `scripts/pha_chat_fact_card_parity_selfcheck.py`（不是 HTTP Loop goldens）。Live 8788（`qwen3:14b`，2026-09-09 ledger）记录于 2026-09-09 16:51，见 `pha-ios-proactive-change-log.md`。

| ID | Locale | Expect |
|---|---|---|
| H9 / H9E | zh / en | `daily_readiness` → profile `wearable_daily_review` |
| H10 / H10E | zh / en | today sleep cluster point-day（5 行；无 90d mean） |
| H11 / H11E | zh / en | grain inherit on；90d stage means off |
| H12 | zh | sleep cluster；仅在被问及时才缺 in-bed |
| H13 / H13E | zh / en | 今日 RHR fail-closed（不对调昨天） |
