# Tax Agent Harness Evidence Matrix（v1）

> **状态**：Active — 2026-06-09  
> **对照**：[PHA harness-evidence-matrix.md](../../personal_health_agent/docs/harness-evidence-matrix.md)  
> **实现**：`tax_agent/harness_plan.py`、`filing_session_state.py`、`numerics_audit.py`

## 1. Profile 定义

| profile | 触发条件 | Tier0 slots | forbidden | tools_allowed | 快车道 |
|---------|----------|-------------|-----------|---------------|--------|
| `casual` | 寒暄 | MASTER_ANCHOR, TASK | LLM_COMPUTE | reply_only | ✓ |
| `filing_onboarding` | 入门/材料问法且无 dataset | FILING_SCOPE, TASK | LLM_COMPUTE | request_upload | ✓ |
| `coverage_check` | 缺年/覆盖 | DATA_COVERAGE, TASK | LLM_COMPUTE | check_coverage | 视 dataset |
| `policy_explain` | 汇率/折算 | FX_PROVENANCE, TASK | LLM_COMPUTE, INVENT_FX | reply_only | ✓ |
| `policy_qa` | 政策知识库问答 | POLICY_CARDS, MASTER_ANCHOR, TASK | LLM_COMPUTE, INVENT_FX, INVENT_POLICY | reply_only | ✓ |
| `guided_filing` | 申报五步向导 | DATA_COVERAGE, FILING_SNAPSHOT, TASK | LLM_COMPUTE, INVENT_POLICY | check_coverage, compute_tax, … | ✓ |
| `compute` | 测算/税额 | FILING_SNAPSHOT, NUMERICS_MANIFEST | LLM_COMPUTE | compute_tax | — |
| `filing_coach` | 四列填表 | FILING_TABLE_AUTHORITY, FX, RISK | LLM_COMPUTE | get_filing_table | — |
| `filing_narrative` | 申报叙述润色 | FILING_TABLE_AUTHORITY, NUMERICS | LLM_COMPUTE | compose_filing_narrative | — |
| `risk_brief` | 风险/ambiguous | RISK_BRIEF, TASK | LLM_COMPUTE | get_risk_brief | — |
| `realized_vs_deferred` | 未实现/抵扣 | TAX_INSIGHT, TASK | INVENT_FX | get_tax_insight | ✓ |
| `holdings_year_end` | 年末持仓 | TAX_INSIGHT, TASK | INVENT_FX | get_tax_insight | ✓ |
| `explain_summary` | 解读结果 | FILING_SNAPSHOT, NUMERICS | LLM_COMPUTE | reply_only | — |
| `general` | 默认 | FILING_SNAPSHOT, TASK | INVENT_FX | 全工具集 | — |

## 2. Slot 说明

| slot_id | 来源 |
|---------|------|
| `MASTER_ANCHOR` | `filing_session_state._master_anchor_block` |
| `FILING_SCOPE` | 产品边界 + 免责声明 |
| `DATA_COVERAGE` | uploaded_years + ambiguous |
| `FILING_SNAPSHOT` / `FILING_TABLE_AUTHORITY` | last_filing_snapshot / filing_table API（含 `combinedRows` / `classifiedIncome`） |
| `FX_PROVENANCE` | tax_provenance / provenance_fast |
| `NUMERICS_MANIFEST` | `numerics_audit.format_numerics_manifest_block`（财产转让 + 股息/利息） |
| `RISK_BRIEF` | risk_flags + R003 notes |
| `TAX_INSIGHT` | tax_insight JSON |
| `POLICY_CARDS` | `policy_kb` 审定知识卡 answer_t0 + citations |
| `TASK` | `FilingTurnPlan.task_text` |
| `CHAT_RECALL` | Tier1，最近 8–12 轮（待 P2） |

## 3. API

| 路径 | 说明 |
|------|------|
| `GET /tax/dataset/{id}/coverage` | 材料覆盖报告 + `reply` |
| `GET /tax/dataset/{id}/journey` | 旅程阶段 + coverage + filingTable |
| `POST /tax/chat` | 响应含 `harness.profile` / `harness.journeyPhase` |

## 4. 快车道

`provenance_fast` · `policy_qa_fast` · `coverage_fast` · `insight_fast`（优先于 LLM）

