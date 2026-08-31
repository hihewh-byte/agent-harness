# Tax Agent · Agent 共识文档 v1

> **状态**：Active — 2026-06-10  
> **受众**：所有在本仓库编码的 Cursor / CLI / 外部 Agent  
> **强制**：修改计税、FIFO、汇率、申报表、API 前**必须先读本文**；PR 不得破坏 §2 SSOT 与 §6 自检。

---

## 1. 产品边界（生产 v1）

| 支持 | 不支持 |
|------|--------|
| 中国**税务居民** | 非居民 / 身份未确认时阻断（R001/R002） |
| **富途** `Annual_Statement` xlsx | 其他券商（代码已收窄，旧自检可能仍引用） |
| 境外股票/期权 **财产转让** FIFO | 自动代申报、CRS XML、港股/A股/crypto |
| 富途税表 **股息/利息**（「股息、利息及其他收入」汇总） | 「全年其他收入」自动计税、基金/crypto |
| 补缴汇率 `cn_supplemental` | 用「办理年」或随意汇率 |

**股息/利息说明**：`income_summary.py` + `build_filing_report(..., events=)` 已提供分类所得 SSOT；侧栏/UI 分项展示（PR-C ✅）与 `combinedRows` 全税目合计。

UI 免责声明：仅供参考，不构成税务意见。

---

## 2. 单一事实来源（SSOT）— 财产转让所得

### 2.1 申报四列（个税 App 填表）

对每一**纳税年度**（按卖出日归属）：

```text
总收入(USD)     = Σ 卖出「成交金额」（毛收入，证券-交易流水）
资产原值(USD)   = Σ FIFO 匹配买入成本（买入佣金已含在买入金额）
合理费用(USD)   = Σ 卖出「总费用」（佣金/平台费）
净损益(USD)     = 总收入 − 资产原值 − 合理费用
                  = Σ (proceeds_usd − cost_basis_usd)   # 每笔 disposal 的 gain_usd
应纳税所得额    = max(0, 净损益) × 合规汇率（全年统一）
应纳税额        = 应纳税所得额 × 20%
```

**实现归属**：

| 模块 | 职责 |
|------|------|
| `cost_basis.match_fifo` | 产出 `RealizedGain`（proceeds, cost_basis, fee, gain_usd） |
| `filing_table.py` | **申报数据表**四列 + RMB 折算（**填表权威**） |
| `futu_session_fifo.realized_gains_to_events` | `TaxEvent.gross_amount = gain_usd`；`fee` 仅作合理费用元数据 |
| `compute_engine.py` | 对 `CAPITAL_GAIN` 事件 `sum(realizedGainCny)` → 必须与 filing_table 一致 |

### 2.2 禁止事项（曾导致生产事故）

1. ❌ 在 `gross_amount` 再减 `fee_usd`（佣金双重扣减 → 少应税 ~合理费用总额）  
2. ❌ 用「变动金额」作总收入填表（应使用成交金额 + 单列合理费用）  
3. ❌ 期初持仓**市值**代替买入成本（仅警告，不自动注入）  
4. ❌ 测算卡片与申报表口径分叉而不跑 `run_filing_ssot_selfcheck.py`

### 2.3 汇率

见 `docs/cn-fx-filing-rules-v1.md`。补缴：`month_key = (taxYear - 1)-12`。

### 2.4 分类所得（股息 / 利息）— SSOT 扩展（v3.0 批准，PR-B 实现）

富途 `Annual_Statement` sheet「股息、利息及其他收入」→ `TaxEvent`（`DIVIDEND` / `INTEREST`），归属 **所得年度**（parser 以 `YYYY-12-31` 标记）。

对每一**纳税年度**（股息/利息与财产转让**分税目**，不得跨类抵减）：

