# Tax Chat Experience v2 — 中国居民境外收入「税务 ChatGPT」详细设计

> **状态**：Approved Design — 2026-06-10（共识 v1.9 §4.3 绑定本文）  
> **受众**：所有在本仓库编码的 Cursor / CLI / 外部 coding agent，**实现对话/辅导相关功能前必读并遵守**  
> **上游契约**：`agent-consensus-v1.md` §2 SSOT、§4.1–4.2 Harness/多轮、`tax-harness-matrix.md`  
> **目标**：在不牺牲「数字确定性」的前提下，把对话体验从「带智能问答的计算器」（6.5/10）提升到「境外收入税务 ChatGPT」（≥8.5/10）

---

## 0. 设计哲学（不可妥协）

```text
ChatGPT 的体验  =  自然语言理解 + 连贯叙述 + 主动引导 + 流式即时感
税务产品的底线  =  数字 100% 来自 SSOT，法条 100% 来自知识库，禁止幻觉
```

**核心公式**：

```text
每轮答复 = T0 事实块（确定性，Python 产出）
         + 叙述层（LLM 把事实讲成人话，可选、可降级）
         + 证据脚注（数据来源 / 法条出处 / 口径标注）
         + 追问建议（3 个 follow-up chips）
```

**v1 的问题不是「快车道太多」，而是「快车道直接把模板甩给用户」**。v2 保留全部快车道的事实生产，
但把「最终成稿」交给叙述层 —— LLM 在场时讲人话，LLM 缺席时回落模板。这就是
**Grounded Generation（落地生成）**：与 PHA「Patient State 账本 + 临床叙述」同构。

### 红线（任何 coding agent 不得违反）

| # | 红线 | 校验机制 |
|---|------|----------|
| R1 | 答复中任何金额/汇率/税额必须 ⊆ `numerics_manifest`（T0） | `numerics_audit` strict，违规即回落模板 |
| R2 | 法条/政策表述必须引用 `rules/knowledge/` 知识卡 ID，禁止 LLM 自由发挥法条原文 | 叙述层 prompt 契约 + `policy_citation_audit`（新） |
| R3 | LLM 不参与计税、FIFO、汇率解析（`LLM_COMPUTE` / `INVENT_FX_RATE` forbidden 继续生效） | Harness forbidden 槽 |
| R4 | 单一网关 `POST /tax/chat`（含流式变体 `/tax/chat/stream`）；前端不得新增意图拦截 | 共识 v1.6 既有规则 |
| R5 | 意图扩展只改 `tax_intent_catalog.yaml` + 黄金用例；禁止散落 regex | 共识 v1.7 既有规则 |
| R6 | 叙述层失败/超时/审计不过 → **静默回落确定性模板**，不向用户报错 | composer 降级链 |
| R7 | 不破坏既有 18 项生产自检；新能力必须带自检并入 production suite | `run_production_selfchecks.py` |
| R8 | 免责声明（仅供参考，不构成税务意见）在叙述层不得被润色删除 | narrative freeze 既有机制扩展 |

---

## 1. 与 v1 的差距分析（为什么现在不像 ChatGPT）

| 维度 | v1 现状 | ChatGPT 体验基准 | 差距 |
|------|---------|------------------|------|
| 答复文体 | 快车道 = Markdown 模板（`## 2022 年度汇率依据（申报口径 T0）`） | 自然段落，先结论后细节，口语化 | **大** |
| 通用政策问答 | 无 dataset 时几乎答不了「境外收入要不要报税」 | 任何相关问题都有可靠回答 | **大** |
| 即时感 | 同步 JSON，LLM 路径 45s 超时 | 流式逐字输出 | **大** |
| 主动性 | 用户问什么答什么 | 答完主动给「下一步建议」 | 中 |
| 连贯性 | episodic（8 轮 TTL）+ 续焦，已较好 | 全程上下文 | 小（v1.6 已补） |
| 个性化 | 单会话内记忆 | 跨会话记住用户身份/进度 | 中 |
| 数字可靠 | **强于 ChatGPT**（SSOT + 审计） | 常编数字 | v1 反超，必须保持 |

结论：v2 的主战场是 **文体（C1）、知识（C2）、即时感（C3）、主动性（C4）、个性化（C5）**，
而不是重做意图/记忆（v1.6–1.8 已达标）。

---

## 2. 总体架构（v2 目标态）