## 5. 工具（`tools_schema.py`）

`check_coverage` · `get_filing_table` · `get_risk_brief` · `compute_tax` · …

## 3. 旅程阶段（journey_phase）

```text
onboarding → collecting → ready → computed → reviewing → export
```

由 `FilingSessionState.journey_phase` 维护；`build_filing_turn_plan` 可覆盖本轮 phase 推断。

## 4. 与 PHA 边界

| 共用模式 | Tax 专用 |
|----------|----------|
| TurnEvidencePlan 契约 | FilingTurnPlan |
| patient_state 投影 | FilingSessionState |
| numerics_manifest 审计 | numerics_audit |
| Tier0 字符预算 | TAX_HARNESS_TIER0_MAX_CHARS=3200 |
| — | 不 import pha.chat_service / memory_engine |

## 6. 多轮对话（v1.6）

| 模块 | 职责 |
|------|------|
| `tax_turn_resolver.py` | `TaxTurnScope`：年度解析、数据扩年、clarify |
| `session_turn_focus.py` | Episodic：`focus_tax_years[]`、`EPISODIC_BRIDGE` |
| `POST /tax/chat` | **唯一**用户自然语言网关 |

黄金用例：`run_tax_turn_resolver_selfcheck.py`（M1–M4）。

## 7. P3/P4（v1.7）

| 模块 | 职责 |
|------|------|
| `rules/tax_intent_catalog.yaml` | Profile 触发词、multi_scope、anaphora |
| `tax_intent_catalog.py` | 打分选 profile |
| `chat_message_stack.py` | `build_tax_chat_message_stack`（FILING_LEDGER user 注入） |

自检：`run_tax_intent_catalog_selfcheck.py`。

## 8. P2 模块

| 模块 | 职责 |
|------|------|
| `session_turn_focus.py` | 回合焦点 TTL（默认 3 轮），指代「那年/继续」 |
| `chat_context.py` | Tier1 `CHAT_RECALL` 关键词召回 |
| `filing_narrative.py` | F8 `compose_filing_narrative` + `narrative_fast` |
| `numerics_audit.py` | `filing_narrative` profile 默认 **strict** |

## 8. P3

| 能力 | 说明 |
|------|------|
| `harnessReport` | 每轮 chat 内嵌 `tax.harness_report/v2`（`runtime.composer` 节点） |
| 叙述双层 | 确定性草稿 → `{{NUM_n}}` 润色 → strict 审计 |
| 侧栏捷径 | 材料/四列/风险/汇率/说明/润色 |
| `GET .../narrative` | 独立拉取说明信 |

## 14. C5 Narration Budget（v2.5 · Ollama 真机默认）

| 项 | 契约 |
|----|------|
| 非流式超时 | `TAX_NARRATION_TIMEOUT_S`（默认 **45**，本地 Ollama 真机放宽；见 §9） |
| 流式首 token | `TAX_NARRATION_STREAM_FIRST_TOKEN_S`（默认 **20**） |
| 流式总预算 | `TAX_NARRATION_STREAM_TOTAL_S`（默认 **90**） |
| `fallbackReason` | `timeout` · `audit_numerics` · `audit_citation` · `llm_unavailable` · `none` |
| 长答复 | 仅 `filing_narrative` / `guided_filing` 可 >500 字（见 `narration_styles.yaml`） |
| Keep-alive | `prepare_ollama_for_tax`（`ollama_memory`） |

自检：`run_narration_budget_selfcheck.py`。

## 15. C7 Chat Quality Evals（v2.5）

| 路径 | 内容 |
|------|------|
| `evals/chat_golden_conversations/degradation.json` | LLM off / 超时 / numerics 审计降级 |
| `evals/chat_golden_conversations/cross_profile.json` | 五类 profile 路由 |
| `evals/chat_golden_conversations/guided_interrupt.json` | 向导中途插问 + 恢复 |
| `evals/chat_golden_conversations/policy_qa.json` | 政策问答卡内 10 问 + 卡外 3 问（C1.4） |

自检：`run_chat_quality_selfcheck.py`（含 C1.4 政策黄金对话）· `run_policy_narration_selfcheck.py`（C3 citation 稳定性）。

## 13. C6 User Profile（v2.4）

