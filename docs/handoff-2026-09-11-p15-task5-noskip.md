# 交接 · 2026-09-11 · P15 下一刀：兑现 v1.19（去 skip）+ Qwen3 黄金句 20 轮

> **Language / 语言**：[English](handoff-2026-09-11-p15-task5-noskip.en.md) · 中文（本文）

> 写给接替的 coding / 验收 agent · 2026-09-11  
> 维护者意图：**新开对话继续**；本文件是唯一开工真源摘要。  
> 前序对话转录：[P15 评测与 TASK 判断](c87f5b03-8377-4253-ac9f-69c95b66631b)  
> 评测画布：[pha-p15-gold-meds-eval](canvases/pha-p15-gold-meds-eval.canvas.tsx)  
> 原始 JSONL：`reports/p15_eval/runs.jsonl`（40 轮完整）

**状态：P15 = DONE（2026-09-11 维护者盖章）。** 证据 `runs_v244_commons_gold10.jsonl`：`slot_named_ge2` 5/10 已接受。遗留项见 §8.3 / change-log，另开卡。本对话不 git。

首条实施回复必须输出：

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

触及启动/重启再叠：`CONSENSUS_ACK: stability-plan-v2026-06-10 read`。

真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.22** · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) **§19–§20** · change-log「P15 → DONE」条。

---

## 0. 一句话

管道已通（brief 含药物项A/补剂项B），黄金句 20 轮药物项A=0 是因为 **运行时 TASK 仍写 `skip it when unrelated`**，与 **已批准的 PRD v1.19「brief 在场不得整槽 skip」脱节**。下一刀 = 兑现 v1.19（改 TASK 第 5 条 + 导语），**不要**采纳 Gemini「强制另起注意事项专段」；改完只用 **qwen3:14b** 跑黄金句 20 轮。

---

## 1. 必读顺序（省 token）

1. 本文  
2. PRD FR-6.8 / FR-6.12（v1.19–v1.20 段）+ §8 M1-P15  
3. 3F RFC §19（槽契约）+ §20（脉络残行）  
4. 磁盘核对（见 §4）——**以磁盘为准，勿信 change-log 已落地**

可不读完整 40 轮正文；看画布或 `runs.jsonl` 摘要即可。

---

## 2. 硬红线（全程有效）

- TurnEvidencePlan 先于 LLM；用户可见数字 ⊆ Numerics Manifest。
- **禁止** Python 新增 phrase / metric / label / **药名**硬编码表。
- fail-closed；禁止换日换指标；**不得**翻转 Data > Context。
- **不得**扫全卡打翻 P9.5b；**不得**为黄金一句加 Python if。
- **不得** must 覆盖 / 缺行重试 / prefs∩ / 运行时 LLM 自愈 / 弱化 Numerics。
- brief 数字不得进 Manifest；`USER_CONTEXT_BRIEF_PROFILES` **不加** `fact_card_interpret`。
- **禁止**「点名训练则补剂相关」TASK 补丁。
- 未改 PRD/RFC 先改 TASK 禁止——但 v1.19 **已批准**去 skip；本刀是兑现，不是新发明。
- 临时换评估句只许内存 `assessment_prompt=`，**禁止写盘 prefs**。
- prefs 测完必须仍是黄金句 + 六项勾选（维护者已冻结）。

---

## 3. 当前状态板

| 卡 | 状态 |
|---|---|
| M1-P6 / P7 / P12 | DONE（占比参考关；**个人百分位仍在卡 JSON/Manifest**） |
| M1-P15 | **DONE**（2026-09-11） |
| M1-P20 | DONE*（Mac exclusive 过；iPhone 同网待验） |
| M2 | 未开 |

远程：`https://github.com/hihewh-byte/agent-harness.git`。agent 只本地 commit；push 由维护者执行。用户未要求 commit 则不要 commit。

运行时：launchd `gui/<uid>/com.personal-health-agent.pha-8788`；env `~/Library/Application Support/pha/env-8788.sh`（ingest token **不得回显**）；长解读 `export LLM_TIMEOUT_SECONDS=300`（`.env` 默认 120，dotenv 不覆盖已 export）。重启：`bash scripts/pha_restart_accept.sh`。默认模型目标：**qwen3:14b**。`OLLAMA_THINK=false`。16GB 勿两模型并行。

**注意**：`pha/build_marker.py` 磁盘上可能仍显示旧 build（如 `pha-v2.3.34-…`）；change-log 曾写 `pha-v2.3.38/39`。以实际改动后 bump 为准；UI 旧 build 需 restart accept。

---

## 4. 文档 vs 磁盘脱节（下一刀的直接靶心）

### 4.1 已批准（v1.19 / 3F §19）

| 做 | 不做 |
|---|---|
| brief 在场则 in-scope，**禁止整槽 skip** | 「点名训练则补剂相关」 |
| 导语去掉「无关则忽略」 | 药名表；解读轮加 `USER_CONTEXT_BRIEF` |
| **写入建议句，不另起编号注意事项清单** | 放水 Numerics；brief 数字进 Manifest |
| 零编数（禁 100−百分位等派生） | |

