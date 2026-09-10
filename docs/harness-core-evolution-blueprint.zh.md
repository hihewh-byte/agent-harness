# Harness Core 演进蓝图 — PHA ↔ tax_agent

> **Language / 语言**：[English](harness-core-evolution-blueprint.md) · 中文（本文）

> **状态**：Phase A 完成（2026-07-09）· **Week 2**：协议隔离已开始  
> **相关文档**：[harness-builder-overview.md](harness-builder-overview.md) · [harness-consensus-opus48-2026-06-08.md](harness-consensus-opus48-2026-06-08.md) · [harness-core-protocol-v0.md](harness-core-protocol-v0.md)  
> **第二域**：`../tax_agent/`（`myAgents/` 下的兄弟仓库）  
> **本机 core 骨架**：`../harness_core/`（仅接口 — 未发布）

---

## 0. 目的

在任何 `agent-harness-core` 包出现之前，先定义 **最低「框架完备」** 门槛：

1. 两个真实领域（健康 + 税务）共享 **同一套控制平面哲学**
2. 两者都能在 **不调用 LLM** 的情况下演示 Plan → Tier0 → Audit
3. 书面对照：**core** vs **domain plugin** 各管什么

本文是 Phase A 交付物。它 **不** 授权抽取到 PyPI。

---

## 1. 控制平面同构

```text
User message
    → Turn plan (profile / slots / forbidden / tools)
    → Tier0 assembly (protected budget)
    → (optional) LLM compose
    → Numerics / citation audit
    → Build report (+ warnings)
```

| 层 | PHA | tax_agent | 共享想法？ |
|-------|-----|-----------|--------------|
| Turn plan | `TurnEvidencePlan` · `pha/harness_plan.py` | `FilingTurnPlan` · `tax_agent/harness_plan.py` | ✅ 形态相同 |
| Intent → profile | `health_intent_catalog` + resolver | `tax_intent_catalog.yaml` + router | ✅ 声明式 catalog |
| Tier0 budget | `harness_tier0_assembly.py`（~474 LOC） | `harness_tier0_assembly.py`（~98 LOC） | ✅ 受保护 SLA |
| Session ledger | Patient State | `FilingSessionState` | ✅ 领域状态 blob |
| Numerics audit | `numerics_manifest.py` | `numerics_audit.py` | ✅ whitelist ⊆ evidence |
| 领域额外审计 | CompareTable（wearable） | `citation_audit`（policy） | ⚠️ 都是「后置门」，操作不同 |
| Build report | `harness_report` v1.2 丰富 | `tax.harness_report/v2` 精简 | ⚠️ 意图相同，tax 更薄 |
| Turn FSM | `chat_turn_fsm.py` | `tax_agent/chat_turn_fsm.py` + 接到 `chat_turn_service` | ✅ Phase A P1 |
| plan_vs_actual | `compute_plan_vs_actual()` | `planVsActual` on `tax.harness_report/v2` | ✅ |
| Profile registry CI | `harness_profile_registry.py` | `tax_agent/harness_profile_registry.py` | ✅ Phase A P1 |
| 无 LLM golden run | `scripts/pha_harness_golden_run.py` | `scripts/run_tax_harness_golden_run.py` | ✅ Phase A |
| 代码 import | — | 仅 `pha.llm_provider` / ollama bridge | ❌ harness 是孪生，不是库 |

**今日复用分数**：哲学 **~8/10** · 共享 harness 代码 **~2/10**。

---

## 2. 字段级 plan 对照

| 字段 | PHA `TurnEvidencePlan` | tax `FilingTurnPlan` | Core 候选？ |
|-------|------------------------|----------------------|-----------------|
| `profile` | ✅ | ✅ | **是** |
| `slots_tier0` / `slots_tier1` | ✅ | ✅ | **是** |
| `forbidden` | ✅ | ✅ | **是** |
| `tools_allowed` | ✅ | ✅ | **是** |
| `task_text` | ✅ | ✅ | **是**（字符串；内容属领域） |
| `legacy_question_type` | 仅 PHA | — | 否（PHA plugin） |
| `tax_year` / `journey_phase` / `focus` | — | 仅 tax | 否（tax plugin） |
| `fast_lane` | 经 runtime | ✅ 在 plan 上 | **是**（可选 flag） |
| `preserve_raw_user` | — | ✅ | **是**（可选） |

---

## 3. 什么进未来 Core，什么留在 plugin

### Core（领域无关）

| 模块想法 | 理由 |
|-------------|-----------|
| `TurnPlan` protocol / dataclass | LLM 之前冻结证据边界 |
| Tier0 assembler + 受保护 SLA | 预算内不丢掉关键 slots |
| `BuildReport` 最小 schema + `plan_vs_actual` | 可观测性 / 回归 |
| 回合阶段守卫（plan 先于 compose） | 可强制的不变量 |
| Numerics 审计 **接口** | `allowed_values` + 扫描回复 + fail → weak lane |
| Sub-agent / tool allowlist veto | 可选但可移植 |

### Domain plugin（不得进入 Core）

| 领域 | 留在 plugin |
|--------|----------------|
| **PHA** | Wearable CompareTable、LDL authority、health intent catalog、patient_state SQL、attachment lanes |
| **tax** | filing_table、FX provenance、classified income、policy citation KB、journey_phase |
| **企业 toB（PHA RFC）** | Gateway JWT、RBAC、`tenant:patient` user_id、device ingest adapters — **在** harness core **之外** |

### Core 的明确非目标

- 多租户 RBAC / care_relationships  
- 设备 MQTT/BLE 传输解析器  
- CRM / ERP 连接器  
- 「医生多患者 UI」