```text
POST /tax/chat  ·  GET /tax/chat/stream (SSE)
        │
        ▼
┌─────────────────────────────────────────────────┐
│ TaxTurnResolver（v1.6 不变）                      │
│  年度 scope · clarify · episodic 续焦             │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ IntentCatalog → FilingTurnPlan（v1.7 不变）       │
│  新增 profile：policy_qa · guided_filing          │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ FactEngine（= v1 快车道集合，输出结构化事实）        │
│  provenance · coverage · insight · filing_table  │
│  + PolicyKB 检索（新）                            │
│  产出：FactBundle（JSON，含 numerics + citations）│
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ GroundedAnswerComposer（新，v2 核心）              │
│  L1 叙述层：LLM 把 FactBundle 讲成自然中文          │
│  L2 审计层：numerics strict + citation audit      │
│  L3 降级链：审计失败/LLM 缺席 → 确定性模板           │
│  L4 增补层：follow-up chips + next-best-action    │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ 输出装配：reply(流式) + factCard + citations      │
│ + followUps + harnessReport + episodic 写入       │
└─────────────────────────────────────────────────┘
```

**关键变化**：快车道从「直接返回 reply」改为「返回 FactBundle」；
所有 profile 的最终文案统一经 Composer。LLM 从「兜底路径」升格为「叙述主力」，
但数字与法条永远不出自它。

---

## 3. C1 — GroundedAnswerComposer（叙述层，最高优先级）

### 3.1 模块

| 模块（建议路径） | 职责 |
|------|------|
| `tax_agent/answer_composer.py` | Composer 主体：L1–L4 流水线 |
| `tax_agent/fact_bundle.py` | `FactBundle` 数据类：facts / numerics / citations / fallback_markdown |
| `rules/narration_styles.yaml` | 各 profile 的叙述风格契约（声明式，禁止散落 prompt 字符串） |

### 3.2 FactBundle 契约

每个快车道/工具改造为产出：

```text
FactBundle:
  profile:            policy_explain | coverage_check | ...
  facts:              结构化 JSON（如 {taxYear, monthKey, rate, ruleLabel, anchorExplanation}）
  numerics:           允许出现在叙述中的数字白名单（并入 numerics_manifest）
  citations:          [{id: "kb:cn-iit-ir-art32", label: "个税法实施条例第三十二条"}]
  fallback_markdown:  v1 既有模板（降级用，禁止删除）
  tier:               T0 | T1（口径标注，叙述层必须保留）
```

### 3.3 叙述层 Prompt 契约（写入 `narration_styles.yaml`）

- 输入：FactBundle.facts + 用户原话 + episodic bridge
- 要求：
  1. **先结论后依据**：第一句直接回答用户问题（如「2022 年补缴用的汇率是 6.3757」）
  2. 数字必须逐字引用 facts 中的值，**不得换算、四舍五入、推导新数字**
  3. 法条只能写「依据【citation label】」，不得展开自拟条文
  4. 口语化、分段、≤300 字（汇率类）/ ≤500 字（填表辅导类）
  5. 结尾保留 tier 标注与免责声明（若 facts.tier == T1 必须写明「辅助口径，不计入申报」）
- 输出：纯 Markdown 叙述，不含 JSON

### 3.4 审计与降级链（L2/L3）

```text
LLM 叙述 → numerics_audit(strict) → citation_audit → 通过 → 发布
                  │                      │
                  └──── 任一失败 ─────────┴→ fallback_markdown（v1 模板）
LLM 超时（预算见 §7）/ 不可用 ──────────────→ fallback_markdown
```

- `citation_audit`（新）：叙述中出现的「法条/文号/政策名」必须能映射回 citations 列表，否则判违规
- 审计结果写入 `harnessReport.runtime.composer`：`{narrated: bool, fallbackReason, auditMs}`

### 3.5 追问建议（L4）

- 每轮答复附 `followUps: [string × 3]`，由 Composer 按 profile + journey_phase 确定性生成（模板池，不靠 LLM）
- 示例（policy_explain 后）：「看 2023 年的汇率」「这个汇率对应的税额是多少」「生成申报数据表」
- 前端渲染为 chips，点击即发该文本到 `/tax/chat`（复用 clarify chips 机制）

### 3.6 验收（黄金用例，须入 production suite）

| ID | 场景 | 断言 |
|----|------|------|
| C1-1 | LLM 在场问「22年汇率怎么定」 | 答复为自然中文（非 `##` 模板开头）、含 6.3757、含 citation、numerics 审计通过 |
| C1-2 | LLM 关闭同问 | 回落 v1 模板，内容不缺失 |
| C1-3 | 叙述层注入假数字（mock） | 审计拦截，最终输出 = fallback |
| C1-4 | 每轮答复 | `followUps` 长度 == 3 且均为合法可发送文本 |

