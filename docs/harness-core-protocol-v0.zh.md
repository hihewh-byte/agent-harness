# Harness Core 协议 v0 — 接口设计（Week 2）

> **Language / 语言**：[English](harness-core-protocol-v0.md) · 中文（本文）

> **状态**：Phase A 完成 · Core 已 vendored 进仓（2026-07-10）· **尚无 PyPI**  
> **上级**：[harness-core-evolution-blueprint.md](harness-core-evolution-blueprint.md)  
> **仓内包**：[`packages/harness_core/`](../packages/harness_core/)  
> **范围外**：ASI、临床多租户 Gateway、发布 tax_agent

---

## 0. 目标

定义 **最薄的领域无关控制平面**，PHA 与 tax 已经作为孪生实现了它：

```text
Plan (freeze evidence boundary)
  → (optional) Compose / Fast-lane
  → Post-Audit (integrity + plan_vs_actual)
```

**框架完备（事实）当且仅当**：

1. 本协议已写成并冻结为 v0  
2. 本机 `harness_core` 包只暴露 Protocol / dataclass / FSM 守卫  
3. Week 3：PHA + tax 各有一个薄 Adapter；两边无 LLM golden run 保持绿灯  

v0 **不** 要求删除 `pha/harness_*.py` 或 `tax_agent/harness_*.py`。

---

## 1. 分层

```text
┌─────────────────────────────────────────────────────────┐
│  组件族                                                  │
│  harness-core（薄在线）                                  │
│  TurnPlan · CoreTurnPhase · PhaseRecorder               │
│  IntegrityResult · plan_vs_actual · （可选）Numerics    │
│                                                          │
│  Harness Loop (Alpha)（离线 — 未 vendored 进 Core）      │
│  proposal / verdict / failure_event 契约（§11）          │
│  → packages/harness_loop + domain plugins                │
└───────────────────────────┬─────────────────────────────┘
                            │ Adapter
           ┌────────────────┼────────────────┐
           ▼                                 ▼
   PHA plugin（参考实现）             tax / HIO / …
   CompareTable, catalog,             domain tables,
   T0 + CHB, loop scripts …           domain Loop Adapter …
```

| 层 | 拥有 | 不得拥有 |
|-------|------|--------------|
| **Core** | Plan 形态、阶段顺序不变量、integrity 码、plan↔runtime diff、**演进协议注册** | Slot 名、领域审计、catalogs、SQL、FX、Harvest/Distill **实现** |
| **Harness Loop (Alpha)** | 离线编排骨架、veto 门禁、promote CLI（Stage B） | 领域 catalogs、T0 schemas |
| **Adapter** | 映射领域 plan ↔ `TurnPlan`；映射领域 phases ↔ core ranks | 业务规则 |
| **Plugin** | 一切领域特定内容（PHA = 参考 Loop plugin） | 重新实现 plan-before-compose |

---

## 2. Core 模块（v0 表面）

| 模块 | 职责 | 今日 PHA 孪生 | 今日 tax 孪生 |
|--------|----------------|----------------|----------------|
| `turn_plan` | 冻结的 LLM 前契约 | `TurnEvidencePlan` | `FilingTurnPlan` |
| `turn_fsm` | 阶段记录器 + plan-before-compose | `ChatTurnPhase` | `TaxTurnPhase` |
| `integrity` | Tier0 integrity 结果形态 + diff 码 | `tier0_integrity` dict | `tier0Integrity` + assertions |
| `plan_vs_actual` | plan vs runtime 的机器 diff | `compute_plan_vs_actual` | tax 报告上同名 |
| `numerics`（可选 v0.1） | 仅 Protocol：`allowed_values` + scan | `numerics_manifest` | `numerics_audit` |

**明确推迟出 Core v0**：

- 完整 Tier0 assembler（预算 + 受保护 SLA 留在 plugins；Core 只类型化 integrity **结果**）  
- Profile registry CI（plugins 继续 generate/check；Core 日后可加通用「契约快照」助手）  
- Build-report JSONL writers（领域 schema 不同）

