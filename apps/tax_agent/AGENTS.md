# Tax Agent — Agent 入口（强制阅读）

本仓库所有 **coding agent** 在改代码前必须阅读：

1. **[docs/agent-consensus-v1.md](docs/agent-consensus-v1.md)** — SSOT、禁止事项、架构共识  
2. **[docs/tax-harness-matrix.md](docs/tax-harness-matrix.md)** — Harness profile / slot 矩阵（对照 PHA）  
   2.1 **[docs/tax-chat-experience-v2.md](docs/tax-chat-experience-v2.md)** — 对话体验 v2 设计（改对话/辅导功能前必读，红线 R1–R8）  
3. **[docs/cn-fx-filing-rules-v1.md](docs/cn-fx-filing-rules-v1.md)** — 补缴/汇算汇率  
4. **[docs/cn-overseas-property-transfer-netting-v1.md](docs/cn-overseas-property-transfer-netting-v1.md)** — 年度盈亏相抵  

## 生产门槛

```bash
cd tax_agent
python scripts/run_production_selfchecks.py   # 必须通过
```

## SSOT 一句话

**申报数据表（`filing_table.py`）与测算引擎（`compute_engine.py`）对同一 dataset 的应税/税额必须一致**；财产转让 `TaxEvent.gross_amount = gain_usd`（`proceeds − cost`），卖出佣金只在「合理费用」列扣一次。

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-06-09 | P0：统一 FIFO→Event 与 filing 四列；新增 `agent-consensus-v1.md`、`run_filing_ssot_selfcheck.py`、`run_production_selfchecks.py` |
| 2026-06-09 | R003=medium 与 golden 对齐；`.cursor/rules/tax-agent-ssot.mdc` 强制共识 |
| 2026-06-09 | Harness v1：`harness_plan`、`filing_session_state`、`numerics_audit`、`tax-harness-matrix.md` |
| 2026-06-09 | Harness P1：`coverage_check`、三工具、journey/coverage API、侧栏四列申报面板、`coverage_fast` |
| 2026-06-09 | Harness P2：`session_turn_focus`、`chat_context`、`filing_narrative`/`narrative_fast`、numerics strict |
| 2026-06-09 | Harness P3：`harnessReport`、叙述润色占位符审计、侧栏辅导捷径 |
| 2026-06-09 | v1.6 多轮对话：`tax_turn_resolver`、EpisodicState、单一 chat 网关、M1–M4 自检 |
| 2026-06-09 | v1.7 P3 意图 catalog + P4 PHA 消息栈（`chat_message_stack`） |
| 2026-06-09 | v1.8 P5 clarify chips、tier0 protected SLA、券商扩展 §1.1 |
| 2026-06-10 | v1.9 对话体验 v2 设计批准：`docs/tax-chat-experience-v2.md`，C1–C7 分期、红线 R1–R8、共识 §4.3 |
| 2026-06-10 | v2.0 C1 Composer：`answer_composer`/`fact_bundle`/`citation_audit`、provenance+coverage FactBundle、`followUps` UI |
| 2026-06-10 | v2.1 C2 PolicyKB：`policy_kb.py`、12 知识卡、`policy_qa` profile、`run_policy_kb_selfcheck.py` |
| 2026-06-10 | v2.2 C3 SSE：`chat_turn_service`/`chat_sse`、`GET /tax/chat/stream`、前端流式、`run_chat_stream_selfcheck.py` |
| 2026-06-10 | v2.3 C4 NBA + 申报向导：`filing_journey_coach`、`guided_filing`、`tax_guided_session`、`run_filing_journey_coach_selfcheck.py` |
| 2026-06-10 | v2.4 C6 跨会话画像：`tax_user_profile`、`userKey`、profile 命令快车道、`run_tax_user_profile_selfcheck.py`；生产自检 23 项 |
| 2026-06-10 | v2.5 C5 叙述预算 + C7 黄金对话评测：`normalize_fallback_reason`、`evals/chat_golden_conversations`、`run_narration_budget_selfcheck.py`、`run_chat_quality_selfcheck.py`；生产自检 25 项 |
| 2026-06-11 | Phase A 体验：前端 `fact_card` + 流式冷启动；叙述默认超时 45/20/90s；`run_chat_ollama_smoke.py`（`TAX_OLLAMA_SMOKE=1`） |
| 2026-06-11 | v2.6 Phase B：`insight_fast`/`filing_narrative` FactBundle、`harnessReport` v2、`NBA` L4 独立渲染；`run_phase_b_selfcheck.py`；生产自检 26 项 |
| 2026-06-11 | v2.7 C1.4 政策 evals：`policy_qa.json` 卡内 10 + 卡外 3；`run_chat_quality_selfcheck.py` 共 22 案 |
| 2026-06-11 | v2.8 C2 画像读回 + C3 政策 citation：`GET /tax/user/profile`、`replyVerbosity`、`_ensure_policy_citations`；生产自检 28 项 |
| 2026-06-11 | v2.9 D1–D4：Ollama/browser E2E、followUps SSE+evals、人工 rubric、CI workflow；生产自检 30 项 |
| 2026-06-10 | v3.0 PR-A：共识 §1/§2.4 股息利息边界；PolicyKB `kb:cn-dividend-interest-20pct`；`policy_qa.json` +3 案 |
| 2026-06-10 | v3.1 PR-B：`income_summary.py`、分类所得 SSOT、`run_futu_income_summary_selfcheck.py`；生产自检 +1 |
| 2026-06-10 | v3.2 PR-C：侧栏/UI 股息利息分项 + 全税目合计；`run_filing_report_contract_selfcheck.py`；生产自检 32 项 |
| 2026-06-10 | v3.3 PR-D：Harness numerics/insight 纳入分类所得；`run_numerics_classified_selfcheck.py`；生产自检 33 项 |
| 2026-06-10 | v3.4 PR-E：`classified_income` 意图路由；C7 黄金对话 +3；`fact_card` 股息/利息摘要；生产自检 33 项 |
| 2026-08-31 | OSS：`apps/tax_agent` monorepo 同步；`preflight_oss_publish.py`；独立 `ollama_local`；fixture-only 自检 |