### 4.2 磁盘现状（2026-09-11 核对）

`pha/harness_plan.py` 第 5 条（`_FACT_CARD_INTERPRET_TASK` 与 `_FACT_CARD_INTERPRET_TASK_SHARED_TAIL` **两处**）仍为：

```text
… skip it when unrelated to the rows the assessment named.
```

`pha/fact_card_copy.py` 导语仍为：

- EN：`ignore anything unrelated to today's card`
- ZH：`与今日卡片无关则忽略`

→ change-log「P15 TASK 槽契约」条**声称已改**，代码**未兑现或已回退**。下一刀先修这两处，再跑测。

### 4.3 v1.20 已落地（保留）

脉络丢指标字段残行（`_is_lineage_field_stub` + `bg_lineage_stub_marks`）；空则整段不注入。selfcheck：`scripts/pha_chb_compiler_selfcheck.py`。不要回退。

---

## 5. 40 轮评测结论（已完成，勿重跑旧契约）

脚本：`reports/p15_eval/run_p15_batch.py`（可断点续跑）。条件：黄金 prefs、内存第二句、`LLM_TIMEOUT=300`、`OLLAMA_THINK=false`。墙钟约 80 min。

### 5.1 黄金句（各 10）

| | qwen3:14b | deepseek-r1:14b |
|---|---|---|
| 审计通过 | 10/10 | 10/10 |
| 训练/力量建议 | 10/10 | 10/10 |
| 点名药物项A | **0/10** | **0/10** |
| 点名补剂项B | 0/10 | 3/10（多为泛称补剂项B，不算注意事项过关） |
| 硬 Markdown / 编 85 / 超时 / think 泄漏 | 0 | 0 |
| 平均耗时 | ~50 s | ~162 s |

### 5.2 药-HRV 问句（内存传入，各 10）

问句：`最近HRV和静息心率都不是最好状态，是不是因为平时服用的药物和补剂对HRV与静息心率有什么影响？`

- qwen3：双点名对冲 6；只点名补剂项B 3；槽位跳过 1；审计 10/10。
- DeepSeek：更散；因果过度 5/10；硬 Markdown 2；1 轮 `unauthorized_value:96.0`（卡上 96.1）。

### 5.3 模型裁决（维护者已认可方向）

- **本轨道默认 / 下一验收：只用 qwen3:14b。**
- DeepSeek 不占下一轮名额（编数风险 + 因果过度 + 时延）。不必上升成全产品永久禁令。

---

## 6. 对 Gemini 建议的维护者裁决（已拍板，按此执行）

| Gemini 说法 | 裁决 |
|---|---|
| 先别在 skip 下再跑 20 轮 | **同意** |
| 根因是 `skip it when unrelated` | **同意** |
| 下一轮只用 Qwen3 | **同意** |
| 脉络残行刀保留 | **同意** |
| 干净版（不点药名/训练） | **同意方向** |
| **MUST synthesize a `注意事项` section** | **拒绝** — 与 v1.19「写入建议句，不另起编号注意事项清单」冲突；会诱清单体/Markdown |
| MUST cross-reference with today's metrics | **偏重，勿用原文** — 易放大因果过度、用 Context 牵 Data |
| 「DeepSeek 唯一不可用」 | **弱化** — 作 interpret 默认弃用即可 |

### 6.1 建议落地口径（编码时按此写英文 TASK；中英 PRD/RFC 同步一句）

**做：**

1. 删除 TASK / 导语中的 `skip it when unrelated` / 「无关则忽略」。
2. brief **非空** → 必须进入建议措辞与 caution（禁止整槽丢弃）。
3. 写入**建议句内**，不另起编号「注意事项」专段 / 清单。
4. 继续：不当数据、不复述/推断剂量。
5. **可选增量**（有 E5 证据）：禁止 definitive causal（`causes` / `leads to` / 导致·引起）；只用 correlational / monitor 措辞。
6. 零编数、禁硬 Markdown（`* # \``）保持。

**不做：**

- TASK 内举例药物项A / 补剂项B / 力量训练 / supplements/medications（连分类词都尽量不出现；引用槽名即可）。
- 「点名训练则补剂相关」。
- 强制独立 `注意事项` 标题块。

可参考（非强制定稿，agent 落地前可略收紧语气，但不得再引入专段 must）：

```text
5. When USER_BACKGROUND_BRIEF is present and non-empty, fold its self-reported
   items into the advice wording as cautions. Do not skip the slot. Never cite
   it as data; never restate or infer doses. Do not open a separate numbered
   precautions list. Use cautious correlational language only; forbid definitive
   causal claims (causes / leads to).
```

导语 `bg_brief_lead` 中英同步去掉「无关则忽略 / ignore unrelated」；CHB 投影若按当前 copy 重渲染，改 copy 即可生效。

---

## 7. 编码清单（下一刀）