```text
股息收入(USD)   = Σ 全年股息（币种 USD、正金额）
利息收入(USD)   = Σ 全年利息（同上）
应纳税所得额    = max(0, 收入USD × 合规汇率)    # 股息 → cn_interest_dividend；利息 → cn_interest
应纳税额        = 应纳税所得额 × 20%
境外已纳税额    = 该税目预扣税（行内 withholding 或 WITHHOLDING_TAX 归集）
应补税额        = 应纳税额 − min(境外已纳税额, 应纳税额)
```

**实现归属（PR-B 起）**：

| 模块 | 职责 |
|------|------|
| `futu_parser.parse_futu_income_summary_rows` | 解析年度汇总 → `DIVIDEND` / `INTEREST` |
| `compute_engine.py` | `cn_interest_dividend` / `cn_interest` 行项；与规则包一致 |
| `income_summary.py` | **分类所得申报表**权威输出（非财产转让四列） |
| `filing_table.py` | 财产转让四列不变；`build_filing_report` 拼接分类所得 + `combinedRows` |

**禁止事项**：

1. ❌ 把股息/利息塞进财产转让四列（税目错误）  
2. ❌ 用财产转让净亏损抵减股息/利息应税（跨类抵减）  
3. ❌ 测算/对话只展示财产转让而隐瞒已计入 `netTaxDueCny` 的股息/利息  
4. ❌ `全年其他收入` 自动按 20% 计税（保持 `OTHER` + 人工复核）

**SSOT 自检（PR-B）**：财产转让、股息、利息**分项**对齐 `compute_engine` line_items；`grandTotal.netTaxDueCny` ≡ `compute.summary.netTaxDueCny`。

---

## 3. 跨年度 FIFO

- 同会话上传 **买入年至卖出年** 全部 `Annual_Statement`  
- `futu_session_fifo.rematch_futu_capital_gains` 合并 legs 后统一 FIFO  
- 损益按 **卖出日** 归属 `taxYear`  
- `ambiguous`（缺买入批次）→ R003，税额仍输出但须人工复核  

---

## 4. 对话 / LLM 架构

| 路径 | 何时 |
|------|------|
| `provenance_fast` / `insight_fast` 等快车道 | 事实由 Python 产出 `FactBundle`；**计税/FIFO/汇率解析不调 LLM**（R3） |
| `GroundedAnswerComposer` | 可选 LLM **叙述** FactBundle；失败/超时/审计不过 → 回落 `fallback_markdown`（v2 §4.3） |
| `compute_engine` + 规则 | 测算、申报表 |
| `orchestrate_with_llm` | 开放域对话；**不得**改写 FIFO/税额 |

快车道优先于 LLM（`api.app tax_chat`）；`llm_model=__off__` 或 Composer 关闭时快车道仅用确定性模板。

### 4.1 Harness 层（对齐 PHA，报税专用）

| 模块 | 职责 |
|------|------|
| `harness_plan.py` | `FilingTurnPlan`：profile / slots / forbidden / tools_allowed |
| `filing_session_state.py` | 旅程状态、Tier0 证据块组装 |
| `numerics_audit.py` | 回复数字 ⊆ filing_table + classifiedIncome manifest |
| `docs/tax-harness-matrix.md` | Profile × Slot 声明式矩阵 |

**禁止**：import `pha.chat_service`；LLM 路径禁止 `LLM_COMPUTE`（心算税额）。

### 4.2 多轮对话架构（v1.6 — 会话可续）

**问题**：双轨路由（前端 regex 直连 API）、年度解析硬编码（`2021–2025`）、单年焦点 TTL 过短，导致「22年汇率 → 那23年呢」断档。

**原则**（对齐 PHA Harness，报税专用）：

