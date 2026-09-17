# 交接 · 2026-09-17 · 对话穿戴「趋势/对比」证据配方（本窗 + 对照 → Manifest）

> **Language / 语言**：[English](handoff-2026-09-17-chat-wearable-trend-compare.en.md) · 中文（本文）

> 写给接替的 coding agent · **M1-P23 DONE 2026-09-17**（真机验收）  
> 触发对话：Mac 对话框「最近一周我的 HRV 和深睡的数据有什么变化？」+「与以往化验对比」→ 模型只引用 2026-09-11～17 均值，称「缺乏此前 HRV/深睡数据」无法谈趋势。  
> 维护者裁定：不靠 Loop / 不靠在线 LLM→harness 补取；按**证据形状**补一类配方（非单句 corner case）。  
> 真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.33** · 任务卡 **M1-P23** · FR-6.16

首条实施回复必须输出：

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

碰启动/重启再叠：`CONSENSUS_ACK: stability-plan-v2026-06-10 read`

---

## 0. 一句话

对话侧凡落入「变化 / 趋势 / 对比 / 以往」且指标为穿戴时，须在调 LLM **之前**由规则层装齐 **本窗汇总 + 对照侧**（均入 Numerics Manifest）；对照缺失则规则层/skip-LLM 披露不足。**禁止**只塞本窗均值却允许谈升降；**禁止**用 Loop 别名或在线 Reflection 改 Plan 补证。与事实卡 M1-P22（`assessment_compare`）同构，补的是 **chat 相对卡侧的缺口**。

---

## 1. 问题与判断（已冻结）

| 现象 | 判断 |
|------|------|
| 回复仅有近一周 HRV/深睡均值，称无历史无法判断升降 | 上游 **对照证据未进 Manifest（或未强制引用）**；模型「无法判断」是诚实症状，不是根因 |
| 库内长期有 HRV/睡眠历史；`wearable_only` 设计上挂 `WEARABLE_90D_SUMMARY` | 缺口更可能是 grain 绑死本窗后对照未入 Manifest / 未进 TASK，或续问搅乱 scope——需编码时用磁盘真源核实，不信 change-log 口头 |
| 「与以往化验对比」接在穿戴趋势后 | **已证伪（Step 0）**：会话用户句无此文；正文「### 与以往化验对比」= `presentation_filter` 将「纵向趋势对账」改写。**跨域 clarify（原 T3）降级/砍掉**，不为展现层 Bug 写拦截逻辑 |
| 能否靠环 R / Loop live harvest？ | **不能**。Loop 只管 catalog 别名；环 R 离线归因，**不可动 Plan**；在线 Core 不在回合中途自愈 |
| 能否让 LLM 发现缺数再反馈取数？ | **禁止**。方向盘不交给 LLM；与 harness 共识冲突 |

架构短答（维护者已同意）：问法无穷 ≠ 证据形状无穷。识别层压到少配方；本卡只立 **「趋势/对比 = 本窗 + 对照」** 一族。

---

## 2. 非目标（本刀禁止）

- **禁止**为「最近一周 + HRV + 深睡」写 Python 问句 `if` / 黄金一句补丁。
- **禁止**放宽 Numerics：模型口算「以往」或编对照均值却过审。
- **禁止**在线 Reflection / tool loop **推翻或重生成** `TurnEvidencePlan` 以补基线。
- **禁止**用 Loop A 别名提案「解决」对照缺失（别名不产生对照数）。
- **禁止**改事实卡 HTML 递进基线契约；本刀主战场是 **对话框 `/api/chat` 穿戴路径**（可复用 P22 编译器思想/模块，但不要把 chat 绑死 interpret-only API）。
- **不做**：跨域因果（睡眠分期 vs 某次 LDL「导致」）；新证据形状另开卡。
- **不做**：为过测放水「缺乏此前数据」检测的字符串匹配豁免。

---

## 3. 设计原则

```text
用户句 ──resolve──► metrics + focal_window + goal∈{lookup, trend_compare, …}
                              │
              goal = trend_compare │
                              ▼
         规则层重算：focal_stats + compare_stats（mean/n/窗界…）
                              │
                              ▼
         Numerics Manifest ⊇ 本窗原子 ∪ 对照原子（或 compare_insufficient）
                              │
                              ▼
         TASK：必须同时引用两侧；对照不足 → skip-LLM / 定账模板
                              │
                              ▼
              LLM 只许抄写 ──► Numerics 审计（仍 ⊆ Manifest）
```