---

## 4. C2 — PolicyKB 政策知识库与 `policy_qa` profile

### 4.1 问题

用户问「境外收入到底要不要申报」「什么时候汇算清缴」「会有滞纳金吗」——v1 无 dataset 时基本失语。
这是「税务 ChatGPT」与「计算器」的最大体感差。

### 4.2 知识卡片库

| 项 | 设计 |
|----|------|
| 位置 | `rules/knowledge/cn_overseas_income/*.yaml`（与 fx/rules 同走快照发布流水线） |
| 卡片结构 | `id` · `title_zh` · `question_patterns`（触发词，进 intent catalog）· `answer_t0`（审定答案，含数字则登记 numerics）· `citations`（法条/公告原文出处+链接）· `effective_date` · `review_status`（draft/reviewed） |
| 首批卡片（≥12 张） | 申报义务与范围 · 汇算清缴时间窗 · 财产转让 20% 税率 · 境外已缴税抵免 · 补缴滞纳金口径 · CRS 与数据来源 · 财产转让 vs 工资薪金（RSU 边界）· 盈亏相抵（年度内）· 亏损不可跨年结转 · 申报渠道（个税 App/办税厅）· 汇率规则总述 · 本产品能做什么/不能做什么 |
| 红线 | **只有 `review_status: reviewed` 的卡片可进入生产答复**；draft 卡片仅在 `TAX_KB_ALLOW_DRAFT=1` 开发环境可见 |

### 4.3 `policy_qa` profile（新增至 intent catalog 与 harness matrix）

| 项 | 设计 |
|----|------|
| 触发 | 知识卡 `question_patterns` 命中且无更高分 profile；**不要求 dataset** |
| 检索 | 关键词打分（沿用 catalog 打分器）选 top-2 卡片；不引入向量库（v2 阶段保持零额外依赖） |
| Tier0 slots | `POLICY_CARDS`（卡片 answer_t0 + citations）+ `MASTER_ANCHOR` + `TASK` |
| 叙述 | 经 Composer：LLM 用卡片内容作答，citation_audit 强制 |
| 无命中 | 诚实回答「该问题超出当前知识库范围」，给出已覆盖主题列表 —— **禁止 LLM 自由发挥**|
| forbidden | `LLM_COMPUTE` · `INVENT_FX_RATE` · `INVENT_POLICY`（新 forbidden 标记） |

### 4.4 验收

| ID | 场景 | 断言 |
|----|------|------|
| C2-1 | 无 dataset 问「境外股票赚的钱要交税吗」 | 命中 policy_qa，引用申报义务卡，含 citation |
| C2-2 | 问知识库外问题（如「法国税怎么算」） | 明确说超范围，不编造 |
| C2-3 | draft 卡片 | 生产配置下不可被引用 |

---

## 5. C3 — 流式输出（SSE）

| 项 | 设计 |
|----|------|
| 端点 | `GET /tax/chat/stream`（SSE）；请求参数与 `POST /tax/chat` 等价；**两端点共用同一 orchestrator，禁止 fork 逻辑** |
| 事件序列 | `meta`（harness profile/turnScope，先发）→ `fact_card`（T0 事实卡 JSON，快车道完成即发，**用户先看到可靠数字**）→ `delta`（叙述层逐 token）→ `follow_ups` → `done`（harnessReport） |
| 体感目标 | fact_card ≤ 1.5s 内可见（快车道本来就快）；叙述层慢也不阻塞核心信息 |
| 降级 | LLM 缺席：fact_card 后直接 `done`，fallback_markdown 作为 reply |
| 前端 | composer 提交走 SSE；保留非流式 POST 兼容自检与脚本调用 |
| 超时 | 叙述层流式预算见 §7；超时即终止 delta、保留已出内容 + 模板补尾 |

**验收**：C3-1 流式端到端事件顺序正确；C3-2 LLM 关闭时 fact_card 路径完整；C3-3 非流式 POST 行为与 v1 兼容（既有自检不破）。

---

## 6. C4 — 主动辅导（Proactive Coach + 申报向导）

### 6.1 Next-Best-Action（NBA）

由 `journey_phase` + coverage + 风险标志确定性推导（模板池，不靠 LLM）：

| 触发时机 | 主动话术（系统消息或答复尾部） |
|----------|------|
| 上传完成且缺买入年 | 「检测到 2023 卖出含 2022 买入批次，建议补传 2022 税表，否则税额可能偏高」 |
| 上传完成且材料齐 | 「材料覆盖完整，可以直接说『测算 2023 年税额』」 |
| 测算完成有 R003 | 「有 N 笔成本不确定（ambiguous），建议先看风险清单再填表」 |
| 测算完成无风险 | 「下一步：生成申报数据表，对照个税 App 四列填写」 |
| 已生成申报表 | 「需要我写一份申报情况说明吗？」 |