1. **单一聊天网关**：所有用户自然语言 → `POST /tax/chat`；快车道在服务端执行，前端不得再拦截路由。  
2. **数据驱动扩年**：多年范围来自 `uploaded_tax_years(data_quality)` 或 `FxRateProvider.list_supplemental_tax_years()`；**禁止**写死 `range(2021, 2026)`。  
3. **TaxTurnResolver**：唯一解析「本轮生效 `tax_years` + `year_source`」；`infer_provenance_years` / `harness_plan` / 前端均不得另写一套。  
4. **TaxEpisodicState**（扩展 `session_turn_focus`）：存 `focus_tax_years[]`、`last_user_message`、`last_assistant_digest`、`last_mode`；同话题续问刷新 TTL（默认 8 轮）。  
5. **澄清优于猜错**：多年已上传且无明确年度时，返回 `action=clarify` + 可选年度列表，禁止静默回退侧栏默认年。  
6. **快车道也写 episodic**：即使 `provenance_fast` 不调 LLM，也必须 `record_turn_focus` + 入库 assistant 消息，供下轮 `EPISODIC_BRIDGE` 注入。

**模块**：

| 模块 | 职责 |
|------|------|
| `tax_turn_resolver.py` | `TaxTurnScope`：年度实体、多年扩 scope、指代续焦、clarify |
| `session_turn_focus.py` | Episodic 持久化、`episodic_bridge_block`、续焦判定 |
| `chat_context.py` | `CHAT_RECALL` + episodic bridge 拼装 |
| `static/index.html` | 仅 `apiChat`；侧栏捷径发自然语言到 `/tax/chat` |

**声明式意图（P3）**：`rules/tax_intent_catalog.yaml` + `tax_intent_catalog.py`；`harness_plan` 禁止新增散落 profile regex。

**消息栈（P4）**：`chat_message_stack.build_tax_chat_message_stack` — system 仅灵魂+TASK；`FILING_LEDGER` 以 **user** 消息紧贴用户原话（仿 PHA Patient State recency）。

**可观测**：`harnessReport.turnScope` 含 `taxYears`、`yearSource`、`episodicRevived`。

**P5（v1.8）**：

- `action=clarify` + `clarifyChoices[]` → 前端年度 chip  
- `harness_tier0_assembly`：FILING_TABLE / NUMERICS protected 降级  
- 侧栏四列与 `turnFocus.taxYear` 行高亮联动  

**黄金多轮用例**（`run_tax_turn_resolver_selfcheck.py`）：

| ID | 场景 |
|----|------|
| M1 | 「22年汇率」→「那23年呢」→ 2023 补缴汇率 6.9646 |
| M2 | 「每个年度汇率」+ 上传 2021–2023 → 三年表，不含未上传年 |
| M3 | 快车道后「继续」→ `year_source=focus`，年度不变 |
| M4 | 无年份 + 多年上传 + 汇率问法 → `needs_clarification` |

### 4.3 对话体验 v2 —「税务 ChatGPT」（v1.9 — 设计已批准，实现须遵守）

**详细设计**：`docs/tax-chat-experience-v2.md`（本节为绑定摘要，冲突时以该文档为准）。

**核心公式**：每轮答复 = T0 事实块（确定性）+ LLM 叙述层（可降级）+ 证据脚注 + 3 个追问建议。
快车道从「直接返回模板」改为「产出 `FactBundle`」，最终成稿统一经 `GroundedAnswerComposer`。

**能力分期（实施顺序强约束）**：

| 期 | 能力 | 关键模块（规划） |
|----|------|------|
| C1 ✅ | 落地生成：叙述层 + numerics/citation 双审计 + followUps | `answer_composer.py` · `fact_bundle.py` · `rules/narration_styles.yaml` · `run_chat_experience_selfcheck.py` |
| C2 ✅ | PolicyKB 政策知识库 + `policy_qa` profile（无 dataset 可答） | `policy_kb.py` · `rules/knowledge/cn_overseas_income/*.yaml` |
| C3 ✅ | SSE 流式：fact_card 先发、叙述 delta 后补 | `chat_turn_service` · `chat_sse` · `GET /tax/chat/stream` |
| C4 ✅ | 主动辅导 NBA + `guided_filing` 向导 | `filing_journey_coach.py` · `tax_guided_session.py` |
| C5 ✅ | 模型策略与超时预算（超时即回落模板） | `answer_composer` · `normalize_fallback_reason` · `run_narration_budget_selfcheck.py` |
| C6 ✅ | 跨会话用户画像（本地、无金额、可一键清除） | `tax_user_profile.py` · `userKey` · `run_tax_user_profile_selfcheck.py` |
| C7 ✅ | 对话质量评测套件（JSON 黄金对话 + 降级回归） | `evals/chat_golden_conversations/` · `run_chat_quality_selfcheck.py` |

