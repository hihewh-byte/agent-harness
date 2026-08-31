# Tax Harness Build Report Schema（`tax.harness_report/v2`）

> **Aligned**: 2026-07-09 · Phase A P0 · implementation in `tax_agent/harness_report.py`  
> **Supersedes**: informal v1 notes below are obsolete where they conflict with v2.

每轮 `/tax/chat` 在 `TAX_HARNESS_REPORT=1`（默认开启）时于响应 `harnessReport` 返回；`TAX_HARNESS_DEBUG=1` 时额外写入 JSONL。

**Privacy**: reports store `userMessageSha` + length only — not raw message text. Do not commit JSONL dumps or personal filing DBs.

## 顶层字段

| 字段 | 说明 |
|------|------|
| `schema` | 固定 `tax.harness_report/v2` |
| `turnId` | `{sessionId}:{userMessageSha}` |
| `ts` | ISO8601 UTC |
| `mode` | `dry_run` / `narrative_fast` / `llm_tools` / `rules` … |
| `action` | `compute` / `none` / `plan_dry_run` / `show_filing_table` … |
| `plan` | 目标 Harness 契约 |
| `runtime` | 实际执行 |
| `numericsAudit` | 数字审计结果 |
| `planVsActual` | **P0** 结构化 plan↔runtime 差分码（见下） |
| `warnings` | 人类可读/兼容列表（含 `planVsActual` 码 + numerics warnings） |

## `plan`

| 字段 | 说明 |
|------|------|
| `profile` | `filing_narrative` / `compute` / `filing_onboarding` … |
| `journeyPhase` | 旅程阶段 |
| `taxYear` | 本轮解析年度 |
| `slotsTier0` / `slotsTier1` | 证据槽 |
| `forbidden` | 禁止工具/行为 |
| `toolsAllowed` | 工具白名单 |
| `fastLane` | 是否快车道 profile |

## `runtime`

| 字段 | 说明 |
|------|------|
| `llmMode` | LLM 子模式 |
| `model` | Ollama 模型（可空） |
| `toolsExecuted` | 已执行工具 |
| `harnessBlockChars` | Tier0 账本字符数 |
| `narrativePolished` | 双层润色是否成功 |
| `turnFocus` | 回合焦点 TTL |
| `composer` | 可选 composer 元数据 |

## `planVsActual`（结构化差分）

Sorted unique codes from `compute_plan_vs_actual()`:

| Code | Meaning |
|------|---------|
| `tool_not_allowed:{name}` | Executed tool not in `toolsAllowed` |
| `forbidden_tool_llm_compute` | Compute-like tool while `LLM_COMPUTE` forbidden |
| `missing_tier0_slot:{id}` | Tracked Tier0 slot present in map but empty |
| `tool_error` | Runtime tool error flag set |

Empty list `[]` means plan matched runtime for checked dimensions.

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `TAX_HARNESS_REPORT` | 1 | 响应内嵌 `harnessReport` |
| `TAX_HARNESS_DEBUG` | 0 | JSONL + INFO 日志 |
| `TAX_HARNESS_REPORT_PATH` | `/tmp/tax-harness-reports.jsonl` | JSONL 路径（本地 only） |
| `TAX_NARRATIVE_LLM_POLISH` | 1 | 叙述双层润色开关 |

## No-LLM golden run

```bash
python scripts/run_tax_harness_golden_run.py
# → RESULT: PASS
```

Uses synthetic Tier0 placeholders only — no filing DB / personal tax data.
