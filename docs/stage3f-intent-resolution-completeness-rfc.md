# Stage 3F — 意图解析完整性 RFC

> **Language / 语言**：[English](stage3f-intent-resolution-completeness-rfc.en.md) · 中文（本文）

> **文件名**：`stage3f-intent-resolution-completeness-rfc.md`  
> **版本**：v0.1（2026-06-17）  
> **状态**：✅ **Approved · 架构完整性锁定版** · §15 为 v1.14 增补（M1-P17 / P18 已编码）  
> **定位**：Stage 3C（多轮连贯性）之后的 **统一产品开发波次** — 补齐「开放意图 → 证据组装」链路，**非**单条 E2E / 单指标 corner case 补丁  
> **上游（只读）**：[`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) · [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) · [`pha-pm-constitution.md`](pha-pm-constitution.md)  
> **下游编码**：`health_turn_resolver` · `intent_gates` · `harness_plan` · `health_intent_catalog` · `clarify_turns` · `harness_report`

---

## 0. 执行口令与共识绑定

任何在本 RFC 下编码的 agent，开工前须：

1. 阅读本文档全文 + [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) §2 宪法对齐  
2. 阅读 [`docs/pha-pm-constitution.md`](pha-pm-constitution.md) 第一～三条  
3. 首条实施回复包含：`CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read`

**禁止**：

- 为通过单条真机剧本（含「身体年龄」类合成问句）在 Python 内新增 phrase if-else  
- 让子 agent / Shadow / LLM 直接选定 `TurnEvidencePlan` 或绕过 Numerics 审计  
- 以「提高 Tier0 上限」作为开放意图的唯一修复  

**Telemetry 驱动声明**（宪法第二条）：本 RFC 的立项依据来自 Harness 遥测中反复出现的 **`profile=lifestyle` + `manifest_n=0` + 用户后续单指标逐轮解锁** 模式（见 [`telemetry-review-playbook.md`](telemetry-review-playbook.md) §4 扩展），属于 **路由完整性缺口**，不是某一指标的 SQL 读不到。

---

## 1. 问题陈述（架构完整性）

### 1.1 已交付能力（Stage 3C-α～ε）

| 能力 | 状态 | 覆盖范围 |
|------|------|----------|
| `HealthTurnResolver` + `turnScope` | ✅ | 指标 / 年 / 窗 / 指代续焦 |
| 全 profile episodic + `EPISODIC_BRIDGE` | ✅ | 单会话内 **profile 车道** 续焦 |
| `health_intent_catalog` 声明式继承 | ✅ | 弱问句、`session_anchor` |
| `clarify` 短路 + chips | ✅ | **`lab_year`** 等化验歧义 |
| `GroundedAnswerComposer` + fact_card | ✅ | 叙述层与 Manifest 同构 |

### 1.2 仍缺的架构块（完整性缺口）

PHA 当前管线在 **「用户目标已表达、证据域未点名」** 时存在系统性空白：

```text
用户句（开放合成目标，无具体指标 token）
  → SchemaIntentRouter：lab/wearable/supplement 打分全 0
  → 默认 lifestyle（最轻车道）
  → Tier0 ≈ TASK only；Manifest / 90d / tools 关闭
  → LLM 在 Soul 契约下输出「缺乏基线 / 请提供报告」
  → 用户被迫逐个点名指标，每轮仅解锁单域 Manifest
  → episodic 续的是 focus_profile（单车道），无法重建多域联合视图
```

这不是某一功能的 bug，而是 **意图解析栈缺少三个正交维度**：

| 维度 | 3C 已覆盖 | 3F 需补齐 |
|------|-----------|-----------|
| **Scope**（哪年 / 哪窗 / 哪指标） | ✅ Resolver | 延续 |
| **Profile**（哪条 Harness 车道） | ✅ SchemaRouter | 需 **Arbiter** 在 under-specified 时升舱 |
| **Goal**（合成目标 vs 单指标查询） | ❌ | 需 **GoalClassifier** + **focus_goal** |

### 1.3 本 RFC 要回答什么

在 **不破坏 A+ 宪法** 与 **Approved 3C RFC** 的前提下，形成 **Stage 3F 统一产品开发安排**，使 PHA 对「无限说法、有限组装模式」具备可声明、可观测、可回归的完整链路。

### 1.4 非目标

- ❌ 为「身体年龄」「抗衰」等单独写 Python 分支  
- ❌ LLM 主控 ReAct 自主拉数  
- ❌ 跨会话长期用户画像（仍属远期 Backlog）  
- ❌ 修改 Numerics 审计算法本体  
- ❌ 在本 RFC 内重写 Soul Prompt 全文（仅声明 **goal-aware 叙述契约** 原则）

---

## 2. 与既有文档的关系

```text
pha-pm-constitution.md          上位法
harness-consensus-opus48          硬约束 + P0/P1/P2
stage3c-multi-turn-episodic-focus-rfc   多轮 scope / episodic / clarify(lab_year)
stage3f-intent-resolution-completeness  ← 本 RFC：goal + arbiter + 多域组装完整性
pha-architecture-evolution-v2.3   Stage 1～3C 总蓝图；3F 写入 §8 路线图
metadata-catalog-v2.3             existence_probe 复用，不新建第二探针
harness-subagent-protocol-v1      Intent Scout 边界
```

**3C 不被废止**：3F 在 3C 之上 **追加模块与 catalog 字段**；`HealthTurnResolver` 仍 **不选定最终 profile**（延续 §6.1 权责）。

---

## 3. 不可妥协的宪法对齐

与 [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) §2 相同，并追加：

| 约束 | 3F 立场 |
|------|---------|
| TurnEvidencePlan 先于 LLM | Arbiter 输出 plan 后才允许 Catalog / 工具 / LLM |
| Harness Veto | `forbidden` / Manifest 域校验不变 |
| Shadow zero-adopt | Intent Scout 仅提案 + telemetry |
| Data > Context | 升舱至 `combined_review` 仍禁止静默全量 `SUPPLEMENT_BG` |
| P0 显式 > P2 episodic | 用户 chip / 显式指标覆盖 `focus_goal` |
| 宪法第三条 | 1.5B 只产 **策略枚举**（`goal_class` / `suggested_domains`），不写断言正文 |

---

## 4. 完整管线（Stage 3F 目标态）

```text
用户句 (+ clarify_choice_id 若有)
  │
  ├─► HealthTurnResolver          # scope：metric / year / window / clarify 触发
  │       HealthTurnScope
  │
  ├─► GoalClassifier (C 层·新)    # goal_class：metric_specific | holistic | casual | clarify_pending
  │       输入：用户句 + catalog.goal_markers + turn_scope
  │       输出：goal_class, goal_confidence (deterministic 优先)
  │
  ├─► SchemaIntentRouter          # 资产域打分 → router_profile 候选
  │
  ├─► Harness Arbiter (C 层·新)   # 唯一权威 profile 合成点
  │       输入：goal_class + router_profile + turn_scope + existence_probe + episodic.focus_goal
  │       输出：authoritative_profile, arbiter_reason (enum)
  │
  ├─► TurnEvidencePlan            # slots / forbidden / tools_allowed
  ├─► Tier0 装配 + Catalog N 步点单
  ├─► LLM Composer（仅叙述）
  └─► numerics_manifest 审计 + Harness Veto
        │
        └── [async] Intent Scout → shadow_routing（zero-adopt）
```

**关键不变量**：Profile **只在 Harness Arbiter 之后** 锁定；Catalog 渲染仍在 Profile 之后。

---

## 5. 核心模块设计

### 5.1 GoalClassifier（C 层 · 声明式）

**职责**：判定用户本轮 **目标类型**，不选 profile、不拉证据。

**输出**：

```text
GoalClassification:
  goal_class: metric_specific | holistic_assessment | casual | clarify_pending
  confidence: float          # 规则命中 = 1.0；Shadow 补充时 < 1.0
  source: catalog | explicit_metric | shadow_suggest
```

**规则（写入 `health_intent_catalog.json`，禁止 Python 硬编码表）**：

```json
"goal_markers": {
  "holistic_assessment": {
    "tokens": ["综合", "整体", "评估", "各项指标", "全面", "大健康"],
    "anti_tokens": [],
    "notes": "合成健康目标；非指标专有名词"
  },
  "metric_specific": {
    "inherit_from": "metric_aliases",
    "notes": "用户句含可解析 metric token 时优先"
  }
}
```

**优先级**：

1. 显式 metric token → `metric_specific`  
2. `goal_markers.holistic_assessment` 命中且无显式 metric → `holistic_assessment`  
3. 寒暄 / 极短弱句 → `casual`（沿用现有 gates）  
4. 无法判定且 probe 多域 → `clarify_pending`

### 5.2 Harness Arbiter（C 层 · 确定性）

**职责**：合成 **authoritative_profile**；对标 tax 侧「clarify vs execute」分支，但 **health 域保持 deterministic**。

**输入**：`GoalClassification` + `SchemaIntentRouter` 候选 + `HealthTurnScope` + `existence_probe(user_id)` + `session_turn_focus.focus_goal`

**核心策略表**：

| goal_class | existence_probe | Arbiter 行为 | authoritative_profile |
|------------|-------------------|--------------|------------------------|
| `holistic_assessment` | lab ✓ 且 wearable ✓ | 自动升舱 | `combined_review` |
| `holistic_assessment` | 仅 lab ✓ | clarify `intent_scope` | `clarify` |
| `holistic_assessment` | 仅 wearable ✓ | clarify `intent_scope` | `clarify` |
| `holistic_assessment` | 均 ✗ | clarify `data_gap` | `clarify` |
| `metric_specific` | — | 沿用 SchemaRouter | router_profile |
| `casual` | — | 沿用 SchemaRouter | router_profile |
| episodic `focus_goal=holistic` + 弱问句 | lab ✓ 且 wearable ✓ | 续 goal，升舱 | `combined_review` |

**`arbiter_reason` 枚举**（写入 harness report，便于 telemetry）：

`schema_default` · `goal_holistic_upgrade` · `goal_clarify_scope` · `goal_clarify_data_gap` · `episodic_goal_continue` · `explicit_metric_override` · `session_anchor`

**与 existence_probe**：复用 [`catalog_existence.py`](../pha/catalog_existence.py) / [`metadata-catalog-v2.3.md`](metadata-catalog-v2.3.md) 既有探针，**不新建**平行探测 API。

**holistic 代理指标集**：由 catalog `holistic_proxy_metrics` 声明（如 LDL、HRV、steps、vo2max），供 Manifest 与 TASK 模板引用 — **非**「身体年龄」硬编码行。

### 5.3 Clarify 契约扩展（3C §6.4 的自然延伸）

在 `PHA_CLARIFY_TURNS=1` 已落地基础上，扩展 `clarify_kind`：

| clarify_kind | 触发 | choices 示例 | 用户选择后 |
|--------------|------|--------------|------------|
| `lab_year`（已有） | 多年化验弱问句 | 2023 / 2025 | explicit year scope |
| **`intent_scope`（新）** | holistic + 单域 probe | 化验+穿戴 / 仅化验 / 仅穿戴 | explicit domains → Arbiter 升舱 |
| **`data_gap`（新）** | holistic + 域缺失 | 说明缺域 + 引导上传（确定性文案） | 不进入 LLM 臆造 |

**原则**（延续 3C §6.4）：

- Clarify 轮短路 LLM；`forbidden` 禁止 Patient State 全表  
- Chip 选择 = P0 explicit，覆盖 episodic  
- Clarify 轮不写 `focus_goal=holistic`（待用户确认后再写）

### 5.4 Goal Session Anchor（Episodic 第二维度）

扩展 `session_turn_focus`（设计字段，编码在 3F-β）：

```text
focus_goal: holistic_assessment | metric_specific | null
focus_domains: ["lab", "wearable"]   # 用户 chip 或 Arbiter 升舱后写入
```

**续焦规则**：

- 弱问句（catalog `weak_followup`）+ `focus_goal=holistic_assessment` → Arbiter **必须**尝试 `combined_review`，**不得**仅续 `wearable_only` / `lab_cross_year` 单车道  
- 用户显式新指标（P0）→ 暂挂或降级 `focus_goal`  
- TTL / 刷新规则与 3C §6.2 相同

### 5.5 Intent Scout（Shadow · P1）

**职责**：异步语义提案，**zero-adopt**。

**输出**（仅 telemetry / 可选 status 提示）：

```json
{
  "goal_class": "holistic_assessment",
  "suggested_domains": ["lab", "wearable"],
  "confidence": 0.88
}
```

**采纳边界**：

- 默认：**不**改变 Arbiter 输出  
- 仅当 authoritative=`lifestyle` 且 shadow=`holistic_assessment` 且 confidence≥`PHA_SHADOW_CONFIDENCE_THRESHOLD` 时，可 emit **非阻塞 status**：「是否基于化验与穿戴综合评估？」→ 仍须 chip 或下轮 explicit  

Flag：`PHA_SHADOW_ROUTING=1`（沿用 v2.3 Stage 2D，扩展 shadow 字段）

### 5.6 Soul / Composer 契约（原则层）

当 `authoritative_profile=combined_review` 且 Manifest 已含 `holistic_proxy_metrics`：

- 允许基于 **Manifest KV 代理指标** 做合成叙述  
- 须声明「非标准临床指标 / 代理估计」  
- **禁止**在 Manifest 为空时（clarify 应已拦截）输出「请上传报告」替代 clarify

具体 Prompt  diff 另开 PR，本 RFC 只锁 **行为契约**。

---

## 6. 声明式 Catalog 扩展（设计稿 · 编码时写入 JSON）

以下片段为 **3F-γ 目标态**；编码 PR 须更新 [`rules/health_intent_catalog.json`](../rules/health_intent_catalog.json) 并由 registry selfcheck 校验。

```json
{
  "version": "1.2",
  "goal_markers": {
    "holistic_assessment": {
      "tokens": ["综合", "整体", "评估", "各项指标", "全面", "大健康", "身体年龄"],
      "priority": 10
    }
  },
  "holistic_proxy_metrics": ["ldl", "hdl", "hrv", "steps", "vo2max", "resting_hr"],
  "clarify_kinds": {
    "intent_scope": {
      "prompt_template": "您希望基于库内哪些数据做综合评估？",
      "choices": [
        {"id": "lab_wearable", "label": "化验 + 穿戴", "domains": ["lab", "wearable"]},
        {"id": "lab_only", "label": "仅化验档案", "domains": ["lab"]},
        {"id": "wearable_only", "label": "仅穿戴近90天", "domains": ["wearable"]}
      ]
    }
  }
}
```

**维护规则**：新合成目标说法 → 改 `goal_markers` + 黄金用例 + telemetry 聚类，**禁止**改 Python phrase 表。

---

## 7. Harness 可观测扩展

扩展 [`harness_report`](../pha/harness_report.py)（建议 schema bump **v1.3**，旧字段保留）：

```json
{
  "goalClass": "holistic_assessment",
  "goalSource": "catalog",
  "arbiterDecision": {
    "authoritative_profile": "combined_review",
    "router_profile": "lifestyle",
    "reason": "goal_holistic_upgrade",
    "existence_probe": {"lab": true, "wearable": true}
  },
  "turnScope": { "...": "同 3C" },
  "episodic": { "focusGoal": "holistic_assessment", "focusDomains": ["lab", "wearable"] }
}
```

**运营用法**（[`telemetry-review-playbook.md`](telemetry-review-playbook.md) §4 待增）：

- `router_profile=lifestyle` 且 `reason=goal_holistic_upgrade` → 升舱成功  
- `router_profile=lifestyle` 且 `goalClass=holistic` 且 profile 仍 lifestyle → **架构回归**  
- Shadow 与 authoritative 分歧率 → Stage 4 离线蒸馏输入

---

## 8. 黄金用例（H5–H8）

入 `scripts/pha_health_turn_resolver_selfcheck.py`（3F-α 起）并注册 `selfcheck_manifest.json`。

| ID | 场景 | 用户句序列 | 断言 |
|----|------|------------|------|
| **H5** | 开放合成首轮 | DB 有 lab+wearable；「根据各项指标综合评估健康状态」 | `goal_class=holistic`；`profile=combined_review` 或 `clarify intent_scope`；**非** lifestyle |
| **H6** | Goal 续焦 | H5 后弱问「那结论呢」 | `focus_goal` 续；`profile=combined_review`；metric 单域 episodic 不覆盖 goal |
| **H7** | P0 显式覆盖 | H5 后「只看 LDL」 | `goal` 降级；`profile=lab_cross_year`；`metric=ldl` |
| **H8** | 单域 probe | 仅 wearable DB；holistic 句 | `clarify_kind=intent_scope`；choices 含「仅穿戴」 |

**E2E（人工 / 真机，不阻塞 CI）**：任意 under-specified 合成问句 + 后续单指标解锁剧本 — 用于 telemetry 对照，**不作为单条 phrase 验收标准**。

---

## 9. 分期实施与 Feature Flag

| 阶段 | 内容 | Flag | 依赖 |
|------|------|------|------|
| **3F-α** | `GoalClassifier` + `Harness Arbiter` + harness `goalClass`/`arbiterDecision` + H5–H8 | `PHA_GOAL_CLASSIFIER=1` | 3C-γ catalog | ✅ 已编码 |
| **3F-β** | `focus_goal` / `focus_domains` episodic + H6/H7 | `PHA_GOAL_SESSION_ANCHOR=1` | 3F-α | ✅ 已编码 |
| **3F-γ** | catalog `goal_markers` + `holistic_proxy_metrics` + clarify `intent_scope`/`data_gap` + H8 | `PHA_CLARIFY_INTENT_SCOPE=1` | 3F-α, 3C-δ | ✅ 已编码 |
| **3F-δ** | Intent Scout shadow 字段 + telemetry  playbook §4 | `PHA_SHADOW_ROUTING=1` | 3F-α | ✅ 已编码 |

**回滚**：各 flag 独立默认 `0`；关闭后回退 3C-ε 行为。

**与共识 P0/P1/P2 映射**：

| 共识优先级 | 3F 映射 |
|------------|---------|
| P0 | Arbiter + orchestrator 接入点；harness report 字段 |
| P1 | Intent Scout shadow；Catalog N 步在 combined 内点单 |
| P2 | catalog 扩展 + registry 校验 + telemetry 聚类 |

---

## 10. § SOTA 业界先进范式对照表

| 业界模式 | PHA 3F 采纳 | 刻意不采纳 |
|----------|-------------|------------|
| OpenAI Tool Use 路由 | C 层 Arbiter 定 plan 后白名单工具 | LLM 自选 tool 序列 |
| Claude Code 自主探索 | Intent Scout 异步提案 | LLM 主控 loop |
| ReAct 多步推理 | Catalog **受控** N 步点单（已有） | 无上限 ReAct |
| RAG 宽检索 | existence_probe **窄域**升舱 | 全库 embedding 检索替代 plan |
| Tax `TaxTurnResolver` + clarify | HealthTurnScope + clarify chips | 跨域 import |

---

## 11. 验收标准

### 11.1 自动

- [x] `bash scripts/run_selfchecks.sh` 全绿（含 H5–H8、H-δ8/δ9、stage3f_delta）  
- [x] `generate --check` profile registry 与 catalog 一致  
- [x] `router_profile=lifestyle` + holistic 句 → authoritative ≠ lifestyle（probe 双域时）

### 11.2 合规

- [x] 无 LLM 夺权；Shadow zero-adopt  
- [x] numerics 无新增 `unauthorized_value` 回归（body-age E2E P2 SSE 硬断言）  
- [x] 无单条 E2E phrase 硬编码（路由/goal 走 catalog + Arbiter）

### 11.3 文档

- [x] 本 RFC 状态 → **Implemented**（2026-06-24）  
- [x] `harness-change-log.md` + `startup-change-log.md` 同步

---

## 12. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| holistic 过触发 → combined 体积膨胀 | 中 | existence_probe 门控 + Tier0 Protected SLA |
| clarify 过多 | 低 | 仅 under-specified + 多域/缺域；单 metric 不 clarify |
| Arbiter 与 Resolver 双源 profile | 高 | **唯一** authoritative 出口 = Arbiter |
| goal_markers 维护熵 | 中 | telemetry 聚类 + 离线蒸馏（Stage 4） |

---

## 13. 文档与变更登记

| 文档 | 内容 |
|------|------|
| `docs/stage3c-multi-turn-episodic-focus-rfc.md` | §15 衔接指针 |
| `docs/pha-architecture-evolution-v2.3.md` | §8 Stage 3F 路线图 |
| `docs/telemetry-review-playbook.md` | §4 goal/arbiter 字段 |
| `docs/harness-change-log.md` | 3F 分期条目 |
| `docs/startup-change-log.md` | flag 与验收 |
| `AGENTS.md` / `pha-mandatory-reads.mdc` | 索引更新 |

---

## 14. 附录：可观测样例（非需求来源）

以下对话模式用于 **telemetry 聚类标注**，**不是**本 RFC 的单点需求：

1. 开放合成问句 → lifestyle / manifest_n=0  
2. 用户逐个点名指标 → 单域 profile 轮换  
3. 显式 VO2 / 穿戴词 → wearable manifest 改善  
4. 同句多指标 → `combined_review` 金路径  

该样例证明 **组装完整性** 缺口；修复路径是 **§5 全模块**，不是为样例中的某一措辞加规则。

---

## 15. v1.14 增补（Approved · 文档锁定 · 未编码）

> 2026-09-09 维护者同意审计：不得为「整体+重点看」扫全卡、不得药物短语翻转 Data > Context、不得按笔记长度捞历史方案。编码前必读 [`handoff-2026-09-09-outline-and-context-lookup.md`](handoff-2026-09-09-outline-and-context-lookup.md)。**不废止** §5.1 既有优先级（显式 metric → `metric_specific`）与 H7「只看 LDL」；下列为 **追加** 模块与策略行。

### 15.1 `outline_mode`（解读 / `daily_readiness` 叙述契约）

不选 profile。写入 `health_intent_catalog.json` 的 `assessment_outline`：

| mode | 标记（catalog tokens，编码时定稿） | 叙述 |
|------|-------------------------------------|------|
| `exclusive` | 只看 / 仅 / only look at | P9.5b：只谈点名行 |
| `emphasis` | 重点看 / 侧重 / especially | 点名为主；其它勾选有值行可同段带过，禁另起专题段。**v1.15**：英文 TASK 第 1 句 = overall（无 metric label）；`exclusive` 不得要求整体起笔 |
| `cover-card` | 未命中上两档 | 覆盖勾选有值行 |

优先级 **exclusive > emphasis > cover-card**。`daily_readiness` 不得默认 exclusive。Python 不解析评估要求中的指标 id。不得把 emphasis 改成 cover-card（有值必须点到）；不得缺行再跑一轮 LLM。

### 15.2 `goal_class=context_lookup`

追加到 GoalClassifier 输出枚举。规则写入 `goal_markers.context_lookup`（禁止 Python 药名/问句表）。existence = notes probe，不是 wearable。

**Arbiter 策略行（追加，不改 Data > Context）：**

| goal_class | 其它 | 行为 | authoritative_profile | arbiter_reason |
|------------|------|------|------------------------|----------------|
| `context_lookup` 且无显式 metric | notes ✓/✗ 均不升舱 combined | 已有 lifestyle / context_only | `lifestyle` | `goal_context_lookup` |
| `context_lookup` 且显式 metric | — | **不** warehouse skip-LLM；数字走点名指标；背景仅 brief 切片 | router_profile（通常 `wearable_only`） | `explicit_metric_with_context_lookup` |
| 纯 metric_specific（如 90d HRV 趋势） | — | 不变 | router_profile | `schema_default` |

升舱 `combined_review` 仍禁止静默全量 `SUPPLEMENT_BG`。`fact_card` ⊆ `turn_scope.metric_keys`；空则不上卡。**v1.15**：`wearable_daily_review` 在已有 FACT_CARD_CONTEXT 时，SSE ⊆ 该卡 metric 行（含合法簇展开）；训练词不把 `workout_*` 塞进 scope。

### 15.3 捕获

`supplement_bg` schema：`background_capture_keywords` 的疑问/祈使为 negative。与 lane 独立（延续 3F capture ≠ route）。

### 15.4 非目标（本增补）

- 为单条黄金句写 Python equals  
- 提前开 CHB / P15  
- 新 profile 仅服务「我有没有服药」  
- 翻转 *Data beats Context* 打分顺序  

编码映射：共识 P1（catalog + Arbiter 行 + plan 发卡过滤）；flag 见交接 §3。

---

## 16. v1.15 增补（Approved · 评测审计落地）

> 2026-09-10 维护者授权：40+40 三方案按共识改写后开工。真源 [`handoff-2026-09-10-eval-audit-solution.md`](handoff-2026-09-10-eval-audit-solution.md)。**不废止** §15。

| 项 | 做 | 不做 |
|---|---|---|
| Tier0 | 卡上已有行 KV / Manifest 不得尾截断；超限先压 FACT_CARD_CONTEXT advice | 单纯调大全局 4500 作为唯一修复；`_cap_system_content` 砍 T0 |
| TASK | emphasis Sentence 1 = overall | exclusive 整体起笔；黄金一句 Python if |
| 发卡 | SSE ⊆ FACT_CARD_CONTEXT metric 行 | prefs ∩ 裁簇展开；must 覆盖；缺行重试 |

编码映射：共识 P1；卡 **M1-P19**。

---

## 17. v1.16 增补（Approved · exclusive 注入 + 规则层为准 + P15）

> 2026-09-10 维护者口令：按 1–5 顺序开工，事项 4（换模型）不做。真源 PRD v1.16。**不废止** §15 / §16。

| 项 | 做 | 不做 |
|---|---|---|
| exclusive 注入 | 仅 exclusive 解读轮 `FACT_CARD_CONTEXT` + Manifest ⊆ catalog `infer_wearable_metric_ids`；可见 HTML 卡仍整卡；空则 fail-closed | 扫全卡；Python 新写评估要求解析器；emphasis/cover 裁卡；must 覆盖 |
| 起笔 / 训练 | 以规则层 summary/advice 为准；P19 Sentence 1 不加字；金标改 telemetry | 为黄金一句加 Python if；按 band 生成「可以力量训练」 |
| brief 读侧 | 配额前与捕获同一 `background_capture_negative_keywords` | 偏爱长笔记；运行时 LLM 自愈 |
| P15 CHB | §Background + lineage；组合 hash；GET 事实卡后台同日一次；interpret 投影无 §Facts | `USER_CONTEXT_BRIEF_PROFILES` 加 `fact_card_interpret`；brief 数字进 Manifest |

编码映射：共识 P1；卡 **M1-P20** / **M1-P15**。Flag：`PHA_EXCLUSIVE_INJECT_NAMED`、`PHA_CHB_AUTOCOMPILE`（均默认 1）。

---

## 18. v1.18 增补（Approved · CHB 自述行 + USER_CONTEXT_BRIEF 投影 §Background）

> 2026-09-10 维护者选第 2 刀。真源 PRD v1.18。**不废止** §15–§17。

| 项 | 做 | 不做 |
|---|---|---|
| 编译 | notes → `background_rows[]`：`category` + 去数字短句 + 相对时间 + `prov_type=user_statement`；时段拆行沿用 copy 词表 | 药名/补剂名 Python 表；自述进 §Facts / Manifest |
| 聊天投影 | `USER_CONTEXT_BRIEF`（lifestyle / combined）必须带 §Background | 解读轮加 `USER_CONTEXT_BRIEF`；`USER_CONTEXT_BRIEF_PROFILES` 加 `fact_card_interpret` |
| 解读 | 同一组行经既有 `USER_BACKGROUND_BRIEF` | 改 TASK 第 5 条；「点名训练则补剂相关」 |

---

## 19. v1.19 增补（Approved · TASK 槽契约：零编数 + brief 在场不得 skip）

> 2026-09-10 黄金句审计熔断 21.5/85/95。维护者采纳通用槽契约，**不废止** §15–§18。数字真源仍是 Manifest / FACT_CARD_CONTEXT，不是 CHB §Facts。

| 项 | 做 | 不做 |
|---|---|---|
| 零编数 | TASK 禁止发明或派生额外数字/百分比（含 100−百分位）；无 Manifest token 只用定性词；人群示例去掉会诱出 95 的 `95%` | 放水 Numerics；brief 数字进 Manifest |
| 背景槽 | brief 在场则 in-scope，禁止整槽 skip；导语去掉「无关则忽略」；写入建议句，不另起编号注意事项清单；弱因果：禁止 causes / leads to / 导致·引起 | 「点名训练则补剂相关」；药名表；解读轮加 `USER_CONTEXT_BRIEF`；强制注意事项专段 |

编码映射：共识 P1；卡 **M1-P15** → DONE（PRD v1.22；遗留另开）。

---

## 20. v1.20 增补（Approved · 脉络丢指标字段残行）

> 2026-09-10。真源 PRD v1.20。**不废止** §15–§19。

| 项 | 做 | 不做 |
|---|---|---|
| 脉络 | 只保留反复出现的注意事项句；去数字后的今日值/百分位/窗口均值残行丢弃；空则不注入 | 放水审计；药名表；从注入里拿掉卡上百分位（规则层仍用百分位分档） |

---

**Stage 3F · v0.1 Approved（2026-06-17）** — **状态：Implemented（2026-06-24）** — **3F-α ✅ · 3F-β ✅ · 3F-γ ✅ · 3F-δ ✅** 已编码；P2 combined_review SSE 硬断言已接入 E2E。
