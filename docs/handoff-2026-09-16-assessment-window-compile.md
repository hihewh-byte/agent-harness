# 交接 · 2026-09-16 · 方案 B：评估窗口先编译进 Manifest（再解读）

> **Language / 语言**：[English](handoff-2026-09-16-assessment-window-compile.en.md) · 中文（本文）

> 写给接替的 coding agent · **仅文档；零生产代码直至维护者下令编码**  
> 触发对话：事实卡解读因 `unauthorized_window:14` 整段丢弃；维护者问「近 10 天 / 近 2 周」若数准是否该过。  
> 真源草案：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.32** · 任务卡 **M1-P22**

**状态：M1-P22 DONE（2026-09-16）。** 任意显式 N 泛化组装；90 与评估窗双 token；跟昨天比本期已做。build `pha-v2.3.57-p22-assess-window`。

首条实施回复必须输出：

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

---

## 0. 一句话

用户评估要求里的「近 N 天 / 近 N 周」**不得**靠放宽 Numerics、也不得靠模型口算；必须在调 LLM **之前**由规则层按 N 重算对比统计，写入解读注入卡与 Numerics Manifest，审计仍 fail-closed。HTML 可见卡的递进基线（90d→365d→all）**不变**。

---

## 1. 问题与证据（磁盘）

| 现象 | 证据 |
|------|------|
| 评估要求可写任意窗口口语 | prefs `assessment_prompt`；注入为 `USER_ASSESSMENT_PROMPT`（大纲，**不是**数值源） |
| 卡上基线只有递进档 | `pha/fact_card.py`：`90d`→`365d`→`all`；`baseline_window` 进 JSON |
| Manifest 窗口 token ⊆ 卡面 | `build_fact_card_numerics_manifest`：从 `baseline_window` 派生 `90`/`12`/`7` 等 |
| 模型写「近 14 日」→ 整段丢弃 | `data/fact_card_interpret/756b3bb7….json`：`unauthorized_window:14`；深睡/HRV 多数读数本可对账 |
| FR 已写死 | FR-6.8 窗口须与规则层逐字一致；FR-6.10 **用户评估要求不能解锁 S 级** |

维护者直觉「近 N 天只要数准就该过」在产品上成立，但**现行管道没有「准」的计算步骤**——审计只做白名单成员测试，不重算 10 日均值。

---

## 2. 非目标（本刀禁止）

- **禁止**放宽 `unauthorized_window`：任意「近 N」只要像窗口就过。
- **禁止**让 LLM 自算近 N 日均值/百分位后再「口头正确」蒙混。
- **禁止**改 HTML 可见卡的递进基线默认（P7 契约保留）；本刀只改**解读注入视图**（同 P20 exclusive 注入分层）。
- **禁止**评估要求解锁 S 级的其它通道（日期、小数、个人归属数）而不经 Manifest。
- **禁止** Python 指标名/药名硬编码表；窗口解析复用或扩展 `wearable_time_grain`，词表进 grain 模块/catalog，不散落 interpret。
- **不做**方案 A（accrual 今日空窗是否展示「最近一次」）——另卡。
- **本刀不做**「跟昨天比」点日对比编译（见 §8 开放项）；点日仍可作大纲时间锚，对比数字须另开或并入本卡二期。

---

## 3. 设计原则

```text
评估文本 ──parse──► assessment_window (N 或 fail)
                         │
                         ▼
              按指标规则层重算 compare_*（mean/min/max/n/…)
                         │
                         ▼
         解读注入卡 facts + Manifest tokens（含 N 与 compare 数）
                         │
                         ▼
              LLM 只许抄写 ──► Numerics 审计（仍 ⊆ Manifest）
```

1. **Evidence before LLM**（TurnEvidencePlan 精神）：窗口与对比数是一等证据，不是文风。
2. **双层卡**：用户可见 HTML = 递进基线；解读 inject = 可见卡 ∪ 本轮 `assessment_compare`（若有）。
3. **无窗口词 = 现状**：不发明 N；Manifest 仍只有递进窗 token。
4. **有窗口词但样本不足**：仍写入 `n` 与窗口 token；**不**伪造百分位/分档；copy 用「历史不足」类定性（对齐卡上 `unknown` 语义）。
5. **与 exclusive 正交**：先 `slice_fact_card_for_outline_inject`（点名行），再在 slim 卡上挂 compare；compare 只覆盖 inject 内指标。

---

## 4. 窗口解析契约

### 4.1 输入

仅 `assessment_prompt`（prefs / 本轮覆盖）。**不要**扫 FACT_CARD_CONTEXT 或 brief 找窗口。

### 4.2 识别（复用并扩展 `pha/wearable_time_grain.py`）

| 用户说法（例） | 规范 `window_days` | `spoken_tokens`（须进 Manifest） |
|----------------|-------------------|----------------------------------|
| 近 10 天 / 过去 10 日 / last 10 days | 10 | `10` |
| 近 2 周 / 过去两周 / last 2 weeks | 14 | `14`、`2`（若文案用「2 周」） |
| 近两周 / 近十四天 | 14 | `14`（及文案实际用到的「两」不进数字审计） |
| 近 7 天 / 近一周 | 7 | `7` |
| 近 90 天 | 90 | `90`（与递进 90d 同 token，仍须有 compare 行或显式挂载） |

