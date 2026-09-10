# Harness Loop (Alpha) — 产品化计划

> **Language / 语言**：[English](official-loop-suite-alpha-plan.md) · 中文（本文）

> **目标：** 交付可对外宣布的 **α**（可安装 + CLI + selfcheck + toy attach）。  
> **分支：** `feat/official-loop-suite-alpha`  
> **本切片非目标：** Trace UI、live HTTP runner、HIO 第三域、把 PHA 脚本全量抽进包。

## 完成标准（LinkedIn-ready α）

| # | 标准 | 证据 | 状态 |
|---|-----------|----------|--------|
| 1 | 可安装包 | `pip install -e packages/harness_loop` | ✅ |
| 2 | CLI 入口 | `harness-loop version\|eval-check\|harvest\|promote\|adopt` | ✅ |
| 3 | 契约自检 | `pha_harness_loop_suite_selfcheck` + eval goldens | ✅ |
| 4 | 非 PHA attach | `examples/loop_reference_toy/` | ✅ |
| 5 | 边界已文档化 | README + plan + changelog | ✅ |

## α 架构

```text
harness_loop (portable)
  - eval_set validate (catalog_path injectable)
  - CLI + plugin delegate (PHA scripts remain reference impl)
  - schemas / version constants

PHA monorepo
  - scripts/pha_loop_*  (reference plugin, unchanged ownership)
  - pha/harness_eval_set.py  → thin adapter over harness_loop when available,
    else local fallback for CI without editable install
```

## 执行顺序

1. 包骨架 + 可移植 `eval_set`
2. 带 PHA 委托的 CLI（`HARNESS_LOOP_REPO_ROOT` / monorepo 探测）
3. Toy 领域 catalog + golden
4. Selfcheck + docs/changelog
5. PR