---

## 3. `TurnPlan` — 通用字段

### 3.1 必填（两域都有）

| 字段 | 类型 | 含义 |
|-------|------|---------|
| `profile` | `str` | 路由 / 组装键 |
| `slots_tier0` | `Sequence[str]` | 必须尝试的证据 slots |
| `slots_tier1` | `Sequence[str]` | 软 / 溢出 slots |
| `forbidden` | `Sequence[str]` | 硬 veto 码（工具或行为） |
| `tools_allowed` | `Sequence[str]` | 工具 allowlist |
| `task_text` | `str` | 操作员指令（领域语言 OK） |

### 3.2 可选（Core 感知，领域可设）

| 字段 | 类型 | 默认 | 说明 |
|-------|------|---------|-------|
| `fast_lane` | `bool` | `False` | 确定性回复可跳过 Compose |
| `preserve_raw_user` | `bool` | `True` | 不在 plan 中改写用户原话 |

### 3.3 仅 Plugin（永不出现在 Core dataclass 上）

| 字段 | 归属 |
|-------|--------|
| `legacy_question_type` | PHA |
| `tax_year`, `journey_phase`, `focus`, `inject_insight`, `intent_score` | tax |

若 Core telemetry 需要袋子，Adapters 通过 `domain_meta: Mapping[str, Any]` 暴露这些 — **不是** 一等 Core 字段。

### 3.4 Protocol 草图

```python
class TurnPlan(Protocol):
    @property
    def profile(self) -> str: ...
    @property
    def slots_tier0(self) -> Sequence[str]: ...
    @property
    def slots_tier1(self) -> Sequence[str]: ...
    @property
    def forbidden(self) -> Sequence[str]: ...
    @property
    def tools_allowed(self) -> Sequence[str]: ...
    @property
    def task_text(self) -> str: ...
```

冻结 dataclass `TurnPlanData` 实现同一形态，供 dry-run 与 adapters 使用。

---

## 4. FSM — core 阶段 vs 领域阶段

### 4.1 设计选择：**带秩的 core 脊柱 + 领域别名**

领域保留丰富阶段名（PHA 有 `SLOT_ASSEMBLY`；tax 有 `SCOPE` / `FAST_LANE`）。  
Core 只强制一条 **脊柱** 和硬不变量。

**Core 脊柱（有序）：**

| CoreTurnPhase | 含义 |
|---------------|---------|
| `INIT` | 回合开始 |
| `SESSION` | 已加载 session / prefs |
| `PLAN` | 证据边界已冻结（存在 `TurnPlan`） |
| `COMPOSE` | LLM 或规则产出用户可见回复 |
| `POST_AUDIT` | Integrity / numerics / plan_vs_actual |
| `DONE` | 成功终态 |
| `ERROR` | 失败终态 |

**不变量（铁律）：** 任何进入 `COMPOSE`（或被分类为 compose 的领域别名）的路径 **必须** 更早进入过 `PLAN`。提前退出（`CLARIFY` → `DONE`）不必 plan。

### 4.2 领域阶段 → core 秩（Adapter 表）

| Core | PHA 例子 | tax 例子 |
|------|--------------|--------------|
| INIT | `init` | `init` |
| SESSION | `session`, `perception`, … | `session`, `scope` |
| PLAN | `plan`, `slot_assembly`, `tier0_assemble`, `plan_pre_llm`, `skip_llm_eval` | `plan` |
| COMPOSE | `compose` | `compose`, `fast_lane` |
| POST_AUDIT | `post_audit` | `post_audit` |
| DONE / ERROR | 相同 | 相同 |

Core `PhaseRecorder` 存储 **core** 阶段（或 `(core, domain_alias)` 对）。Plugins 可并行保留完整领域 telemetry。

### 4.3 环境 kill-switch

| 今日领域 | Core v0 |
|--------------|---------|
| `PHA_CHAT_TURN_FSM` | Adapter 映射到 `HARNESS_TURN_FSM` **或** 保留领域环境变量 |
| `TAX_CHAT_TURN_FSM` | 相同 |