1. **Evidence before LLM**：对照是一等证据，不是文风。
2. **形状验收，不金句验收**：任意（指标集 × 本窗 × 对比意图）→ Manifest 形状正确；selfcheck 至少 **2～3 组不同 grain/指标**。
3. **与 P22 同构、路径分立**：P22 = 评估要求 → interpret inject；P23 = 对话用户句 → chat Manifest。共享解析/重算库优先，禁止两套互斥口径。
4. **跨域 clarify（降级）**：Step 0 证实触发会话无真实「化验对比」用户句；原 T3 **不做**为本刀 DoD。若日后真有用户跨域问，另开卡。
5. **识别扩面仍归 Loop/catalog**：新口语只加别名触发「落入 trend_compare」；**不**改配方拓扑。
6. **同窗重叠硬拦（Grok/Gemini）**：对照重算若基线窗与本窗时间戳完全重合 → 跳过该候选、递进更长窗，或 `compare_insufficient`。
7. **强制策略 1 + 禁 skip + 防截断**：对照必须 Manifest 原子；`trend_compare` 禁 warehouse focus-skip；对照原子前置以免 600 字尾切。

---

## 4. 意图与触发契约

### 4.1 `goal_class` / 配方键（建议名）

| 键 | 含义 | 本卡 |
|----|------|------|
| `lookup` / 点查 | 某窗/某日读数 | 现状；不强制对照 |
| **`trend_compare`** | 变化 / 趋势 / 对比 / 以往 / 升降 / 比以前 | **强制本窗 + 对照** |
| `lab_*` | 化验卷宗 | 不走本配方；跨域见 §4.3 |

触发词表进 **Intent Catalog / schema**（中英），**禁止**散落在 `harness_plan.py` 硬编码长列表。编码前 `rg` 是否已有 delta/trend marker；有则复用扩面，无则加 catalog 字段。

示例（验收用，非穷尽）：「有什么变化」「趋势如何」「跟以往比」「比以前」「上升还是下降」「compared to before」「how has … changed」。

### 4.2 本窗（focal）

复用既有 `wearable_time_grain` / `HealthTurnScope.wearable_window`：近一周 → 7 日窗；近 N 天/周 → 同 grain。无显式窗 → 产品默认（与今日对话默认窗一致，**写进 TASK 披露**，勿 silently 换窗）。

### 4.3 对照侧（compare）默认策略

| 优先级 | 策略 | 说明 |
|--------|------|------|
| 1 | **递进个人基线**（90d→365d→all，对齐 FR-2.6）同指标 mean + n + `baseline_window` | 与事实卡「相对自己」一致；HRV 仍无人群参考 |
| 2 | 若实现成本更低：固定挂 **近 90 日同指标摘要**（已有 `WEARABLE_90D_SUMMARY` 槽）但 **均值/n 必须进 Manifest 原子**，不得只进散文块 | 散文块 alone 不足——审计与「可引用」以 Manifest 为准 |
| 3 | 可选增强（本期可砍）：等长前窗（本窗前一段等长） | 若做，须进 Manifest；不做则文档标明 backlog |

**样本不足**：写入 `compare_insufficient`（或等价）+ 实际 n；**禁止**伪造分位/趋势方向。用户可见：规则层模板「本窗有数、对照历史不足 n/…」，**优先 skip-LLM**。

### 4.4 跨域 clarify（**降级 · 非本刀 DoD**）

Step 0：触发会话无用户「与以往化验对比」；标题来自 `presentation_filter`。**不**为本刀实现三选一 clarify。真跨域续问另开卡。

---

## 5. Manifest / TASK / 失败形态

### 5.1 Manifest 必须含（形状）

- 本窗：指标值或窗均值、窗起止 day token、n（若适用）
- 对照：基线/90d 均值、`baseline_window` 或 90、n；或 `compare_insufficient` 标记（无对照数则模型不得写升降）
- **双 token**：本窗 N 与对照窗（如 90）可并存（对齐 P22）

### 5.2 TASK 要点

- 谈变化必须同时引用本窗与对照数字（字面 ⊆ Manifest）。
- 无对照原子时 **禁止**「上升/下降/稳定」类结论；应 defer 到规则层不足文案。
- 禁止 Markdown 列表（对话既有约束照旧）。

### 5.3 失败与诚实

| 情况 | 用户可见 |
|------|----------|
| 本窗无数 | 既有空窗 fail-closed / skip-LLM |
| 本窗有、对照不足 | 披露不足；不编趋势 |
| 本窗有、对照有 | 允许相关/伴随措辞谈相对位置；**弱因果**（禁「导致」） |
| 模型无视对照仍写「无历史」 | 属综合纪律；可用 post-audit 降级或后续薄约束；**本期不**为抓话术开 Python 表 |