| 模块 | 职责 |
|------|------|
| `tax_user_profile.py` | SQLite `tax_user_profile` 表；`sync_profile_from_session`；摘要脱敏（无金额，保留 20xx 年度） |
| `try_profile_command_turn` | 「上次我算到哪了」/「忘掉我的记录」确定性快车道（`profile_memory` harness） |
| `userKey` | 前端 localStorage UUID；`POST /tax/chat` body + `GET /tax/chat/stream` query |
| `replyVerbosity` | `brief` \| `normal` \| `detailed`；随 chat 请求写入画像并影响 Composer 字数上限 |
| `GET /tax/user/profile` | 读回 `llmPreference` / `replyVerbosity`（C2，无金额） |
| `master_anchor_with_profile` | 新会话 `MASTER_ANCHOR` 附「上次进度」一行 |

自检：`run_tax_user_profile_selfcheck.py`（C6-1…C6-3）· `run_phase_c2_selfcheck.py`（C2 读回）。

## 12. C4 Journey Coach（v2.3）

| 模块 | 职责 |
|------|------|
| `filing_journey_coach.py` | NBA 尾部建议、`try_guided_filing_fast_turn` |
| `tax_guided_session.py` | SQLite 持久化 `guided_step` / `wizard_active` |

自检：`run_filing_journey_coach_selfcheck.py`（C4-1/C4-2）。

## 11. C3 SSE（v2.2）

| 模块 | 职责 |
|------|------|
| `chat_turn_service.py` | POST / SSE 共享 `resolve_chat_turn` |
| `chat_sse.py` | `iter_chat_sse_events`：meta → fact_card → delta → follow_ups → done |
| `GET /tax/chat/stream` | 与 POST 参数等价（query string） |

自检：`run_chat_stream_selfcheck.py`（C3-1…C3-3）。

## 10. C1 Composer（v2.0）

| 模块 | 职责 |
|------|------|
| `fact_bundle.py` | 快车道结构化事实 + `fallback_markdown` |
| `answer_composer.py` | 叙述 → numerics/citation 审计 → 降级 → `followUps` |
| `citation_audit.py` | 法条引用 ⊆ bundle citations |
| `rules/narration_styles.yaml` | 各 profile 叙述契约（禁止散落 prompt） |

快车道 `provenance_fast` / `coverage_fast` 产出 `FactBundle`；`finalize_turn_with_composer` 在 `/tax/chat` 与 `orchestrate_with_llm` 统一装配。

自检：`run_chat_experience_selfcheck.py`（C1-1…C1-4）。

## 9. 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `TAX_COMPOSER_ENABLED` | 1 | 0 时快车道仅用 v1 模板 |
| `TAX_NARRATION_TIMEOUT_S` | 45 | 叙述层硬超时（秒）；本地 Ollama 默认放宽 |
| `TAX_KB_ALLOW_DRAFT` | 0 | 1 时允许 draft 知识卡进入检索（仅开发） |
| `TAX_NARRATION_STREAM_FIRST_TOKEN_S` | 20 | 流式叙述首 token 超时（秒） |
| `TAX_NARRATION_STREAM_TOTAL_S` | 90 | 流式叙述总超时（秒） |
| `TAX_OLLAMA_SMOKE` | 0 | 1 时运行 `run_chat_ollama_smoke.py` 真机自检 |
| `CHAT_STREAM_TIMEOUT_MS` | 120000 | 前端 SSE fetch 上限（`static/index.html`） |
| `CHAT_POST_TIMEOUT_MS` | 120000 | 前端 POST `/tax/chat` 上限；流式 abort 后回落同路径 |
| `TAX_HARNESS_TIER0_MAX_CHARS` | 3200 | Tier0 总字符上限 |
| `TAX_MANIFEST_MAX_CHARS` | 500 | manifest 块上限 |
| `TAX_NUMERICS_AUDIT_STRICT` | 0 | 1 时未登记数字记 strict 违规 |
| `TAX_SESSION_FOCUS_TTL_TURNS` | 8 | 回合焦点保持轮数（v1.6 episodic） |
| `TAX_HARNESS_REPORT` | 1 | chat 响应内嵌 harnessReport |
| `TAX_NARRATIVE_LLM_POLISH` | 1 | 叙述 LLM 润色（双层） |