Week 2 骨架只在 `harness_core` 内使用 `HARNESS_TURN_FSM`；adapters 日后决定桥接。

---

## 5. Integrity + `plan_vs_actual`

### 5.1 `IntegrityResult`（最小）

```text
budget_limit: int
used_chars: int
slots: list[{slot_id, present, protected?, level?, chars?, materialized?}]
errors: list[str]      # hard codes
warnings: list[str]    # soft codes
assertions: list[str]  # optional compliance labels (tax-style)
```

Core **不知道** `FILING_TABLE_AUTHORITY` 是什么意思 — 只知道码是字符串。

### 5.2 `plan_vs_actual` 码（可移植模式）

| 模式 | 例子 | 含义 |
|---------|---------|---------|
| `tool_not_allowed:{name}` | `tool_not_allowed:invent_fx` | 已执行工具 ∉ allowlist |
| `missing_tier0_slot:{id}` | `missing_tier0_slot:NUMERICS_MANIFEST` | 被跟踪的计划 slot 为空 |
| `tier0_not_materialized:{id}` | … | slot 内容不在 ledger 文本中 |
| `protected_slot_empty:{id}` | … | 受保护 slot 缺失 |
| 领域码 | `assert:no_llm_compute` | 插件特定；Core 当作不透明 |

函数签名：

```python
def compute_plan_vs_actual(
    plan: TurnPlan,
    *,
    tools_executed: Sequence[str] = (),
    slot_contents: Mapping[str, str] | None = None,
    tool_error: str | None = None,
    integrity: IntegrityResult | Mapping[str, Any] | None = None,
) -> list[str]:
    ...
```

---

## 6. Numerics 审计（v0 仅 Protocol）

```python
class NumericsAuditor(Protocol):
    def allowed_values(self) -> Sequence[str]: ...
    def audit_reply(self, reply: str) -> Mapping[str, Any]:
        """Return at least {ok: bool, warnings: list[str]}."""
```

实现留在 PHA / tax。Core 日后可附带一个平凡「子串 allowlist」助手 — Week 2 Done **不** 要求。

---

## 7. 字段映射速查（Adapter 准备）

| Core `TurnPlan` | PHA `TurnEvidencePlan` | tax `FilingTurnPlan` |
|-----------------|------------------------|----------------------|
| `profile` | `profile` | `profile` |
| `slots_tier0` | `slots_tier0` | `slots_tier0` |
| `slots_tier1` | `slots_tier1` | `slots_tier1` |
| `forbidden` | `forbidden` | `forbidden` |
| `tools_allowed` | `tools_allowed` | `tools_allowed` |
| `task_text` | `task_text` | `task_text` |
| `fast_lane` | （runtime） | `fast_lane` |
| `preserve_raw_user` | `preserve_raw_user` | `preserve_raw_user` |
| — | `legacy_question_type` → `domain_meta` | `tax_year`, `journey_phase`, … → `domain_meta` |

---

## 8. 包布局

**公开（本仓库）：**

```text
packages/harness_core/   # monorepo root (GitHub: agent-harness)
  README.md
  pyproject.toml
  src/harness_core/
    turn_plan.py · turn_fsm.py · integrity.py · plan_vs_actual.py
  tests/
```

**本机孪生（未发布）：** `myAgents/harness_core/` 仍可作为工作副本存在；PHA 优先使用上面 vendored 树。

**Week 2 Done 标准（本文 + 骨架）：**

- [x] PHA `docs/harness-core-protocol-v0.md` 中的协议文档  
- [x] 本机 `myAgents/harness_core/` 骨架（TurnPlan / FSM / Integrity / plan_vs_actual）  
- [x] FSM + plan_vs_actual 的单元测试  
- [x] 协议文档在公开 `main`（`77cde06`）  
- [x] 两边领域 golden run 绿灯 **且不** 要求公开 PHA clone 必须有 Core（软跳过）