**红线 R1–R8**（详见设计文档 §0，coding agent 不得违反）：数字 ⊆ numerics_manifest；
法条必须引用知识卡 citation（新增 `citation_audit` 与 `INVENT_POLICY` forbidden）；
LLM 不参与计税；单一网关；catalog 声明式意图；叙述失败静默回落模板；
不破坏既有生产自检；免责声明不得被润色删除。

---

## 5. 变更流程（Agent 必遵）

1. 读本文 + 相关 spec（`cn-us-equity-calculation-spec-v1.md`、`cn-fx-filing-rules-v1.md`）  
2. 改代码  
3. 运行 `python scripts/run_production_selfchecks.py`（必须通过）  
4. 若改 SSOT：更新本文版本号与 §2，并在 `AGENTS.md` 变更日志记一行  

---

## 6. 生产自检套件

```bash
python scripts/run_production_selfchecks.py
```

必含：`run_filing_ssot_selfcheck.py`（compute ≡ filing_table）、golden、FIFO、汇率、富途解析。

全量 `run_all_selfchecks.py` 含**已弃用**多券商脚本，**不作为**生产门槛。

---

## 7. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-06-09 | 初版：四列 SSOT、修复佣金双重扣减、生产自检套件 |
| v1.1 | 2026-06-09 | R003 定为 medium（出数+警告）；golden 与实现对齐 |
| v1.2 | 2026-06-09 | Harness 骨架：FilingTurnPlan、FilingSessionState、numerics_audit；`tax-harness-matrix.md` |
| v1.3 | 2026-06-09 | P1：`check_coverage`/`get_filing_table`/`get_risk_brief`、coverage_fast、journey API、侧栏四列申报面板 |
| v1.4 | 2026-06-09 | P2：`session_turn_focus`、`chat_context`、`filing_narrative`/`narrative_fast`、numerics strict |
| v1.5 | 2026-06-09 | P3：`harnessReport` v1、叙述双层润色、侧栏辅导捷径、`GET /narrative` |
| v1.6 | 2026-06-09 | 多轮对话：`TaxTurnResolver`、EpisodicState、单一 `/tax/chat` 网关、去硬编码年份、clarify |
| v1.7 | 2026-06-09 | P3 `tax_intent_catalog.yaml`；P4 `build_tax_chat_message_stack`（PHA 消息栈） |
| v1.8 | 2026-06-09 | P5 clarify chips、`harness_tier0_assembly`、四列 turnFocus 高亮；§1.1 券商扩展路径 |
| v1.9 | 2026-06-10 | §4.3 对话体验 v2 设计批准：`docs/tax-chat-experience-v2.md`，C1–C7 分期与红线 R1–R8 |
| v2.0 | 2026-06-10 | C1 落地生成：`GroundedAnswerComposer`、`FactBundle`、快车道经 Composer、`followUps` chips |
| v2.1 | 2026-06-10 | C2 PolicyKB：12 张审定知识卡、`policy_qa` 快车道、超范围诚实拒答 |
| v2.2 | 2026-06-10 | C3 SSE：`/tax/chat/stream`、共享 `chat_turn_service`、前端流式 |
| v2.3 | 2026-06-10 | C4 NBA + `guided_filing` 五步向导、`tax_guided_session`；生产自检 22 项 |
| v2.4 | 2026-06-10 | C6 跨会话画像：`tax_user_profile` 表、`userKey`、profile 命令快车道、`MASTER_ANCHOR` 进度行；生产自检 23 项 |
| v2.5 | 2026-06-10 | C5 叙述预算 + `fallbackReason` 契约；C7 `evals/chat_golden_conversations` + `run_chat_quality_selfcheck.py`；生产自检 25 项 |
| v2.6 | 2026-06-11 | 体验达标 Phase A/B：Ollama 叙述超时 45/20/90s；`insight_fast`/`filing_narrative` FactBundle；`harnessReport` v2；NBA L4 独立渲染；生产自检 26 项 |
| v2.7 | 2026-06-11 | 体验达标 C1.4：政策问答黄金 evals（10+3）`policy_qa.json`；共识 §4 快车道/Composer 分工脚注 |
| v2.8 | 2026-06-11 | 体验达标 C2 画像读回（`llmPreference`/`replyVerbosity`）+ C3 政策 citation 稳定性；生产自检 28 项 |
| v2.9 | 2026-06-11 | D1–D4：真机 E2E、followUps 黄金用例、人工 rubric、GitHub Actions production-selfcheck；生产自检 30 项 |
| v3.0 | 2026-06-10 | PR-A：§1 纳入富途股息/利息；新增 §2.4 分类所得 SSOT 规格；PolicyKB + `policy_qa` evals |
| v3.1 | 2026-06-10 | PR-B：`income_summary.py`、`build_filing_report` 分类所得 + `combinedRows`；分项 SSOT 自检；生产自检 31 项 |
| v3.2 | 2026-06-10 | PR-C：侧栏申报表分项 UI、测算卡片全税目拆项、`run_filing_report_contract_selfcheck.py`；生产自检 32 项 |
| v3.3 | 2026-06-10 | PR-D：`insight_fast`/`filing_narrative` 含分类所得；`numerics_audit` manifest 含 `classifiedIncome`；生产自检 33 项 |
| v3.4 | 2026-06-10 | PR-E：`classified_income` 意图（有 dataset 时数据问法）；C7 `classified_income.json`；`fact_card` 展示股息/利息；生产自检 33 项（C7 +3 案） |