1. `pha/harness_plan.py`：两处第 5 条（base + SHARED_TAIL）。  
2. `pha/fact_card_copy.py`：`bg_brief_lead` 中英。  
3. 若有 selfcheck 断言旧 skip 文案 → 更新夹具。  
4. 中英 PRD / 3F §19 若需补「弱因果禁令」一句则 bump 小版本；若仅兑现已写「不得 skip」可不升大版，但 change-log 必须记「磁盘兑现 v1.19 + 因果护栏」。  
5. `pha/build_marker.py` bump（如 `pha-v2.3.40-p15-noskip`）。  
6. 中英 `pha-ios-proactive-change-log` + `harness-change-log`。  
7. **不要**动 prefs；**不要**开 M2；**不要**改审计放水。

---

## 8. 验收：黄金句 20 轮（改完再跑）

### 8.1 冻结 prefs（测前测后核对）

评估句：

```text
评估今天整体身体状况，重点看今天的静息心率与HRV，睡眠的各项指标，用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度的建议，是否可以进行力量训练？
```

勾选六项：`sleep_deep`、`sleep_time_asleep`、`hrv_sdnn_ms`、`resting_heart_rate_bpm`、`active_energy`、`spo2_percent`。

### 8.2 跑法

```bash
set -a; source "$HOME/Library/Application Support/pha/env-8788.sh"; set +a
export LLM_TIMEOUT_SECONDS=300 PHA_AGENT_TIMEOUT_SECONDS=300
export OLLAMA_KEEP_ALIVE=10m OLLAMA_THINK=false
export PYTHONPATH="."
# 只用 qwen3:14b × 黄金句 20 轮；可改 batch 脚本或循环 run_interpretation
```

路径：`pha.fact_card_interpret.run_interpretation`（事实卡槽），不是 `/api/chat`。  
可复用/改编 `reports/p15_eval/run_p15_batch.py`（把 PER_CELL 调到 20、只跑 gold + qwen3；**勿写 prefs**）。

注入核对：brief 含药物项A与补剂项B；`notes_used` / `brief_source`（chb 或 live_notes 均可，关键是槽非空且有品类自述）。本批曾见 `live_notes` notes_used=1 但正文仍含药物项A+补剂项B——以注入内容为准。

### 8.3 P15 DONE 门槛（已盖章）

2026-09-11 维护者改口并盖章：

1. 零编数（无 unauthorized；无派生 85/21.5 类）。训练常识整数走 Manifest `population_commons` 域（整数 ∧ 同句无卡上指标标签）放行，不算编数。
2. 无硬 Markdown（剥后测）。
3. **黄金句**：建议句带出 brief 槽内 **≥2 个具体自述项**。药物项A∧补剂项B **不**再作为训练黄金句门槛。**5/10 可接受**（原建议 ≥8/10 降为非阻塞遗留）。
4. **meds-HRV 句**（若跑）：药物项A ∧ 补剂项B双点名门槛仍适用。
5. prefs 测后未变。
6. 不放水个人数据审计。

**已 DONE。** 遗留（另开）：审计小数/个别整数、`slot_named_ge2` 频率、prefs 勾选漂移、think 性能。

---

## 9. 明确不做

- 在 skip 仍在时重跑 20/40 轮「再确认一次」。  
- Gemini 原文「MUST synthesize 注意事项 section」。  
- DeepSeek 再占验收名额。  
- must 覆盖 / 缺行重试 / prefs∩ / 翻转 Data>Context / brief→Manifest / 解读轮加 USER_CONTEXT_BRIEF / 药名表 / 为过测拿掉卡上百分位 / 弱化 Numerics。  
- 未授权 commit/push。

---

## 10. 开工检查清单（新 agent 复制）

- [ ] 输出 CONSENSUS_ACK 行  
- [ ] `rg "skip it when unrelated" pha/harness_plan.py` 确认仍在 → 按 §6 改掉  
- [ ] 同步 `bg_brief_lead` 中英  
- [ ] selfcheck 相关脚本 PASS  
- [ ] bump build + change-log  
- [ ] prefs 仍是黄金句  
- [ ] qwen3:14b × 黄金句 20 轮；结果写入 `reports/p15_eval/`  
- [x] 按 §8.3 决定是否标 P15 DONE — **DONE（5/10 接受）**  
- [ ] 回复维护者：通过率 + 失败样本 + prefs 未变

---

## 11. 关键路径速查

| 路径 | 用途 |
|---|---|
| `pha/harness_plan.py` | TASK 第 5 条 |
| `pha/fact_card_copy.py` | `bg_brief_lead` |
| `pha/fact_card_interpret.py` | `run_interpretation` |
| `pha/fact_card_background_brief.py` | brief 构建 / 导语 |
| `pha/chb_compiler.py` | 脉络残行过滤（已落地） |
| `data/fact_card_prefs.json` | 黄金 prefs（勿改） |
| `reports/p15_eval/runs.jsonl` | 旧 40 轮证据 |
| `docs/prd-pha-ios-proactive-agent-v1.md` | v1.20 |
| `docs/stage3f-intent-resolution-completeness-rfc.md` | §19–§20 |

---

**维护者口令摘要**：P15 已 DONE（药物项A不作训练黄金句；5/10 槽内 ≥2 可接受）。遗留另开。本对话不 git。