**Week 3 Done 标准（adapter 集成 — 2026-07-10）：**

- [x] `pha/harness_core_adapter.py` + `tax_agent/harness_core_adapter.py`（tax 仅本机）  
- [x] Golden run 断言 adapter smoke  
- [x] 软 tax 运行时 telemetry：Core 存在时有 `corePhases`（本机）  
- [x] **公开 PHA 中 vendored Core：** `packages/harness_core/`（clone-and-run；不是 PyPI）  
- [ ] 日后可选：领域 FSM **委托** `assert_plan_before_compose` 给 Core  
- [x] `pha_harness_golden_run` PASS，使用仓内 Core

---

## 9. 非目标（重申）

- 不要把 ASI 改写到本 Core 上  
- 不要把 Gateway / RBAC / device ingest 放进 Core  
- 不要把 CompareTable 或 filing_table 移进 Core  
- 在 Week 3 adapters 被证明之前不要发布到 PyPI  
- 设计期间不要打断 PHA 5 分钟 UI 路径或 tax 30s golden run

---

## 10. 决策日志

| 日期 | 决策 |
|------|----------|
| 2026-07-10 | 跳过 ASI Phase B1；主线 = Core 协议隔离 |
| 2026-07-10 | Core FSM = 脊柱 + adapter 别名表（不是所有领域阶段的并集） |
| 2026-07-10 | Tier0 **assembler** 留在 plugin；Core 拥有 integrity **结果** + plan_vs_actual |
| 2026-07-10 | 本机包路径：`myAgents/harness_core/`（兄弟目录），不在 tax_agent 内 |
| 2026-07-13 | 离线演进 = **Harness Loop** 伴侣（不在 Core 源树）；在本协议注册 proposal/verdict schemas；PHA = 参考 plugin |
| 2026-07-13 | 命名：弃用 “Official Loop Suite”；公开名 = **Harness Loop (Alpha)** |

---

## 11. 离线演进契约（Harness Loop）

> **状态：** schemas 注册为 **控制平面 I/O**。  
> **今日实现：** PHA 脚本（`pha_loop_*`、`pha_t0_*`、`pha_reflection_*`）+ 可安装 [`packages/harness_loop/`](../packages/harness_loop/) α CLI。  
> **接入指南：** [`examples/loop_reference_pha.md`](../examples/loop_reference_pha.md)。

在线 Core 保持 fail-closed，**不** 在回合中途自愈。演进是离线的：

```text
Telemetry / E2E JSONL
  → Ring R Reflection Critic (read-only attribution)
  → Loop A proposal (global recognition, e.g. catalog aliases)
  → promote_verdict (static + regression veto)
  → human PR (no auto-merge)

  → Loop B T0 ingest proposal (per-user facts)
  → gated apply (--confirm) → domain brief recompile
```

### 11.1 `failure_event/v1`（形态指引）

suite harvest 的最小字段（每个事件一个 JSONL 对象）：

| 字段 | 类型 | 必填 | 说明 |
|-------|------|----------|-------|
| `schema` | `str` | 推荐 | 例如 `harness.failure_event/v1` |
| `session_id` | `str` | yes | |
| `turn` | `int` | yes | |
| `check_id` / `error_code` | `str` | yes | 领域检查或 integrity 码 |
| `user_message` | `str` | yes | |
| `answer_head` | `str` | no | 截断后的回复 |
| `harness_profile` | `str` | no | |
| `signal` | `str` | no | harvest 后由 taxonomy 填写 |

PHA E2E / harness JSONL 行作为此形态的 **超集** 被接受。

### 11.2 `loop_proposal/v2`（alias / config 提议）

今日规范 `schema` 字符串：**`pha.loop_proposal/v2`**  
（suite 抽取落地时改名为 `harness.loop_proposal/v2`；迁移期间两者 MUST 都被接受。）

