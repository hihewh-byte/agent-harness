# 威胁模型 v0 — Harness Core + Loop

> **Language / 语言**：[English](threat-model-v0.md) · 中文（本文）

> 范围：本仓库内 vendored 的 harness 控制平面（在线 `harness_core` + 离线 Harness Loop）。
> 非范围：PHA 应用安全（web UI、存储加密、macOS 打包）— 另行跟踪。
> 状态：v0（审计计划 P1-4）。刻意控制在一页；仅在真实接入需要时再展开。

---

## 1. 信任边界

```text
                 ┌──────────────────────────────────────────────┐
   user turn ───▶│  ONLINE — 用户 agent + Domain Adapter         │
                 │  LLM 输出 = UNTRUSTED 输入                    │
                 │  harness_core: Plan → Compose → Post-Audit    │
                 │  fail-closed；无运行时自愈                    │
                 └───────────────┬──────────────────────────────┘
                                 │ failure events（JSONL，只追加）
                                 ▼
                 ┌──────────────────────────────────────────────┐
   offline ─────▶│  OFFLINE — Harness Loop（harvest → distill    │
   (cron/manual) │  → 1E gates → static veto → proposal）        │
                 │  仅 proposal；从不写入 catalogs               │
                 └───────────────┬──────────────────────────────┘
                                 │ loop_proposal / promote_verdict（JSON）
                                 ▼
                 ┌──────────────────────────────────────────────┐
                 │  HUMAN — PR 评审 + CI 门禁 + merge            │
                 │  进入 main / catalogs 的唯一写路径            │
                 └──────────────────────────────────────────────┘
```

三个信任等级，严格有序：

| 区 | 信任 | 永不信任 |
|------|--------|--------------|
| Online Core | 自己冻结的 plan（allowlist、row keys、FSM） | LLM 散文、OCR 文本、用户附件 |
| Offline Loop | 指向的文件系统输入（见 §3） | candidate 短语、harvest 到的消息 |
| Human PR | 已审过的 CI-green diffs | 任何自动生成的补丁，无论多绿 |

**设计不变量：** 数据只沿信任梯度 *向下* 流动，且经窄工件（failure JSONL → proposal JSON → PR diff）。离线侧任何东西都回不到 live turn。

## 2. 在线攻击面（harness_core）

**威胁 O1 — 组稿时数字/ID 对调。** LLM 替换或编造注入证据中不存在的指标值、日期或 row key。
*防御：* post-audit 成员检查 — 回复中每个 numeric atom 必须属于 plan 时冻结的 value/date 集合（PHA 参考实现：numerics manifest）。违规变成机器 diff 码（`compute_plan_vs_actual` 帧），回复被拦截或降级。
Fail-closed：没有「让模型自己改」的重试环。
*抽取说明：* diff-code 帧可移植（`harness_core.plan_vs_actual`）；值成员审计本身仍在 PHA 参考实现 — 其契约形态属于 P1.5-1。

**威胁 O2 — 阶段混淆。** 调用方在 Plan 之前调用 Compose，或双重审计。
*防御：* 回合 FSM（`validate_phase_transition`、`plan_precedes_compose`）；违规是硬错误，不是警告。

**威胁 O3 — adapter 走私。** 有缺陷/敌意的 Domain Adapter 在 planning 之后放宽 allowlist。
*防御（部分）：* `plan_vs_actual` diff 码暴露漂移；plan 是冻结数据（`TurnPlanData`）。
*残余风险：* adapter 在信任边界之内 — 恶意 adapter 可以在 plan 与 actual 两边撒谎。
Core 防御的是 *混淆* 的 adapter，不是 *敌意* 的。部署方负责 adapter 代码审查。

## 3. 离线攻击面（Harness Loop）

主威胁：**识别投毒** — 受攻击者影响的文本（聊天消息、OCR chrome、精心构造的 E2E JSONL）变成 catalog alias，导致后续回合误路由。

**威胁 L1 — 恶意/垃圾 JSONL 喂给 `harvest --e2e-jsonl`。**
Harvest 刻意很笨：只把 `passed:false` 行抽成 candidates；不写 catalogs。
被投毒的行只会变成 *candidates*，仅此而已。

**威胁 L2 — 经 distill 把垃圾 promote 上去。** 到达 PR 之前有三层有序防御：

1. **1E gates**（a: 时间/聚合/情感 denylist · b: 子串继承 · c: 窄域污染探针 · d: OCR/UI chrome 词如 "Query"/"Cancel"）。领域词表在 domain plugin；门禁帧（`harness_loop.gates`）有序且首次失败即决。
2. **Static veto**（`promote --static-only`）：拒绝带 `code_review_items`、patch ops 落在 `/metric_aliases/` 之外、或把 Tier-C slots promote 进 catalog 的 proposal。从不应用补丁。
3. **Human PR + CI**：唯一写路径。回归 goldens（`harness.eval_set/v1`，含 alias-fuzz）必须保持绿灯；consensus 门禁强制更新 changelog。

**威胁 L3 — gated adopt 绕过（Loop B / T0 每用户 facts）。**
`harness-loop adopt` 没有字面 `--confirm YES` 就拒绝；它委托给 T0 gated adopter，这是 Loop 中唯一写入用户可见 facts 的路径。任何 cron 都不应传入 `--confirm YES`。

**威胁 L4 — proposal 工件篡改**（distill 之后、promote 之前编辑 `loop_proposal` JSON）。
*防御：* static veto 在 promote 时重新校验形态与 patch 路径；人工 diff 评审看到的是最终工件。*残余风险：* 工件无密码学签名 — 当前规模（单维护者）可接受；若 proposal 跨越机器/信任边界再复审。

## 4. 明确非目标（v0）

- **无运行时输入过滤 / jailbreak 检测。** Core 对照冻结 plan 审计 *输出*；它不是语义护栏（见文档中的 Guardrails/NeMo 对比）。需要输入侧过滤的部署方应在前面组合外部工具。
- **无多租户隔离。** 假定单用户 local-first 部署；多租户是 RFC。
- **无工件签名 / 供应链证明**（见 L4 残余）。
- **不防护敌意 Domain Adapter 或敌意本机用户** — 二者都在 local-first 安装的信任边界之内。

## 5. 运维清单

- 永不从自动化运行 `adopt --confirm YES`。
- 把带非空 `static_veto` 的任何 `promote` verdict 当硬停止，不是警告。
- 把 `reports/loop/`（harvest/proposal 工件）留在 git 外 — 可能嵌入用户文本（已 gitignore）。
- 接入新领域时：垃圾词表（1E-d 等价物）是 *你的* 责任；可移植门禁帧出厂为空。

---

### 修订历史

| 日期 | 变更 |
|------|--------|
| 2026-07-15 | v0 — 初始威胁模型（审计计划 P1-4） |