须补 grain 能力（今日缺口）：

- `_ROLLING_N_RE` 已覆盖「近/过去/最近 + N + 天」；确认评估句路径走同一解析。
- **新增**「近/过去/最近 + N + 周」与「两周 / 2 weeks」→ `days = 7 * N`（N=2 → 14）。
- 固定词「近一周 / past week」→ 7（已有 `_ROLLING_WEEK_RE`）。

### 4.3 歧义与冲突

| 情况 | 行为 |
|------|------|
| 无滚动窗口词 | `assessment_window = null`；不挂 compare |
| 多个不同 N（「近 7 天和近 30 天」） | **fail-closed**：本轮不挂 compare；telemetry `assessment_window_ambiguous`；解读仍可用递进基线；TASK 不要求抄用户冲突窗口 |
| 同时有点日词与滚动窗（「今天 vs 近 14 天」） | 滚动窗胜出挂 compare；点日留作大纲（outline），**本刀不算点日差值** |
| N &lt; 1 或 N &gt; 365 | clamp 到 `[1, 365]` 并记 telemetry；或拒挂 compare（编码时选 **clamp + 披露实际 N**，禁止静默改用户语义却写用户原 N） |
| 只有「近一段时间」无数字 | 不挂；不猜 90 |

**披露**：inject 与 Manifest 一律用**实际采用的 N**；若 clamp，FACT_CARD_CONTEXT 一行说明「评估窗口按 N 日计」。

---

## 5. 规则层重算（每指标）

对 inject 卡内每个有 `value` 的 metric 行（`band=missing` 跳过 compare）：

1. 锚点日 = 该行 `day`（无则 `facts.as_of` / `calendar_day`）。
2. 用与 `pick_baseline_samples` **同一取值字段**，在 `[anchor - (N-1), anchor]` 内取历史样本（是否排除锚点当日：与现基线一致——现逻辑排除 `as_of` 当日，compare **保持同一约定**，避免两套口径）。
3. 写出：

```json
"assessment_compare": {
  "window_days": 14,
  "window_label": "14d",
  "source": "assessment_prompt",
  "token": "近2周",
  "spoken_day_tokens": ["14"],
  "per_metric": {
    "hrv_sdnn_ms": {
      "n": 5,
      "mean": 34.7,
      "min": 29.8,
      "max": 37.6,
      "percentile": null,
      "band": "unknown"
    }
  }
}
```

4. `n < MIN_BASELINE_N`（7）：`percentile`/`band` 置空或 `unknown`；**仍**把 `mean/min/max/n`（有则）与窗口 token 进 Manifest。
5. `n == 0`：该指标无 compare 数；窗口 token **仍**全局进 Manifest（允许模型说「近 14 日暂无足够对比样本」——定性，不编数）。
6. **禁止**从递进基线百分位或 90d 均值改贴标签成「近 14 日」。

小数位：与卡上 `_round_num` / 展示位一致，进 Manifest 双形态（`34.7` / `34.70` 若卡面有）。

---

## 6. Manifest / 审计 / TASK

### 6.1 Manifest

`build_fact_card_numerics_manifest(card)` 在既有递进基线条目之外：

- `window_day_tokens ∪= spoken_day_tokens`（如 `14`）。
- 为每个 `per_metric` 的 mean/min/max/n/percentile（非 null）建 `domain=fact_card`（或 `fact_card_assessment_compare`）条目。
- **不**删除递进基线条目（模型仍可能引用卡上「近 90 日」——若 inject 仍含 `baseline_window=90d`）。若产品希望 exclusive「只谈近 14 日」、禁止再写 90：另加 flag（默认 **仍保留** 90 token，避免误杀抄了可见卡 advice 的句子）。维护者编码前二选一，见 §8。

### 6.2 审计

- **不改** S/E/commons 分级哲学。
- `unauthorized_window:14` 在 14∈`window_day_tokens` 时通过。
- 仍拒：卡外个人小数、派生百分位、把 commons 整数贴到卡标签上。

### 6.3 TASK（解读 profile）

在第 2 条「窗口措辞须与卡一致」旁增一句（英 copy + zh 镜像）：

- When `assessment_compare` is present, rolling-window phrases and compare stats must match that block (and Manifest); do not invent another N; do not relabel progressive-baseline numbers as the assessment window.

不写「评估要求可解锁任意数字」。

### 6.4 缓存键

interpret cache key 增加 `assessment_window` 摘要（如 `14d` 或 `none`）+ compare 指纹（或并入现有 `card_digest`）。改评估窗口必须使缓存失效。

---

## 7. 管道落点（编码时）