实现归属：`filing_journey_coach.py`（新）；输出并入 Composer L4，与 followUps 共用渲染。

### 6.2 申报向导模式（guided_filing profile）

- 触发：「带我申报」「一步步教我」「开始申报流程」
- 行为：状态机推进 `collecting → ready → computed → reviewing → export`，每步一条主消息 + 完成判定（基于 session 状态，非用户口头确认）
- 每步可随时打断问其他问题（episodic 保持向导进度，TTL 不清除向导状态）
- 向导状态持久化于 `FilingSessionState`（新增 `guided_step` 字段），跨轮可恢复

**验收**：C4-1 上传缺年 → 答复尾部出现补传建议；C4-2 guided_filing 五步可走通且中途插问不丢进度。

---

## 7. C5 — 模型策略与性能预算（体验稳定性）

| 项 | 契约 |
|----|------|
| 叙述层模型 | 沿用 `llm_model_resolver`；推荐 qwen2.5:7b 级别；模型解析失败不报错、直接走模板 |
| 预算 | 叙述层（非流式）：默认 **45s** 硬超时；流式：首 token **20s**、总 **90s**（本地 Ollama 真机默认，见 `tax-harness-matrix.md` §9/§14）；超时回落模板 |
| Keep-alive | 会话活跃期间保持模型加载（沿用 `ollama_memory` 机制）；冷启动惩罚不计入预算（首轮提示「模型加载中」） |
| 长答复 | 仅 `filing_narrative` / `guided_filing` 允许 >500 字 |
| 失败可观测 | `harnessReport.runtime.composer.fallbackReason` ∈ {timeout, audit_numerics, audit_citation, llm_unavailable, none} |

---

## 8. C6 — 跨会话用户画像（轻量，隐私优先）

| 项 | 设计 |
|----|------|
| 存储 | SQLite 表 `tax_user_profile`（本地单机，沿用现有 DB；不引入云端） |
| 字段 | 居民身份确认结果 · 已处理年度及状态（未传/已传/已测算/已申报标记）· 偏好（LLM 开关、答复详简）· 最近会话摘要（≤500 字，确定性生成） |
| 注入 | 新会话首轮 `MASTER_ANCHOR` 附「上次进度」一行；用户可说「忘掉我的记录」清除（提供确定性指令，不靠 LLM 判断删除） |
| 红线 | 不存税表原始数据于画像表；摘要中不含具体金额（防泄漏 + 防 stale 数字污染 numerics 审计） |

**验收**：C6-1 跨会话「上次我算到哪了」可答；C6-2 清除指令生效；C6-3 画像摘要不含金额数字。

---

## 9. 评测体系（对话质量回归，新增生产门槛）

新增 `scripts/run_chat_experience_selfcheck.py`（C1–C4 黄金用例）+ `evals/chat_golden_conversations/*.json`：

| 集合 | 内容 | 通过标准 |
|------|------|----------|
| 多轮连贯 | M1–M4（既有）+ 向导中途插问 + 跨 profile 切换 ×5 | 年度/话题不漂移 |
| 落地生成 | C1-1…C1-4 | 审计 0 泄漏 |
| 政策问答 | 知识卡内 10 问 + 卡外 3 问 | 卡内全中、卡外全部诚实拒答 |
| 主动辅导 | C4-1/C4-2 | NBA 触发正确 |
| 降级 | LLM off / 超时注入 | 全部回落模板、无报错文案 |

主观体验另设人工 rubric（自然度/有用性/信任感 1–5 分），每次大版本人工抽测 10 段对话，目标均分 ≥4。

---

## 10. 实施顺序与依赖（强约束）

```text
C1 Composer（叙述层+审计+followUps）          ← 最高优先级，其他全部依赖它
 ├─ C2 PolicyKB + policy_qa                  ← 依赖 Composer 的 citation_audit
 ├─ C3 SSE 流式                              ← 依赖 Composer 的分层输出
 └─ C4 Proactive Coach / guided_filing       ← 依赖 Composer L4
C5 模型策略预算                               ← 与 C1 同步落地（超时即模板）
C6 用户画像                                   ← 最后，独立
C7 评测套件                                   ← 每阶段交付时同步补，不得后补
```

