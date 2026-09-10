# PHA Harness — 构建者总览（OSS）

> **Language / 语言**：[English](harness-builder-overview.md) · 中文（本文）

> 状态：面向外部读者的描述性总览 · 尚非独立 SDK  
> 基线：[harness-consensus-opus48-2026-06-08.md](harness-consensus-opus48-2026-06-08.md)

## 它是什么

PHA Harness 是本地 LLM 周围的 **控制平面**：

- Harness **规划**本回合允许哪些证据（`TurnEvidencePlan`）
- LLM 从注入的 Tier0/Tier1 块 **组稿**
- **C 层审计**检查用户可见数字是否与证据一致（否则降级答案）

这与编码 agent 常用的「LLM-first 工具环」相反。健康数据是 **不可核验的个人领域** — 编造 LDL 或 HRV 比拒答更糟。

```text
message → plan (profile / slots / forbidden / tools)
        → assemble Tier0 under budget (protected slots)
        → LLM compose
        → numerics / compare-table audit
        → SSE reply + HarnessBuildReport
```

## 对其它 agent 构建者可能有什么价值

| 想法 | 价值 |
|------|--------|
| Plan-before-LLM | 生成前冻结证据边界 |
| Tier0 受保护预算 | 关键事实不会被长上下文截掉 |
| Numerics / Compare 审计 | 个人数字可机器核验的诚实性 |
| plan_vs_actual 报告 | 对比计划注入 vs 实际注入 |
| Profile registry + CI | 运行时自省防止配置漂移 |

## 它今天 *不是* 什么

- 不是 `pip install agent-harness` 包（尚无 PyPI）— Core **vendored** 在 [`packages/harness_core/`](../packages/harness_core/)
- 不是完整双域 OSS monorepo — **tax** 以 [`apps/tax_agent/`](../apps/tax_agent/) 形式附带（仅 fixtures；无个人 xlsx）
- PHA 插件层并非领域无关 — 健康 slots / CompareTable 留在 PHA
- 不是多 agent swarm 框架

**已经完成的（Phase A）：** 在本地沙箱证明双域哲学；公开协议 v0 + 仓内 Core + 薄 adapter（`pha/harness_core_adapter.py`）。见 [harness-core-protocol-v0.md](harness-core-protocol-v0.md) 与 [harness-core-evolution-blueprint.md](harness-core-evolution-blueprint.md)。

可复用 **模式** 也在 `pha/harness_*.py`、`pha/numerics_manifest.py`、`pha/chat_turn_fsm.py`。发布独立 core 包是需求驱动（Issue #1），不是 `v0.4.0-beta.1` 的一部分。

双域对照（PHA ↔ tax_agent）：[harness-core-evolution-blueprint.md](harness-core-evolution-blueprint.md)。

## 关键入口

| 关注点 | 模块 |
|---------|--------|
| 回合 plan | `pha/harness_plan.py` |
| Tier0 组装 | `pha/harness_tier0_assembly.py` |
| Build report | `pha/harness_report.py` |
| Numerics 审计 | `pha/numerics_manifest.py` |
| 穿戴 compare 审计 | `pha/wearable_compare_table_v1.py` |
| 回合 FSM | `pha/chat_turn_fsm.py` |
| 可选 Core 桥 | `pha/harness_core_adapter.py` → vendored [`packages/harness_core/`](../packages/harness_core/) |
| 编排器 | `pha/chat_turn_orchestrator.py` |

离线 dry-run（无 LLM）— bootstrap 后约 1 秒：

```bash
bash scripts/bootstrap.sh
# or, if deps already installed:
python scripts/pha_harness_golden_run.py
# → RESULT: PASS — harness planned and assembled evidence without calling an LLM.
```

## 征求反馈

若你 clone PHA 是为了研究 harness：

1. 跑 `bash scripts/bootstrap.sh`（完整套件用 `bash scripts/run_selfchecks.sh`）
2. 浏览本文件 + consensus 基线
3. [开 Issue](https://github.com/hihewh-byte/agent-harness/issues)，写清：你想复用什么、什么挡住你、哪个模块最可移植

这些反馈决定未来抽取 `agent-harness-core` 是否值得成本。