| 步骤 | 建议落点 | 说明 |
|------|----------|------|
| 1 解析窗口 | `wearable_time_grain` 扩展 + 小函数 `parse_assessment_rolling_window(prompt) -> Optional[AssessmentWindow]` | 禁止在 `fact_card_interpret` 内写第二套正则 |
| 2 重算 | `fact_card.py` 旁路纯函数 `attach_assessment_compare(card, window, rows) -> card` | 只改 dict；不写 prefs |
| 3 接入解读 | `fact_card_interpret.py`：load 全卡 → exclusive slice → attach compare → manifest / context | HTML `/view` **不**调用 attach |
| 4 Manifest | `numerics_manifest.build_fact_card_numerics_manifest` | 读 `assessment_compare` |
| 5 TASK | `harness_plan.fact_card_interpret_task_text` | 短句；bump interpret prompt rev |
| 6 文案 | `fact_card_copy` 窗口标签（如「近 {n} 日」） | 无硬编码指标名 |
| 7 selfcheck | `scripts/pha_fact_card_selfcheck.py` 新段 | 见 §9 |
| 8 文档 | PRD FR-6.15 / change-log / 本交接标 DONE | bump `build_marker` |

Flag（可选）：`PHA_ASSESSMENT_WINDOW_COMPARE=1` 默认开；关则完全回到 v1.31 行为。

---

## 8. 编码前请维护者拍板

1. **递进 90 与评估 14 并存**：默认 Manifest **保留**两者 token（推荐），还是 exclusive 评估窗时从 inject 去掉 `baseline_*` 对比句？  
2. **样本是否排除锚点日**：与 P7 基线对齐（排除）还是「近 N 天含今日」？推荐 **与 P7 对齐**。  
3. **「跟昨天比」**是否并入本卡二期（点日差值编译），还是永远对话车道？  
4. N 上限 365 clamp 是否同意？

未拍板前编码按本文推荐默认实现，并在 PR 描述列出默认值。

---

## 9. 验收（编码后）

离线 selfcheck（夹具卡 + 假 assessment_prompt，不写盘 prefs）：

| ID | 输入 | 期望 |
|----|------|------|
| W1 | 「只看 HRV，对比近 14 天」 | Manifest 含 `14`；含规则层 14d mean；假回复「近 14 日」+ 该 mean → 审计过 |
| W2 | 同卡无评估窗 | Manifest **无** `14`；假回复「近 14 日」→ `unauthorized_window:14` |
| W3 | 「近 10 天」 | token `10`；假回复「近 2 周」→ 拒 |
| W4 | 「近 7 天和近 30 天」 | 不挂 compare（或 ambiguous）；不得只取其一却静默 |
| W5 | exclusive 点名 + 近 14 天 | inject 仅点名行；compare 仅这些行；HTML 全卡基线不变 |
| W6 | n&lt;7 | 有 n/mean（若有样本）无假百分位；定性不足可过 |

回归：现有 `pha_fact_card_selfcheck` 全绿；P15 黄金句路径不因无窗口词而变。

真机：评估框改「近 14 天」生成解读，不再因 `unauthorized_window:14` 丢弃；正文窗口与数字 ⊆ 卡面/Manifest。

---

## 10. PRD 草案（编码 PR 写入正文）

### FR-6.15（新）· 评估滚动窗口编译

用户评估要求中的显式滚动窗口（近/过去 N 天或周）在 `fact_card_interpret` 路径上须于 LLM 前解析并规则层重算对比统计，写入解读注入卡的 `assessment_compare` 与 Numerics Manifest（含窗口 day token 与 compare 数值）。HTML 可见卡递进基线不变。无显式窗口则行为同 v1.31。歧义多 N fail-closed 不挂 compare。评估要求仍不得直接解锁未入 Manifest 的 S 级数字。验收见交接 §9。

### FR-6.8 / FR-6.10 补一句

- FR-6.8：窗口与对比均值以卡上规则层（含本轮 `assessment_compare`）为准。  
- FR-6.10：「不能解锁 S 级」保留；本 FR 是 **先写入 Manifest**，不是审计放水。

### §8 任务卡

| ID | 里程碑 | 状态 |
|----|--------|------|
| **M1-P22** | 评估滚动窗口编译进解读 Manifest（FR-6.15） | `TODO` |

---

## 11. 回滚

- Flag 关闭或 revert attach/manifest/TASK 三处；HTML 无改则用户可见卡零回归。  
- 缓存目录 `data/fact_card_interpret/` 旧键可留；新键因 digest 变化自然未命中。

---

## 12. 相关路径（省 token）

- `pha/fact_card_interpret.py` · `pha/fact_card.py` · `pha/numerics_manifest.py`  
- `pha/wearable_time_grain.py` · `pha/harness_plan.py` · `pha/fact_card_copy.py`  
- `scripts/pha_fact_card_selfcheck.py`  
- 前序：[`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) · P7 [`handoff-2026-09-07-fact-card-assessment.md`](handoff-2026-09-07-fact-card-assessment.md)

---

**维护者意图摘要**：近 N 天要过审计 → 先编译进 Manifest；不放水；可见卡递进基线不动。