这些属于 **Gateway / Ingest** 层（见 §5）。放进 Core 会变成 Gemini 正确警告过的「四不像」。

---

## 4. tax 相对 PHA 的缺口（建设 backlog）

| 缺口 | 优先级 | 说明 |
|-----|----------|-------|
| 结构化 `plan_vs_actual[]`（或等价机器 diff） | **P0** | ✅ `planVsActual` on `tax.harness_report/v2`（2026-07-09） |
| 带人读卡片的无 LLM golden run | **P0** | ✅ `tax_agent/scripts/run_tax_harness_golden_run.py` |
| 将 `docs/tax-harness-build-report-schema.md` 对齐到 **v2** | **P0** | ✅ 本机 tax_agent 文档（未公开发布） |
| Turn FSM / 阶段 telemetry | **P1** | ✅ `chat_turn_fsm.py` + `resolve_chat_turn` phases（2026-07-09） |
| Profile registry generate + CI check | **P1** | ✅ `harness_profile_registry.py` + selfcheck `--generate/--check` |
| 报告中更丰富的 tier0_integrity slot 行 | **P1** | ✅ `tier0Integrity` + tax compliance `assertions[]` |
| golden run 中的英文 dry-run 用例 | **P2** | 构建者 onboarding |
| 抽取共享包 | **P2+** | 仅在 adapters 被证明之后 |

---

## 5. 设计文档里的 PHA「toB」（不是 harness-core）

个人 OSS（`v0.4.0-beta.1`）是 **单用户本机**。行业 / 临床 toB 是 **Future Work，仅文档**：

| RFC | 意图 | 与 Harness 的关系 |
|-----|--------|---------------------|
| [`rfcs/rfc-device-ingestion-adapter.md`](rfcs/rfc-device-ingestion-adapter.md) | 任意 wearable/IoT → L1 日行；双层 `source_vendor` | **Ingest L0**；CompareTable/FSM **不变** |
| [`rfcs/rfc-enterprise-multi-tenant.md`](rfcs/rfc-enterprise-multi-tenant.md) | 医院 → 医生 → 多名患者；Gateway RBAC；`effective_user_id = tenant:patient` | **HTTP Gateway**；Core 仍只看到一个 `user_id` |
| [`rfcs/rfc-hospital-iot-ops-agent.md`](rfcs/rfc-hospital-iot-ops-agent.md) | **Hospital IoT Ops Agent** 产品草案（HIO-A/G/R/D…）；面向医疗 IoT 厂商的证据锁定运维问答 | **Domain plugin + PoC 计划**；消费 Core / Gateway / Ingest；**仅文档 / 零生产代码** |
| [`rfcs/product-definition-hio-ops-agent.md`](rfcs/product-definition-hio-ops-agent.md) | 可售卖产品定义（HIO-A P0），面向厂商售前 / 医院设备科 | 产品包装；验收标准 |
| [`rfcs/handoff-tob-hio-agent.md`](rfcs/handoff-tob-hio-agent.md) | **ToB agent 交接**：使命、产品判断、可复用资产、铁律、backlog | 专用 HIO/ToB 工作流入口 |

Wave 4a 明确把多租户 SaaS 与厂商设备集成 **排除** 在开源个人版之外（[`wave4a-open-source-readiness-spec.md`](wave4a-open-source-readiness-spec.md) §1）。

**对路线图的含义**：PHA 行业 toB 是 **产品/平台** 轨道（Gateway + Device Adapter）。它应 **消费** 稳定 harness，而不是重定义它。Phase A（PHA↔tax 对齐）仍是编码这些 RFC 之前正确的地基。

---

## 6. ASI 适配（销售情报）— 推迟

ASI（`agentic_sales_intelligence`）是 **pipeline / evidence-tier / delivery** 系统。它当前 **没有** 实现 PHA 的 Plan → Tier0 → Numerics 硬门。

| 问题 | 结论 |
|----------|---------|
| 宣告 harness「框架完备」需要 ASI 吗？ | **否** — 双域（PHA ↔ tax）已足够 |
| 是否应把 ASI 整仓改写到 PHA harness 上？ | **否** — 形态不对（多模块 M1/M3/M5，cloud/local 混合） |
| 日后可选切片？ | 可能做数字诚实网关 — **不** 在关键路径上 |

**2026-07-10 决策**：跳过 ASI Phase B1；主线 = Core 协议隔离 → adapters。

---

## 7. Phase A 退出标准

- [x] 本蓝图存在  
- [x] `tax_agent` 无 LLM golden run 脚本存在且打印 PASS  
- [x] tax `planVsActual` 结构化字段 + schema 文档 v2（仅本机 tax_agent；**未** 发布到 GitHub）  
- [x] tax P1：Turn FSM + profile registry + 更丰富的 `tier0Integrity`（仅本机）  
- [x] 尚未运行时抽进 PHA；PHA `main` 5 分钟路径未动  
- [x] **政策**：未经明确必要性审查，不得把 tax_agent 个人数据或 tax 仓库内容上传到公开远端

---

## 8. Phase A 之后（Week 2–3）

1. ~~关闭 tax P0/P1 缺口~~ ✅  
2. ~~Week 2：冻结协议 + 本机 `harness_core` 骨架~~ ✅  
3. ~~Week 3 薄 Adapter + golden 绿墙~~ ✅（`pha/harness_core_adapter.py`，`tax_agent/harness_core_adapter.py`）  
4. 日后可选：ASI 数字切片 **或** Device/Gateway 文档→原型 — **在 Core 之外**  
5. 仅在你明确要发布包之后才上 PyPI（adapters 已证明接口）