### 1.1 券商 / 机构文档扩展（架构能力 vs 生产边界）

**生产 v1 仅开放富途**（`api/app.py` 上传与 `_run_compute` 均校验 `broker_futu_v1`）。

**引擎层已具备扩展骨架**（换券商 ≠ 重写计税 SSOT）：

| 层 | 模块 | 可复用性 |
|----|------|----------|
| 事件模型 | `TaxEvent` / `EventType` | 通用 |
| FIFO / 四列 | `cost_basis` · `filing_table` · `compute_engine` | **与券商无关** |
| 汇率 / 规则 | `fx_rates.yaml` · `rule_registry` | 与券商无关 |
| 列映射 | `mappings/broker_*.yaml` | 已有 Schwab/Fidelity/IBKR/Tiger/Vanguard 草案 |
| 专用解析器 | `parser/schwab_parser.py` 等 | 历史/实验代码，**未接生产上传** |
| 富途税表 | `broker_parser.py` + `futu_session_fifo` | 当前唯一生产路径 |

**接入新券商的最小步骤**：

1. 新增或完善 `mappings/broker_<name>_v1.yaml`（表头检测、买卖/费用/日期列映射）  
2. 实现 `parse_bytes` → 统一产出 `TaxEvent` + `data_quality`（含 `taxPackages` 年度列表）  
3. 若需跨年 FIFO：与富途相同，合并多年度 legs 后 `match_fifo`  
4. 放开 `api/app.py` 的 `FUTU_TEMPLATE` 硬门禁，按 `broker_template_id` 路由解析器  
5. 黄金用例：`run_*_parser_selfcheck` + `run_filing_ssot_selfcheck` + 该券商样例文件  

**不能自动保证的**：各机构 PDF/非标准 xlsx、期权行权样式、RSU/ESPP（属工资薪金）、基金/债券等非财产转让所得——需单独产品范围与解析规则。

**对话/Harness 层**：与券商无关；换券商后 `TaxTurnResolver`、intent catalog、消息栈无需改动。

### R003（ambiguous 成本）

**等级 medium**：仍输出税额与申报表，notes 要求补全年份税表；**不**列入 `_BLOCKING_HIGH_RULES`。