| 字段 | 类型 | 含义 |
|-------|------|---------|
| `schema` | `str` | 必须是 `pha.loop_proposal/v2` |
| `generated_at` | `str` | ISO 时间戳 |
| `stage` | `str` | 流水线阶段 id |
| `source` | `str` | Harvest / human_curated / … |
| `accepted_catalog` | `list[object]` | Tier-A catalog 行 |
| `accepted_schema` | `list[object]` | Schema 触发器（可选） |
| `slot_candidates` | `list[object]` | 未经人工评审 **不得** 把 Tier-C promote 进 catalog |
| `rejected` | `list[object]` | 显式拒绝 |
| `patch_ops` | `list[object]` | 类 JSON-patch 操作；路径受 static veto 限制 |
| `counts` | `object` | 汇总计数 |
| `suggested_regression` | `list[str]` | 例如 `EN07`、`EN08` |
| `notes` | `str` | 人工 / 机器备注 |

**Static veto（规范）：**

- 若 `schema` ≠ 已注册 proposal schema 则拒绝  
- 若存在 `code_review_items` 则拒绝（需要人工代码审查，不是 auto-promote）  
- 拒绝 `path` 落在领域 allowlist 之外的 `patch_ops`（PHA：仅 `/metric_aliases/…`）  
- 拒绝被当作 catalog promote 的 Tier-C `slot_candidates`

参考发射器：`scripts/pha_loop_alias_distiller.py` · 精选夹具：`scripts/fixtures/loop_alias_proposal_curated.json`。

### 11.3 `promote_verdict/v1`（门禁结果）

今日规范 `schema` 字符串：**`pha.loop_promote_verdict/v1`**

| 字段 | 类型 | 含义 |
|-------|------|---------|
| `schema` | `str` | `pha.loop_promote_verdict/v1` |
| `generated_at` | `str` | ISO 时间戳 |
| `proposal_path` | `str` | 输入 proposal |
| `proposal` | `object` | 汇总计数 / suggested_regression |
| `static_veto` | `list[str]` | 空 ⇒ static pass |
| `checks` | `list[object]` | 每项：`cmd`、`exit_code`、`passed`、`timed_out`、`output_tail` |
| `passed` | `bool` | `all(checks.passed) and not static_veto` |
| `notes` | `str` | 必须声明 dry-run / 无自动 merge |

**规范：** `passed: true` 只允许 **人工 PR**，从不自动 merge 或写 T0。

参考写入器：`scripts/pha_loop_promote_candidate.py`。

### 11.4 `eval_set/v1`（回归 goldens）

规范 `schema` 字符串：**`harness.eval_set/v1`**

可移植用例表，供离线 + 未来 live runners。规格：
[`docs/harness-eval-set-v1.md`](harness-eval-set-v1.md)。

| 字段 | 类型 | 含义 |
|-------|------|---------|
| `schema` | `str` | `harness.eval_set/v1` |
| `id` | `str` | 集合 id，例如 `pha.smoke.v0` |
| `domain` | `str` | Plugin 领域 |
| `version` | `str` | 该集合的 Semver |
| `cases` | `list[object]` | 每项：`id`、`turns[]`、`expects[]`，可选 `tags`/`locale`/`source` |

**离线 expects（CI selfcheck 规范）：** `non_empty_turn_text`、`min_turns`、
`tag_required`、`catalog_alias`、`alias_must_reject`。
**保留：** `live_non_empty_answer`、`live_locale`（离线忽略）。

参考：`pha/harness_eval_set.py` · goldens `evals/goldens/pha_smoke_v0.json` ·
`pha_alias_fuzz_v0.json` · `scripts/pha_eval_set_selfcheck.py` ·
`scripts/pha_eval_set_alias_fuzz_selfcheck.py`。

### 11.5 §11 的非目标

- 不要在用户可见聊天回合内跑 Reflection  
- 不要允许 Loop suite 补丁修改 `harness_core` 断言模块  
- 在 Stage B 抽取测过之前不要要求 PyPI `harness-loop`  
- 不要用 eval_set 替换完整 PHA E2E 题库（eval_set 是导出子集）