---

## 6. 建议落点（编码时再 `rg` 确认）

| 区域 | 候选 |
|------|------|
| 意图 | `health_intent_catalog` / schema markers；`health_turn_resolver` / goal 合成 |
| 窗 | `wearable_time_grain.py`（复用，少扩） |
| 对照重算 | 优先抽共享模块（可从 `fact_card_assessment_window.py` / `fact_card` 基线逻辑复用），供 chat compose 调用 |
| Plan | `harness_plan.py`：`wearable_only` / `wearable_daily_review` 在 `trend_compare` 时保证对照槽 + Manifest 物化 |
| Compose | `chat_turn_compose` / numerics 构建：对照原子写入 |
| Clarify | `clarify_turns` + stage3f intent_scope 扩展（若尚未覆盖「化验 vs 穿戴」） |
| 自检 | 新脚本或扩既有 chat/numerics selfcheck（见 §7） |
| Flag | 建议 `PHA_CHAT_TREND_COMPARE=1`（默认开），便于回滚 |

**不改**：`packages/harness_core`；Loop promote；事实卡 HTML 默认基线。

---

## 7. 验收（形状，非单句）

至少三组（指标/窗不同，同一配方）：

| ID | 用户句（例） | 通过条件 |
|----|--------------|----------|
| T1 | 最近一周我的 HRV 和深睡有什么变化？ | 库有历史时 Manifest ⊇ 本窗 HRV/深睡 + 对照均值/n；正文不得称「缺乏此前…数据」；数字 ⊆ Manifest |
| T2 | 近 14 天静息心率趋势如何？ | 同配方；窗 token 14 + 对照 token；换指标仍过 |
| T3 | （降级）原「续问化验对比」 | **不做**为本刀验收；见 §4.4 |
| T4 | 本窗有、对照 n&lt;阈值 | 不足披露；无升降结论 |
| T5 | 点查「昨天深睡多少」 | **不**强制对照（防配方误触发） |

回归：`pha_fact_card_selfcheck`（P22 不回归）；相关 chat/numerics/ledger selfcheck；改 harness 后 bump `build_marker` + change-log。

人工：8788 真机复现触发对话，确认不再「无历史」。

---

## 8. 做事顺序（不要并行乱跳）

| 序 | 步骤 | 完成标志 |
|----|------|----------|
| 0 | 磁盘核实触发会话的 plan/slots/Manifest（telemetry 或复现） | ✅ 2026-09-17：Manifest 仅本窗 2 原子；90D 槽同窗噪音；无用户跨域句 |
| 1 | Catalog/schema：`trend_compare` 触发（无 Python 长列表） | ✅ selfcheck T1/T5 |
| 2 | 对照重算 + 写入 chat Manifest（策略 1、防重叠、前置防截断） | ✅ T1/T2；build `pha-v2.3.59` |
| 3 | TASK + skip-LLM/不足模板；禁 warehouse skip | ✅ 2026-09-17：`trend_compare_task_text` + `try_trend_compare_deterministic_reply`；T4；build `pha-v2.3.60-p23-task-insuff` |
| 4 | ~~跨域 clarify~~ | **砍掉（本刀）** |
| 5 | PRD §8 M1-P23 → DONE；change-log；build bump | ✅ 2026-09-17 真机验收盖章（见 change-log DONE 条） |

只本地 commit；**维护者说 commit 才 commit**；不 push。

---

## 9. 与 Loop / Reflection 的边界（写进 PR 说明）

| 机制 | 对本卡 |
|------|--------|
| Loop A / live harvest | 仅扩「变化/趋势」类口语别名 → 更容易落入 `trend_compare`；**不**产生对照数 |
| 环 R | 离线归因「对照未装」类失败 → 人审是否要改 catalog/触发；**不**在线改 Plan |
| Stage 3G | 仍只对齐已注入数字；**不可动 Plan** |

若实现后仍要为「近三周血氧变化」再开同构卡 → 说明做成了 corner case，驳回。

---

## 10. 开放项（本期可砍，登记勿做）

- 等长前窗对照（§4.3 策略 3）
- 模型「无视已注入对照」的专门后处理
- 将 chat 与 interpret 对照编译完全合并为单一 public API（可演进，非本刀 DoD）
- **残余（2026-09-17 真机）**：HRV 无对照原子时，模型偶发把本窗均值误标为「近90日」——另开 Numerics/措辞合规卡，不回滚本配方

---

## 11. 回滚

`PHA_CHAT_TREND_COMPARE=0` → 恢复改前 plan/compose 行为；文档保留配方定义供再开。
