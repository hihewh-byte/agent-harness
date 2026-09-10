# 15 分钟接入 harness-core

> **Language / 语言**：[English](attach-in-15-minutes.md) · 中文（本文）

你已有一个 agent。它偶尔会编造 ID、对调数字，或引用数据里不存在的日期。harness-core 是围在外面的 fail-closed 围栏：**Plan → Compose → Post-Audit**。若草稿引用了组稿前冻结证据之外的任何内容，裁决为 `ok=False`，你就拦截回复。没有回合中途自愈，也没有「让模型自己改」。

你实现 **一个对象、三个方法**。整段接入就是这些。

## 0. 先看它跑起来（60 秒）

```bash
git clone https://github.com/hihewh-byte/agent-harness
cd agent-harness
PYTHONPATH=packages/harness_core/src python examples/attach_minimal/run_demo.py
```

第 1 轮打印 `PASS`。第 2 轮（agent 编造工单 `TCK-9999` 和 `admin-root` 角色）打印 `FAIL-CLOSED: verdict.ok=False`，并向 `examples/attach_minimal/failures.jsonl` 追加一行。演示是内存里的 IT 工单助手 — 三个小文件，无 LLM、无 API key、无其它领域知识。

## 1. 契约（已冻结，v1）

你需要的一切都在一个模块：
[`packages/harness_core/src/harness_core/interfaces.py`](../packages/harness_core/src/harness_core/interfaces.py)
— 公开符号 ≤15 个，零第三方依赖。核心如下：

```python
from harness_core.interfaces import DomainAdapter, run_post_audit, emit_failure_event

class MyAdapter:                                # structural typing — no subclassing
    def build_plan(self, user_message: str):    # freeze evidence BEFORE composing
        return TurnPlanData(profile="...", tools_allowed=("..."), task_text=user_message)

    def extract_atoms(self, text: str):         # pull auditable tokens out of any text
        return re.findall(r"...", text)         # IDs, dates, amounts — your regexes

    def allowed_atoms(self, plan):              # the closed set a reply may cite
        return {...}                            # from YOUR database / API, not the LLM
```

一条不变量最重要：`extract_atoms` 对 allowlist 与草稿必须使用 **同一套规范化**，因为成员判定是精确字符串相等。两个方法放在同一个对象上，就不容易写岔。

## 2. 接到你的回合循环里

```python
adapter = MyAdapter()

plan    = adapter.build_plan(user_message)          # 1. plan (freeze evidence)
draft   = your_llm_call(user_message, evidence)     # 2. compose (your code, any model)
verdict = run_post_audit(adapter, plan, draft)      # 3. post-audit (fail-closed)

if verdict.ok:
    return draft
emit_failure_event("failures.jsonl", user_message=user_message, verdict=verdict)
return "Blocked: reply cited data outside the evidence base."   # your fallback
```

你会看到的违规码：`atom_not_allowed:{atom}`（编造/对调引用）以及 `tool_not_allowed:{tool}` 这类机器 diff 码（工具漂移）。空 allowlist + 抽出任意 atom ⇒ 拦截。拿不准就拦。

## 3. 失败记录免费喂给离线环

`emit_failure_event` 的行是 `harness-loop harvest` 消费内容的超集。有了若干真实失败后：

```bash
pip install -e packages/harness_loop
harness-loop harvest --e2e-jsonl failures.jsonl --out reports/loop/candidates.jsonl
```

Harvest → distill → 带门禁的 proposal → **人工 PR** — 环在运行时从不改写你的 prompt 或 catalog（[威胁模型](threat-model-v0.md)）。

## harness-core 永远不会做的事

- 从不编辑草稿、从不重试模型（fail-closed，不是自愈）。
- 从不回传、不需要网络、不绑定特定 LLM 厂商。
- 从不 import 你的领域代码；边界就是三方法 adapter。

问题 / 反馈：[Issue #1 — call for builders](https://github.com/hihewh-byte/agent-harness/issues/1)。
本仓库里的健康应用（PHA）只是同一契约的参考实现（`pha/harness_core_adapter.py::PHANumericsAdapter`）。