**每阶段交付定义（DoD）**：代码 + 黄金用例入 production suite + 本文对应小节标记「✅ 已实现」+ `AGENTS.md` 变更日志一行。

---

## 12. 实现状态

| 期 | 状态 | 说明 |
|----|------|------|
| C1 | ✅ 2026-06-10 | `answer_composer` · `fact_bundle` · `citation_audit` · provenance/coverage FactBundle · followUps chips |
| C2 | ✅ 2026-06-10 | `policy_kb.py` · 12 张审定知识卡 · `policy_qa` profile/fast lane · `run_policy_kb_selfcheck.py` |
| C3 | ✅ 2026-06-10 | `GET /tax/chat/stream` · `chat_turn_service` · `chat_sse` · 前端 fetch SSE |
| C4 | ✅ 2026-06-10 | `filing_journey_coach` · NBA 尾部建议 · `guided_filing` 五步向导 · `tax_guided_session` |
| C5 | ✅ 2026-06-10 | 叙述超时 env · 流式首 token/总预算 · `normalize_fallback_reason` · 长答复仅 `filing_narrative`/`guided_filing` · `run_narration_budget_selfcheck.py` |
| C6 | ✅ 2026-06-10 | `tax_user_profile.py` · `userKey`（localStorage）· profile 命令快车道 · `MASTER_ANCHOR` 进度行 · `run_tax_user_profile_selfcheck.py` |
| C7 | ✅ 2026-06-11 | `evals/chat_golden_conversations/*.json` · `run_chat_quality_selfcheck.py`（降级/跨 profile/向导/政策 10+3） |

### 体验达标进度

| 项 | 状态 | 说明 |
|----|------|------|
| A1 fact_card UI | ✅ 2026-06-11 | 前端渲染 SSE `fact_card`、冷启动「模型加载中」、回落保留事实卡 |
| A2 叙述预算 | ✅ 2026-06-11 | 默认 45s/20s/90s；`merged_numerics` 含两位年度；`run_chat_ollama_smoke.py` |
| B1 FactBundle 补齐 | ✅ 2026-06-11 | `insight_fast` / `filing_narrative` → `build_*_fact_bundle` + Composer |
| B2 harnessReport v2 | ✅ 2026-06-11 | `tax.harness_report/v2` · `runtime.composer` · 顶层 `numericsAudit` 保留 |
| B3 NBA → Composer L4 | ✅ 2026-06-11 | `resolve_turn_nba` · 前端 `nba-hint` · 不再拼接 reply 尾部 |
| C1.4 政策 evals | ✅ 2026-06-11 | `evals/chat_golden_conversations/policy_qa.json`（卡内 10 + 卡外 3）· `run_chat_quality_selfcheck.py` |
| C2 画像读回 | ✅ 2026-06-11 | `resolve_profile_preferences` · `GET /tax/user/profile` · 侧栏答复详简 · Composer `replyVerbosity` |
| C3 政策叙述稳定性 | ✅ 2026-06-11 | `_ensure_policy_citations` · citation 归一化审计 · `run_policy_narration_selfcheck.py` · Ollama smoke 要求 cite 通过 |
| D1 真机叙述 | ✅ 2026-06-11 | `numericsRetried` 一次重试 · `run_chat_ollama_smoke.py` · `run_browser_e2e_verify.py` |
| D2 followUps UI | ✅ 2026-06-11 | SSE `follow_ups` 事件 · `follow_ups.json` · 浏览器 chips×3 验证 |
| D3 人工 rubric | ✅ 2026-06-11 | `evals/chat_manual_rubric.json`（10 段）· `run_manual_rubric_selfcheck.py` |
| D4 发布工程 | ✅ 2026-06-11 | `.github/workflows/production-selfcheck.yml` · `docs/DEPLOYMENT.md` |

---

## 11. 对既有契约的修订汇总（coding agent 检查清单）

1. 快车道函数（`try_*_fast_turn`）逐步改为产出 `FactBundle`；**过渡期内必须保留 fallback_markdown 与现行为等价**  
2. `tax-harness-matrix.md` 增加 `policy_qa`、`guided_filing` 两个 profile 行与 `POLICY_CARDS` slot  
3. `tax_intent_catalog.yaml` 新增上述 profile 触发词；继续禁止散落 regex  
4. `harnessReport` schema 升级为 `tax.harness_report/v2`（新增 `composer` 节点），旧字段不删  
5. 新环境变量统一登记到 harness matrix §9  
6. 任何阶段不得引入对 `pha.chat_service` 的 import（仅可对照其设计）  
7. 违反 §0 红线的 PR 视为破坏共识，必须回退
