# 交接 · 事实卡按钮式解读 v2 + 指标时效 + 勾选即所见（M1-P9.1 / P10 / P11 / P9.2 / P9.3）

> 写给接替的 coding agent · 2026-09-08 08:00 起笔，08:30 定稿 · 依据 9/7 23:20–23:30 浏览器验收 + 9/8 08:00 / 08:12 真机复测  
> 首条回复必须同时输出两行：  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> 真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.7**（§1.3 / §4.2 / FR-1.5 / FR-2.7 / FR-2.9 / FR-6 / §8 / §11）· [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) §2 / §5 / §6  
> **维护者已拍板**（2026-09-08 08:27）：§6 决定 11 = 方案 A，决定 12 = 去掉隐式展开；FR-1.5 / FR-2.7 v1.7 已写进 PRD。决定 7–10 按默认执行。
> 上一份交接：[`handoff-2026-09-07-fact-card-assessment.md`](handoff-2026-09-07-fact-card-assessment.md)（P7 / P8 已 DONE，P9 首版已落地但未 commit）

---

## 0. 开工前必读与现场状态

必读顺序：`pha-mandatory-reads.mdc` 全局两条 → PRD v1.6 → harness 共识 → `pha-ios-proactive-change-log.md` 最近三条 → `harness-change-log.md` 最近三条 → `rules/harness_profile_registry.generated.json`（看 `wearable_only` / `supplement_manifest` 的槽位声明方式）。

**工作区不是干净的。** `git status` 应显示：`pha/fact_card.py`、`fact_card_api.py`、`fact_card_html.py`、`fact_card_prefs.py`、`scripts/pha_fact_card_selfcheck.py`、四份 docs（PRD / change-log / roadmap / pha-fact-card）为 modified，`pha/fact_card_interpret.py` 与本文件为 untracked。代码改动是 M1-P9 首版 + 昨晚验收时的三处临时修补；docs 改动含 9/8 的 PRD v1.7（决定 11/12 已拍板）。**不要 stash、不要 checkout 丢弃、不要 commit。** 维护者说「commit」才 commit；本交接的 P9.1 完成后与首版一起提交，避免把过渡态审计逻辑留进历史。

三处临时修补（都在 `fact_card_interpret.py`，P9.1 要替换掉其中两处）：

1. 日期片段白名单：把 as_of 的年/月/日拆成 `2026` `09` `07` 塞进原子集 —— 治标，P9.1 用日期归一化替换。
2. harness `numerics_audit.passed=True` 时只拦 ≥100 的外来数 —— **这是放松审计，违背 PRD §4.2 与 harness 共识 §5.3，必须撤掉。**
3. `failed` 缓存允许再次 POST 触发重试 —— 保留。

`data/fact_card_interpret/` 里有一条 `done` 缓存，正文是「近 90 天…睡眠均值 7.6h（2026-06-10~2026-09-07）」，是在放松审计下通过的。P9.1 落地后**清空该目录**。

---

## 1. 昨晚验收发现了什么（证据）

浏览器全程：填写「我的评估要求」→ 保存回显 OK → 点「生成解读」→ <1s 显示「生成中」→ 第一次 `audit_rejected`（片段 `09` `07` `90` `06` `10`）→ 修补后 `done`。链路通了，但内容与口径有四个问题：

| # | 现象 | 根因 | 违反 |
|---|------|------|------|
| A | 解读只写一行「近 90 天睡眠均值 7.6h」，用户点名的**深睡**一字未提，基线含义没解释 | 走的是 `supplement_manifest` 路由（日志 `qtype=lifestyle`、WARN `matrix_gap_supplement_text_matches_wearable_regex`）；harness T0 manifest 只有一条 KV `wearable\|2026-06-10~2026-09-07\|睡眠均值\|7.6\|h`；事实卡 JSON 走 `extra_system_context` 侧通道，模型按「引用必须匹配 KV」只敢引那一条 | FR-6.2（输入应为 facts + 递进基线 + 参考层 + 评估要求） |
| B | 同一页面规则层写「近 12 个月 267 夜」，AI 区块写「近 90 天」；且 6/10–9/7 窗口内只有一两夜 HealthKit 睡眠，所谓「均值」就是今天这一夜 | `wearable_only` / 相邻 profile 的 Tier0 槽 `WEARABLE_90D_SUMMARY` 是固定 90 日窗口、不带 n | §1.3a 不割裂、FR-2.6 递进窗口 + 披露 n、n<7 不叫基线 |
| C | 卡侧补充审计用 `\d+` 抓片段，把日期的月/日和窗口天数当外来数误拒；放松后又能放过编造的 `n=45` 或 `深睡 2.3h` | 日期、窗口天数、样本数、测量值混成一类比对 | harness §2.3 C 层审计要可追溯，不得因表面流畅弱化 |
| D | 页面显示 `2026-09-07T15:29:08.651238+00:00`（本地其实 23:29）、`上次同步成功：2026-09-07T16:26:19`、`**睡眠均值**` 星号原样输出 | 渲染层直接吐存储格式；textContent 不解析 Markdown | 非红线，但 2.3 成功标准「诚实」要求用户看得懂 |

次要：缓存键 `(user, as_of, prompt)` 不含指标选择，改勾选后旧解读不失效；「模型不可用」只在 selfcheck 用假流验证过，未真停 Ollama；未在 iPhone Safari 上跑；未测跨日缓存失效；未测英文环境。

### 1.1 2026-09-08 08:00 维护者真机复测又暴露三件事

| # | 现象 | 证据 | 根因 |
|---|------|------|------|
| E | **静息心率勾选了但「无」**；卡顶「上次同步失败：08:00:46 · quantity · unreadable_value」 | 日志 08:00:41–46 四次 `POST /ingest/healthkit`：能量、HRV、（第三项）200，第四项 `rhr` 正文 `value:"" timestamp:""` → ingest fail-closed 400。`wearable_daily` 9/7 与 9/8 的 RHR 都是 NULL，9/6 = 60 | 两层：① Apple 的静息心率是**每日一次、滞后计算**的派生值，早上 08:00 健康 App 里还没有 9/8 的 RHR，捷径按「今天」过滤取到空集仍 POST，被正确地拒了；② 9/7 的 RHR 健康 App 里有，但 9/7 没跑数量捷径，且捷径**不带样本日期**（日志「empty timestamp; using received_at」），永远只能把值打到「今天」，昨天的值无路可进。事实卡按 PRD「当日行缺则空，不顶」如实显示「无」 |
| F | 08:00 的卡把**活动消耗 13.5 kcal 判 below**、**HRV 19.3 ms（一夜一两个样本）判 below**，并给「可考虑偏轻松安排」 | 卡 JSON `active_energy value 13.5 band below n=274` | **进行中的日**：累计型指标（步数、消耗）在早上只有零头，却与 274 个**整日**基线比；HRV 日均值也随白天样本变化。这是「用部分日冒充整日」，与 E 是同一个问题的两面：卡没有「指标时效语义」概念 |
| G | 用户把评估要求改成「重点静息心率与 HRV 和深睡…对今天运动训练有哪些建议，比如运动类型运动强度」→ 点解读 → **「未生成（审计未通过）」** | 缓存 `f1bdff52…` `violations: ['unauthorized_wearable_count:100']`；日志该轮 `route=wearable_only`、manifest 只有 `wearable\|2026-09-08\|今日HRV\|19.3\|ms`、`numerics=FAIL` | 这次是 **harness 自己的 C 层审计**拒的（不是卡侧补充审计），拒得对：模型写了 `100`（大概率是静息心率参考 60–100 或运动心率区间），而 100 既不在 manifest，也没放进 T1 披露块。深层原因仍是问题 A：参考范围只在侧通道，不是 manifest 的 T1 条目；TASK 没告诉模型「卡外数字只能进 T1 块」；用户要的「运动强度」本质上需要卡上没有的数字，产品上需要明确出口 |

E/F 不属于解读，是事实卡数字层的产品缺口，单独立卡 **M1-P10**（§5b）。G 由 P9.1 覆盖，并在 4.3 / 4.4 / 4.6 补三条。

### 1.2 2026-09-08 08:12 截图：勾选与卡上清单不一致；改勾选要重装捷径

| # | 现象 | 证据 | 根因 |
|---|------|------|------|
| H | 「我要看哪些指标」勾了 5 项（睡眠总时长 / HRV / 静息心率 / 深睡 / 活动消耗），「事实」却列了 9 项，多出 REM / 核心睡眠 / 在床 / 睡眠清醒；评估写「已选 9 项中 7 项有数」 | 注册表 5 个睡眠分期行都带 `fact_card.reveal_when_selected: [sleep_time_asleep, sleep_deep, sleep_rem]`；`fact_card_prefs.resolve_metric_specs` 在用户勾了其中任一项时把全部分期**追加**进卡 | M1-P6 为了「睡眠有则比」加的隐式展开。它让卡的指标集不再等于用户勾选，直接违反 FR-2.7「指标集由用户指定」，还把覆盖率分母从 5 抬到 9，评估层据此写「不综合」「缺项」。change-log 里没有维护者对此的决定记录，属实现选择 |
| I | 页面提示「改勾选后请在 Mac 重新生成捷径」；维护者希望改勾选后**重跑捷径即生效**，或**只刷新浏览器即生效** | `build_pha_ingest_shortcuts.py` 调 `shortcut_sync_specs("default")`，按**当前 prefs** 生成固定的 Find 动作；PRD FR-1.5 原文「捷径对用户已选且有 `shortcut_health_type` 的项，各 POST 一个当日数字」 | 捷径是按勾选快照生成的静态产物；iOS「查找健康样本」的类型参数只能在编辑器里静态选定，不能由变量决定，所以捷径不可能在运行时「按服务端给的名单任意取」。要么让捷径覆盖全集、卡按勾选过滤，要么让捷径带全集 Find 并在运行时按服务端计划用 If 门控 |

H 在共识内可直接改（§5c）；I 的方案 A 已由维护者 08:27 拍板，FR-1.5 v1.7 已写入 PRD（§6 决定 11）。

另两处顺带记下（P9.2 处理）：band 标签是**质量方向**（清醒 3.5h 显示 `below` 表示比基线差）而文案是**数值方向**（「明显高于」），同一行两种方向读者会懵；顶部「上次同步失败 · unreadable_value」把「今天健康 App 还没有静息心率」说成了同步失败。

---

## 2. 本次不可违背的约束（两份共识映射到这件事）

- **TurnEvidencePlan 先于 LLM**（harness §2.1）：解读必须有自己的 profile 声明槽位/禁用/工具，不能靳靠 user_message 文本去撞路由器。
- **Tier0 预算**（harness §2.2）：事实卡 manifest 与用户评估要求都是 Tier0 关键槽，不得被尾截断挤掉；评估要求上限 2000 字已定，超出 400。
- **C 层审计不得弱化**（harness §2.3 / §5.3；PRD §4.2）：只能加严、加维度（日期成为独立词类），不能加阈值放行。
- **不得裸奔**（PRD §4.2）：仍走 `stream_pha_chat_events` → `orchestrate_chat_turn_events`，不 import Ollama 客户端。
- **主动路径无 LLM**（PRD §1.3）：通知 body、`assessment`、定时任务不含解读；不预生成；`interpretation` 只在顶层、只在用户点过按钮后非空。
- **反硬编码**（宪法；`pha-mandatory-reads.mdc` 禁止项）：新 profile 走 registry 声明并 `--write` 重生；不为过审加 phrase 规则；参考范围仍在注册表。
- **fail-closed**：审计不过 → 整段丢弃，显示「未生成（审计未通过）」；绝不用模板文字冒充 AI。
- **变更流程**：P9.1 同 PR 更新 `harness-change-log.md`（声明 P0/P1/P2 类别、回滚、至少一条 harness 自检）**和** `pha-ios-proactive-change-log.md`；P9.2 / P9.3 只更新后者。重启只用 `bash scripts/pha_restart_accept.sh`。
- **不改** `packages/harness_core`、公开 README、`pha/healthkit_ingest.py` 睡眠路径。

---

## 3. 做事顺序

| 序 | 卡 | 性质 | 完成标志 |
|----|----|------|----------|
| 1 | **M1-P9.1** 专属 profile + 事实卡 manifest + 日期归一化审计 + 卡外数字 T1 出口 | 碰 harness（P2：Profile/Registry 扩展，主路由 deterministic 不变；审计只加严） | 复跑两次真机流程：解读提到用户点名的指标；窗口说法与规则层逐字一致；无「近 90」；日期只出现 as_of；运动强度类建议只以定性词或带来源 T1 块出现；selfcheck 与 harness 自检绿 |
| 2 | **M1-P10** 指标时效语义（滞后日值 / 进行中累计 / 滚动均值） | 只碰事实卡侧 + 捷径生成器 + ingest 空样本处理；**改一条冻结 PRD 行，需 §6 决定 7** | 早上 08:00 的卡能显示「静息心率 60 bpm（9月7日，最近一次）」并分档；消耗写「截至 08:00 累计，进行中，不分档」；捷径空集不再 POST 出 400 |
| 2' | **M1-P11** 勾选即所见 + 捷径全集同步 | 只碰事实卡侧 + 注册表 + 捷径生成器；FR-1.5 / FR-2.7 v1.7 **已拍板写入 PRD**，照做即可 | 卡上清单 = 勾选清单，覆盖率分母 = 勾选数；改勾选后刷新浏览器即切换；新勾选项的当日值在下一次捷径运行后出现，无需重装捷径 |
| 3 | **M1-P9.2** 本地时区 + locale 日期渲染 + 纯文本输出 + 缓存键 + band/文案方向统一 | 只碰事实卡侧 | 页面所有时间为本地分钟精度；中文「9月7日 23:29」；无 `**`；改勾选后旧解读消失 |
| 4 | **M1-P9.3** 真机与边界验收 | 验证为主 | iPhone Safari 全流程；停 Ollama 显示「模型不可用」；跨日缓存失效；en-US 格式 |

P9.1 与 P10/P11 互不依赖，可由两个 agent 并行。**P10 与 P11 必须由同一 agent 一次做完**：两者都改捷径生成器，维护者每次重装捷径都要 Mac 导出 + iPhone 替换，合成一次重装。P9.2 依赖三者。

每张卡：selfcheck → 官方重启 → 浏览器/真机看 → 同 PR 写 change-log → 改 PRD §8 状态。

---

## 4. M1-P9.1 具体做法

### 4.1 新 profile `fact_card_interpret`

在现有 profile 声明处（`harness_report.py` 的 profile 表，与 `wearable_only` 同级）新增，随后 `python scripts/pha_harness_profile_registry_generate.py --write` 重生 registry，diff 里必须能看到新 profile。

- `slots_tier0`：`TASK`、`NUMERICS_MANIFEST`、`FACT_CARD_CONTEXT`（新槽：事实卡精简 JSON，见 4.2）、`USER_ASSESSMENT_PROMPT`（新槽：用户评估要求原文，性质同 `SUPPLEMENT_BG` —— 用户口述，不是数值来源）。
- `slots_tier1`：空。
- `forbidden`：`WEARABLE_90D_SUMMARY`、`PATIENT_STATE_WEARABLE`、`PATIENT_STATE_LAB`、`USER_SNAPSHOT`、`SUPPLEMENT_BG`、`DOSSIER_*`、`GET_HEALTH_DATA`、`GET_TEMPORAL_HISTORY_DOSSIER`、`EVIDENCE_CATALOG`。**这一条直接解决问题 B**：harness 的固定 90 日摘要根本不进这条路径。
- `tools_allowed`：空。
- `legacy_question_type`：`WEARABLE`。

**如何进入这个 profile**：给 `stream_pha_chat_events` / `orchestrate_chat_turn_events` 增加一个显式 `profile_override` 参数，只接受 registry 里存在的 profile 名，否则忽略并 telemetry 记 `profile_override_rejected`。`fact_card_interpret.py` 传 `profile_override="fact_card_interpret"`；resolver 的 `infer_profile_hint` 被跳过。**默认不把该参数暴露在公开 `/api/chat` body 上**（见 §6 决定 4）。这是 TurnEvidencePlan 的正当入口，不是 phrase 规则。

`user_message` 改成固定短句（例如「请生成今日事实卡解读」），不再拼评估要求，避免文本泄入任何路由/分类器。

### 4.2 事实卡 → Numerics Manifest

新增一个 manifest 构建入口（放 `numerics_manifest.py` 或独立模块，由 profile 的 `NUMERICS_MANIFEST` 槽调用），输入是 `load_fact_card()` 返回的卡，输出与现有 `ManifestEntry` 同格式 `domain|anchor|metric|value|unit`：

- domain 用新值 `fact_card`（不要冒充 `wearable`，避免触发 `wearable_grain_source` 相关逻辑）。
- 每个已选且有值的指标：`fact_card|{as_of}|{label}|{value}|{unit}`。
- 每个有基线的指标：`baseline_mean` / `baseline_min` / `baseline_max` / `percentile` 各一条，anchor 用 `{baseline_earliest}~{as_of}`，metric 名里带窗口词（例如「睡眠总时长·近 12 个月均值」），另一条 `fact_card|{anchor}|睡眠总时长·基线夜数|267|nights`。
- 参考范围：T1 条目 `reference|-|{label}·参考下限|7|h` 与上限，`source` 进 metric 名或备注。规则：与 FR-2.8 一致，只对注册表有 `reference_range` 的指标。
- `reference_date = as_of`；`forbidden_dates` 留空。
- **`allowed_dates` 目前只收 `lipid` 域 10 位 anchor**（`numerics_manifest.py` 约 234 行）。扩成同时收 `fact_card` 域 anchor 里出现的所有 ISO 日期（as_of、baseline_earliest）。这是加严不是放松：以前 wearable 日期根本不进允许集也不审。

`FACT_CARD_CONTEXT` 槽放精简卡（as_of、calendar_day、stale、metrics、summary、advice），顶部一句「以下为唯一可引用数字与日期」。Tier0 预算：这一槽在 TASK 与 manifest 之后、评估要求之前；超预算时按 advice → summary → metrics 的顺序裁，**不得裁 manifest 与评估要求**。

### 4.3 TASK 文本（写在 profile 里，不写在 `fact_card_interpret.py`）

要点，措辞由执行者定：只能引用 manifest 中的数字与日期；每个指标的窗口说法必须与卡上完全一致（卡说「近 12 个月 267 夜」就不能说「近 90 天」）；日期只允许出现 as_of（P10 落地后加上各行的实际 `day`），其余用「今天」「近 N 个月 N 夜」等相对表达；必须回应用户评估要求点名的指标，若该指标当日无值要明说「今日无记录」（P10 后改为「最近一次是 X 日」）；输出纯文本、不用 Markdown 标记；禁止诊断/处方/剂量；结尾不重复免责（页面已有）；语言按 `response_locale`。

**卡外数字的唯一出口（针对问题 G）**：用户评估要求里常会要「运动强度」「心率区间」「多少步」这类卡上没有的数字。TASK 必须写明：任何不在 manifest 里的数字，只能出现在 `【参考标准】…（来源：…，请自行查证，非医疗建议）` T1 披露块内并给出来源；块外只能用定性词（低强度 / 中等 / 偏轻松 / 恢复日）。用户的评估要求**不能解锁**这条规则——它是用户口述，不是数值来源。这样 harness 的 `audit_disclosure_block` 与 `unauthorized_wearable_count` 都能正确放行/拦截，卡侧审计的「剥 T1 块再比对」也已兼容。

### 4.4 卡侧审计重做（`fact_card_interpret.py`）

> **2026-09-08 20:11 起被 [`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) §2–§3 取代**：本节「每个数字必须 ∈ 原子集」与「两道审计独立」两条已废止（假阳性：`SpO2`/`VO2max` 标签、`96.0`、科普整数；en-US 下 T1 必败）。以下保留作历史记录。

撤掉「≥100 阈值」和「日期片段白名单」，改为两步：

1. **日期步**：复用 `numerics_manifest._extract_normalized_dates`（已支持 ISO 与「2026年9月7日」中文式；若 P9.2 引入英文月名格式，在同一函数加英文解析，属加严）。归一化后的每个日期必须 ∈ {as_of, calendar_day, baseline_earliest…}，否则 `audit_rejected` / `unauthorized_date:<d>`。然后把这些日期串从正文里遮掉。
2. **数值步**：剩余正文（已剥 T1 块）中的每个数字必须 ∈ 原子集。原子集 = `fact_card_numeric_atoms(card)` ∪ 卡上实际使用的窗口天数（`baseline_window` 为 `90d`/`365d` 时的 90/365）∪ 文案常量 7、12（「n/7」「近 12 个月」）。**不再有任何阈值。** 不在集合里 → `audit_rejected` / `unauthorized_value:<t>`。

harness 侧 `numerics_audit` 只要 `passed=False`（任何 violation，不只 `unauthorized`）即拒。两道审计独立、都必须通过；卡侧审计是对 harness 审计的**补充维度**（窗口一致性、卡外日期），不是替代。

缓存记录新增字段：`harness_profile`、`numerics_audit`（完整对象）、`card_digest`，供 telemetry。

**失败态要把被拒的数字告诉用户**（本机数据，无隐私问题）：`GET …/interpret` 的 `failed` 响应保留 `violations`；页面写「模型写了卡上没有的数字（100），已整段丢弃，可重试」。同时把「我的评估要求」文本框的说明改成一句：「解读只能引用卡上的数字；运动强度、心率区间这类建议会用定性描述或带来源的参考标准给出」，把期望管理做在输入端。

### 4.5 缓存键

`sha256(user_id | as_of | card_digest | locale | assessment_prompt)`，其中 `card_digest` = 已选指标 id 序列 + 每指标 value/baseline_window/baseline_n 的稳定序列化哈希。改勾选、值变化、换语言都自动失效。

### 4.6 自检（`scripts/pha_fact_card_selfcheck.py` 扩展 + harness 侧至少一条）

事实卡侧（monkeypatch stream）：

- 卡窗口 365d，假回复写「近 90 天」→ `audit_rejected` 含 `unauthorized_value:90`。
- 假回复写卡上没有的 `2026-06-10` → `unauthorized_date:2026-06-10`。
- 假回复写「2026年9月7日」（= as_of 中文式）与 `7.6h`、`267` → `done`。
- 假回复带 T1 块且块内数字 = 注册表参考范围 → `done`。
- harness `numerics_audit.passed=False` 且 violation 是 `future_date` → 拒（验证不再只看 `unauthorized`）。
- 评估要求写「给运动强度建议」，假回复块外写「心率 120–140」→ 拒；改写成 T1 块「【参考标准】中等强度常见对应最大心率 64–76%（来源：ACSM，请自行查证，非医疗建议）」→ `done`；`violations` 原样进 GET 响应。
- 复现问题 G：假回复块外写「参考范围 60–100」而卡上 RHR 参考范围就是 60–100 → 仍拒（参考范围只能以 T1 块出现，这与 FR-2.8 一致）。
- 改勾选后 `current_interpret_key` 变化；旧缓存不命中。
- 不点按钮 `interpretation is None`；通知 body 与 `assessment` 无解读字样（已有，保留）。

harness 侧：registry `--write` 后 `python3 scripts/pha_chat_turn_fsm_selfcheck.py`、`pha_numerics_manifest_selfcheck.py` 仍 PASS；新增或扩展一条自检证明 `profile_override="fact_card_interpret"` 生成的 plan 里 `WEARABLE_90D_SUMMARY` 在 forbidden、`NUMERICS_MANIFEST` 条目数 = 已选有值指标数 + 基线条目数 + 参考条目数。

真机/浏览器：复跑两个真实流程。① 评估要求「重点看睡眠总时长和深睡」→ 正文出现「深睡」与「睡眠总时长」；基线表述与卡上「近 12 个月 267 夜」一致；正文无「90」；除 as_of 外无日期。② 评估要求用维护者 9/8 原文（静息心率 + HRV + 深睡 + 运动类型/强度）→ `done`；运动强度只以定性词或 T1 块出现；静息心率当日无值时明说；页面显示模型名。两轮日志都是 `route=fact_card_interpret`。

### 4.7 文档

- `harness-change-log.md`：条目声明 **P2（Profile/Registry 扩展）+ C 层审计加维度**；列 profile 槽位；回滚 = 删 profile 声明 + `--write` 重生 + 还原 `allowed_dates`。
- `pha-ios-proactive-change-log.md`：条目 + 撤掉昨晚「审计放松」的说明。
- PRD：FR-6 增两行（措辞见 §7），§8 M1-P9 备注改为「P9.1 DONE」。

---

## 5b. M1-P10 指标时效语义（回答「PHA 是不是直接不用昨天的数据」）

### 5b.1 结论先说

是的，现在的卡按 PRD §4.1「日历日当日行（缺则空，不顶）」执行，所以 9/8 早上静息心率显示「无」。这条原则的目的是**不把非当日的数字冒充当日**，这一点必须保留；但它把「不冒充」和「不显示」绑在了一起，对静息心率这类 Apple 每日滞后一次计算的指标、对早上只有零头的累计型指标、对本来就是多日均值的指标，都不成立。解法不是放弃原则，而是把「这个指标的值在时间上是什么」写进注册表，让卡按声明取值并**把实际日期/截至时间写在脸上**。

### 5b.2 注册表：`fact_card.temporal`（反硬编码，不在 Python 里 if 指标名）

每个 eligible 指标声明一个 `temporal` 对象；缺省 = 现行为（只取当日整日值），保证未改注册表的指标行为不变。

| `kind` | 含义 | 取值规则 | 卡上写法 | 建议归类 |
|--------|------|----------|----------|----------|
| `accrual` | 当日内累计，日终才完整 | 取当日行；若 `calendar_day == 今天` 则标 `partial_day=true`、附 `as_of_time`，**不分档**；基线只用整日 | 「活动消耗 13.5 kcal · 截至 08:00 累计 · 进行中，不分档」 | 步数、活动消耗 |
| `daily_lagged` | 平台每日一次派生、常滞后 | 在 `freshness_days`（默认 2）内回看最近一行；行的 `day` 原样输出，`freshness = same_day \| prior_day`；分档照常；超窗才「无」 | 「静息心率 60 bpm（9月7日，最近一次）· 高于你近 12 个月…」 | 静息心率；将来的 VO2max、步行心率均值 |
| `overnight` | 归属醒来日 | 现有睡眠逻辑不变 | 「睡眠总时长 6.2h」 | 睡眠各项；HRV 见 §6 决定 9 |
| `rolling_mean` | 指标本身就是多日均值 | 取 `window_days` 内日值均值并输出 `n_days`；基线用同样的滚动序列（同口径比同口径） | 「近 7 日均值 X · n=5」 | 用户提到的「过去 7 天均值」类指标；当前注册表尚无实例，先把 kind 定义好 |

通知导语的覆盖率随之细分：「7/9 有数，其中 1 项为前一日值，2 项进行中」。任何行 `day != calendar_day` 或 `partial_day` 都不得被写成「今日」——这是替代原 selfcheck 断言「today must stay empty」的新诚实不变量。

### 5b.3 捷径生成器（`scripts/macos/build_pha_ingest_shortcuts.py`）

- `daily_lagged` 指标：Find 改为 `Start Date is in the last 2 days`（同 T6.1 睡眠 D1 做法，Operator 1001 / 2 / 16384），Get Details 取 **Start Date 与值**，按样本 POST，`timestamp` 带真实日期；ingest 侧聚合器按日均值。不能再用一个不带日期的 Average。
- 所有数量捷径：Find 结果 **count = 0 时跳过 POST**（If 分支），不再发空值。这就消灭了 08:00:46 那个 400 和顶部「同步失败」。
- `accrual` 指标保持「今天 Sum」，ingest 已用 `received_at` 落时间，卡用它算 `as_of_time`。
- 生成后维护者需在 Mac 重新导出并在 iPhone 替换捷径（走既有流程）。

### 5b.4 ingest（不碰睡眠路径）

- 空值仍 fail-closed 400（原则不变），但回执 `error` 区分 `empty_sample`（捷径没取到）与 `unreadable_value`（值坏了），完整卡顶部文案对应写「健康 App 今日尚无静息心率」而不是「同步失败」。捷径修好后这条基本不会再出现，但要留着。
- 接受 `rhr` / `hrv_sdnn` 按样本带 `timestamp` 入库；`daily_key` 聚合按 `timestamp` 的本地日归日。

### 5b.5 事实卡（`fact_card.py` / `fact_card_prefs.py` / `fact_card_html.py`）

- `FactCardMetricSpec` 承接 `temporal`；`_metric_row` 按 kind 取值，输出新增字段 `day`（已有）、`freshness`、`partial_day`、`as_of_time`、`n_days`。
- `fact_card_numeric_atoms` 把各行 `day`、`as_of_time`（HH:MM）纳入原子集，否则 P9.1 的日期审计会把「9月7日」当卡外日期。
- 文案模板按 kind 分三套；`compose_assessment_summary` 的卡级综合：`partial_day` 与 `prior_day` 行是否参与投票 → 见 §6 决定 8。
- P9.1 的 manifest 构建：每条 entry 的 anchor 用该行实际 `day`，累计型 partial 行加 `·截至HH:MM`。

### 5b.6 自检

RHR 只在 D-1 有行 → 显示 D-1 日期、`freshness=prior_day`、有 band；只在 D-3 有行（超 2 天）→ 「无」；累计型今天有零头 → `partial_day=true`、band 不分档、文案含「截至」；`rolling_mean` 7 日 5 行 → 均值 + `n_days=5`；通知导语含「前一日」计数；不变量：任何 `day != calendar_day` 的行文案不含「今日」；捷径 plist：RHR Find 带 last-2-days 谓词与 Get Details Start Date，所有数量捷径含 count=0 跳过分支；ingest selfcheck：空值回执 `error=empty_sample`。

### 5b.7 文档

PRD §4.1 该行改为「按注册表 `temporal` 声明取值并明写实际日期/截至时间；超时效窗口才空；任何情况下不把非当日值标成当日」；FR-2.1 / FR-2.2 同步；§11 登记决定 7–9；`wearable-metric-registry-v1.md` 增 `temporal` 字段说明；`pha-ios-proactive-change-log.md` 条目；`pha-fact-card.md` 表格加「时效」一行。

---

## 5c. M1-P11 勾选即所见 + 捷径全集同步

### 5c.1 可能性分析

**问题 H（卡 ≠ 勾选）**：纯软件问题，无物理限制。去掉隐式展开即可。

**问题 I（改勾选后不用重装捷径）**，逐一排除：

| 路径 | 可行性 | 结论 |
|------|--------|------|
| 只刷新浏览器就有**新数据** | Mac 不能触达 HealthKit（PRD §1.4 数据物理事实），刷新只能重算账本里已有的数 | **不可能**拿到新数据；但对账本里已有历史的指标（如步数 9/4–9/5、zip 全部历史），刷新即显示，这一半天然成立 |
| 捷径运行时向 Mac 拿名单再「按名单 Find」 | iOS「查找健康样本」的类型是静态参数，不能由文本变量指定 | **不可能**做成通用循环 |
| **A. 捷径覆盖全集，卡按勾选过滤** | 生成器改为按注册表 `eligible ∧ shortcut_health_type` 全集出 Find（现为 4 项：步数 / 活动消耗 / 静息心率 / HRV；睡眠捷径本来就是整包），不再读 prefs；勾选只影响卡的显示与评估 | **可行且最简**。改勾选 → 刷新即切换；新勾选项当日值在下一次捷径运行（定时或手动）后出现；只有注册表新增了 `shortcut_health_type`（例如给血氧配上）才需要重装一次捷径。代价：每次多 1 个 Find（秒级），账本多存用户暂未看的指标——这正好符合 §1.3a「账本全部可比历史」，基线提前累积。**冲突**：FR-1.5 原文「对用户已选…的项」与 `pha-fact-card.md`「按当前勾选生成」 |
| **B. 全集 Find + 运行时按服务端计划 If 门控** | 捷径开头 `Get Contents of URL` 取 `GET /proactive/fact-card/prefs`，每个 Find 包一层 If「名单含该 id」 | 可行，不改 FR-1.5；但只满足「重跑捷径即生效」，不满足「刷新即生效」；未勾选的指标不入库，基线不累积；plist 复杂度翻倍、多一个网络失败点；Mac 不可达时整条捷径本来也会失败 |
| C. 等 M2 App 读 prefs 决定同步项 | App 阶段自然解决 | 不解当下 |

**维护者 2026-09-08 08:27 拍板 A**（理由见 §6 决定 11）。B 不再考虑。

### 5c.2 做法（按 A）

- **注册表**：删除 5 个睡眠分期行的 `fact_card.reveal_when_selected`；保留 `include_when_selected`（它只服务睡眠捷径整包同步，是数据层语义，不影响卡上显示）。`wearable-metric-registry-v1.md` 第 64 行随之删除或标 deprecated。
- **`fact_card_prefs.resolve_metric_specs`**：去掉「按 reveal 追加」分支；卡的指标集 = `sanitize_metric_ids(勾选)`，顺序按勾选。`FactCardMetricSpec.reveal_when_selected` 字段删除。
- **`healthkit_sync_plan.shortcut_sync_specs`**：不再读 prefs，返回注册表全集（`eligible ∧ shortcut_health_type ∧ ingest_key`）。睡眠 `shortcut_sleep_specs` 同理改为全包（现已接近）。Sum 先于 Average 的排序规则保留。
- **`build_pha_ingest_shortcuts.py`**：调用点不再传 user_id 的勾选语义；生成物名称不变；「显示结果」里列出本次同步了哪些指标。与 P10 的 last-2-days / count=0 跳过一起改，**一次重装**。
- **HTML**：`catalog` 提示改三态：「由健康捷径同步」「由睡眠捷径同步」「暂无捷径同步，仅展示历史」；页底说明改为「勾选只决定卡上显示与评估；数据由捷径按全集同步。改勾选后刷新即可；新勾选项的当日值在下一次捷径运行后出现」。修掉现在把「睡眠总时长」标成「仅展示，捷径暂不同步」的错误提示（它由睡眠捷径派生）。
- **通知导语 / 评估**：覆盖率分母自动变为勾选数；无需额外改。
- **P9.1 缓存键**已含指标摘要，改勾选后旧解读自动失效。

### 5c.3 自检

勾 5 项 → `facts.metrics` 恰好 5 行且顺序同勾选；`coverage_total == 5`；未勾的 REM 不出现在 facts / assessment / notification 任何字段；只勾「深睡」不再带出「在床」；`shortcut_sync_specs` 与 prefs 无关（改 prefs 前后返回一致）且等于注册表全集；生成的 plist 含 4 个数量 Find；`sleep_time_asleep` 的 catalog 提示为「由睡眠捷径同步」。现有断言「prefs save should keep catalog order」「sync plan must be selected ∩ quantity types」需改为新契约。

### 5c.4 文档

PRD FR-1.5 / FR-2.7 / §4.1 数据完整性段 / §8 / §11 / §12 **已于 v1.7 写好，不要再改措辞**；执行 agent 只需：完成后把 §8 `M1-P11` 状态 `TODO → DONE` 并填完成记录；`pha-ios-proactive-change-log.md` 加条目（类别：注册表 / 捷径生成器 / 事实卡 prefs；证据；回滚）；`pha-fact-card.md`「PHA 同步健康」段已重写为全集口径，落地后核对一遍与实际生成物一致；`wearable-metric-registry-v1.md` 第 64 行删除。M1-P5 历史条目不改。

### 5c.5 执行清单（P10 + P11 同一 agent，按序打勾）

前置：读完本文件 §0–§3、§5b、§5c；`git status` 与 §0 描述一致；**不 commit**。

1. **注册表**（`storage/registry/wearable_metric_registry.json`）
   - 5 个睡眠分期行删 `fact_card.reveal_when_selected`；`include_when_selected` 保留。
   - 按 §5b.1 给每个 eligible 指标加 `fact_card.temporal`（P10）。
   - `python3 scripts/pha_wearable_registry_selfcheck.py` 绿（若它校验 `fact_card` 字段集合，需同步接纳 `temporal`、移除 `reveal_when_selected`）。
2. **prefs 解析**（`pha/fact_card_prefs.py`）
   - `resolve_metric_specs` 删 reveal 追加分支；返回 = `sanitize_metric_ids(勾选)` 按勾选顺序。
   - 删 `FactCardMetricSpec.reveal_when_selected`；grep 全仓无残留引用。
   - `catalog_specs` 的提示字段改三态（§5c.2 HTML 项）；`derived_from_asleep_stages` 映射为「由睡眠捷径同步」。
3. **同步计划**（`pha/healthkit_sync_plan.py`）
   - `shortcut_sync_specs()` 不再调 `load_enabled_metric_ids`；返回注册表 `eligible ∧ shortcut_health_type ∧ ingest_key` 全集，Sum 先于 Average。
   - `shortcut_sleep_specs()` 同理改全包。
   - 签名保留 `user_id` 形参以免破调用方，但函数体不使用；docstring 写明「与勾选无关（FR-1.5 v1.7）」。
4. **捷径生成器**（`scripts/macos/build_pha_ingest_shortcuts.py`）
   - 数量捷径：全集 Find；`daily_lagged` 项按 §5b.2 取最近 `freshness_days` 天并带样本日期；`count == 0` 跳过不 POST。
   - 「显示结果」列出本次实际同步/跳过的指标。
   - 生成 → 本机导入验证 plist 可打开；**只交付一次**给维护者重装。
5. **ingest**（`pha/healthkit_ingest.py` 数量路径，睡眠路径不动）
   - 按 §5b.3 接受带日期样本、拒空值不变。
6. **事实卡**（`pha/fact_card.py` / `fact_card_html.py`）
   - 覆盖率分母自动 = 勾选数，确认无处再引用 reveal。
   - HTML 页底说明改为：「勾选只决定卡上显示与评估；数据由捷径按注册表全集同步。改勾选后刷新即可；新勾选项的当日值在下一次捷径运行后出现。」删掉「改勾选后请在 Mac 重新生成捷径」。
   - P10 的实际日期 / 进行中标注按 §5b.4。
7. **自检**（`scripts/pha_fact_card_selfcheck.py` + 捷径生成器自检）
   - §5c.3 全部断言 + §5b.6 全部用例；改掉旧断言「sync plan must be selected ∩ quantity types」。
   - `python3 scripts/pha_fact_card_selfcheck.py` PASS。
8. **重启 + 浏览器**：`bash scripts/pha_restart_accept.sh`；打开完整卡：勾 5 项 → 卡 5 行、「已选 5 项中 N 项有数」；取消勾「深睡」→ 刷新 → 4 行，不带出其它分期；勾「步数」→ 刷新 → 立即显示历史（9/4、9/5 有数），当日为「无」直到下一次捷径运行。
9. **文档**：§5c.4；PRD §8 P10 / P11 → DONE；change-log 两条（P10、P11 可合一条）。
10. **交付维护者**：一句话说明「需在 iPhone 替换『PHA 同步健康』一次；之后改勾选不再需要」。

---

## 5. M1-P9.2 具体做法（只碰事实卡侧）

### 5.1 日期与时间的三层规则

- **机器层永远 ISO 8601**：存储、`GET /proactive/fact-card` JSON、缓存键、审计比对不变。
- **展示层按 locale 渲染，用户不选日期格式，只选语言**。prefs 新增 `locale`（`zh-CN` / `en-US`，默认见 §6 决定 2），来源优先级：prefs > 请求 `Accept-Language` > 默认。同一值传给 `stream_pha_chat_events(response_locale=…)`。
  - zh-CN：`9月7日`；跨年才带年 `2025年12月31日`；区间 `6月10日–9月7日`；时间 `9月7日 23:29`。
  - en-US：`Sep 7, 2026`；区间 `Jun 10 – Sep 7, 2026`；时间 `Sep 7, 23:29`。
  - **任何语言禁止纯数字斜杠格式**（`09/07` 美英歧义），selfcheck 用正则断言 HTML 里不出现 `\d{1,2}/\d{1,2}`。
- **LLM 文本层优先相对表达**（已在 4.3 TASK 里要求）。

### 5.2 改动点

- `fact_card_html.py`：`generated_at`、`facts.ingest_last.at`、`facts.healthkit.last_timestamp`、页首 `as_of` / `calendar_day` 全部经一个 locale 感知的展示函数；时区用 Mac 系统时区（prefs 可加 `timezone` 覆盖，默认不加）；分钟精度。JSON 不变。
- 解读区块：模型名 + 「生成于 9月7日 23:29」；正文允许剥掉 `*`、`#`、反引号这类 Markdown 标记字符（只删标记，**不得改动任何数字或日期**），或依赖 4.3 的纯文本指令二选一，建议两者都做。
- 失败态按钮文字改「重试」；失败原因附一句人话并带被拒 token：`audit_rejected` → 「模型写了卡上没有的数字（100），已整段丢弃」；`model_unavailable` → 「本机模型未响应」。
- band 标签与文案方向统一：要么标签改成数值方向词（「高于 / 持平 / 低于」）而把好坏交给文案，要么标签保留质量方向但改成「偏好 / 持平 / 偏差」这类不含高低字眼的词。建议前者，与 P7 文案「高于你近 12 个月…」一致。
- 渲染 P10 新字段：`prior_day` 行日期用 locale 格式跟在值后；`partial_day` 行显示「截至 HH:MM」。
- 通知 body 里的 `as_of` 日期格式**本卡不动**（selfcheck 与捷径文案依赖 ISO），是否本地化放 §6 决定 5。

### 5.3 自检

zh 渲染含「9月7日」且不含 `T15:29`；en 渲染含 `Sep 7`；两者都不含斜杠日期；JSON `facts.as_of` 仍为 ISO；`interpretation.generated_at` 仍为 ISO（展示层转换不回写）。

---

## 6. 需要维护者拍板（附默认值，未回复即按默认执行）

| # | 决定 | 默认 |
|---|------|------|
| 1 | 90 日窗口冲突：A = 解读 profile 禁用 `WEARABLE_90D_SUMMARY`，只用卡上递进基线；B = harness 穿戴 T0 摘要整体改递进窗口并强制带 n | **A**。B 影响所有问答口径，另立 harness 卡 |
| 2 | `locale` 默认值 | **en-US（git / OSS）**。维护者本机 prefs 仍可 zh-CN。2026-09-08 覆盖原「默认 zh-CN」 |
| 3 | 卡侧第二道审计撤还是留 | **留**，但按 4.4 重做为日期/数值两步且无阈值。两份共识都不允许「因冗余而删审计」 |
| 4 | `profile_override` 是否暴露到公开 `/api/chat` | **不暴露**，仅内部调用；暴露需另立决定并登记 PRD §11 |
| 5 | 通知 body 日期是否本地化 | **P9.3 再定**；本轮 ISO 不动 |
| 6 | 真测「模型不可用」需要停 Ollama | 停 Ollama 不属 PHA 重启红线，但请维护者确认时间窗 |
| 7 | **改冻结行**：PRD §4.1「当日行缺则空，不顶」→「按注册表时效语义取值并明写实际日期；超窗才空；不把非当日值标成当日」 | **同意改**。原则「不冒充」保留，只解绑「不显示」 |
| 8 | 卡级综合投票是否接纳 `prior_day` / `partial_day` 行 | `prior_day` **接纳**（静息心率本来就是昨夜到今晨的量）；`partial_day` **不接纳**（零头不能投票） |
| 9 | HRV 的 `temporal.kind` | **`overnight`**：Apple Watch 的 SDNN 主要在睡眠中测，早上的值可视为「这一夜」；但注册表要写 `min_samples`（建议 2），不足时标「样本少，暂不分档」。若维护者更信任健康 App 的「当日均值」，改 `accrual`，代价是早上永远不分档 |
| 10 | `daily_lagged` 的 `freshness_days` | **2**；超过 2 天的静息心率对「今天怎么练」已无参考价值 |
| 11 | **改 FR-1.5**：捷径从「按用户已选生成」改为「按注册表全集生成，卡按勾选过滤」（§5c 方案 A）；同时 P10 让静息心率按「最近 2 天样本带日期」POST，触碰 FR-1.5「禁止 Find 原始列表」的字面 | **维护者 2026-09-08 08:27 拍板：同意 A。已写入 PRD v1.7 FR-1.5 / §11 / §12。** 原推荐理由：① 满足「改勾选后刷新即切换、重跑捷径即补数、不重装」；② 账本多存 1–2 个指标正合 §1.3a「全部可比历史」，未勾指标的基线提前累积；③ 反硬编码依旧——全集来自注册表不是代码；④ 每次运行多 1 个 Find，秒级。「禁止 Find 原始列表」的本意是防步数原始样本爆量，静息心率每天 1 个样本、睡眠 D1 已按同法通过验收，措辞已改为「累计型禁止 Find 原始列表；每日一次型可按样本带日期 POST」。方案 B 作废 |
| 12 | 去掉睡眠分期 `reveal_when_selected` 隐式展开 | **已替维护者选定：去掉。** 依据 FR-2.7「指标集由用户指定」，隐式展开让卡 ≠ 勾选、覆盖率分母失真、评估层据此说「缺项」；change-log 无维护者对该行为的决定记录，属实现选择，不构成共识冲突。想看分期就勾分期；睡眠捷径整包同步不受影响（`include_when_selected` 保留） |

---

## 7. 建议写入 PRD 的措辞（P9.1 同 PR，维护者确认 §6 后）

FR-6 表新增：

- **FR-6.8 证据源**：解读的唯一一等证据源是当日事实卡 JSON（facts + 递进基线 + 参考层）；以 `fact_card_interpret` profile 进入 harness，Tier0 只含 TASK / NUMERICS_MANIFEST（由卡生成）/ FACT_CARD_CONTEXT / USER_ASSESSMENT_PROMPT；`WEARABLE_90D_SUMMARY` 等固定窗口摘要禁止进入该路径。解读中任何窗口、n、日期必须与卡上规则层逐字一致。验收：selfcheck 注入「近 90 天」于 365d 卡 → 拒。
- **FR-6.9 日期与语言**：机器层 ISO 8601；展示层按 `locale` 渲染，禁止纯数字斜杠日期；LLM 文本优先相对表达，绝对日期仅允许 as_of；审计把日期作为独立词类归一化后比对。验收：中英两种 locale 的 HTML selfcheck；`unauthorized_date` 用例。

§4.2 追加一条：「让固定窗口穿戴摘要（`WEARABLE_90D_SUMMARY`）进入事实卡解读路径」。

FR-6 再加一行：

- **FR-6.10 卡外数字出口**：解读中任何不在事实卡 manifest 的数字（运动强度、心率区间、目标步数等）只能以 T1 披露块形式出现并注明来源；块外只允许定性描述。用户评估要求不能解锁该限制。验收：selfcheck 块外「120–140」→ 拒，T1 块内 → 过。

FR-2 新增一行（P10）：

- **FR-2.10 指标时效语义**：每个 eligible 指标在注册表声明 `temporal.kind ∈ {accrual, daily_lagged, overnight, rolling_mean}` 及窗口参数；卡按声明取值，行上必写实际 `day` 或 `as_of_time`；`accrual` 当日进行中不分档；`daily_lagged` 在 `freshness_days` 内回看并标「前一日」；超窗才空。通知导语按当日 / 前一日 / 进行中分计覆盖。禁止在 Python 里按指标名写特例。验收：§5b.6 全部用例。

**FR-1.5 / FR-2.7 v1.7 已于 2026-09-08 写入 PRD**（含 §4.1 数据完整性段、§8 五张新卡、§11 三条、§12 v1.7 行），执行 agent 不要重写。仍待执行 agent 随 PR 写入的只剩：FR-6.8 / 6.9 / 6.10（P9.1）、FR-2.10 与 §4.1「缺则空」行改写（P10，见 §5b.7）、§4.2 追加禁止项（P9.1）、§11 补决定 1、3、7、8、9、10 的落地记录。

---

## 8. 不要做的事

- 不要用「≥N 才拦」「只拦大数」之类阈值换取解读通过。
- 不要为了让模型提到深睡而在 user_message 里塞关键词去撞路由；用 profile。
- 不要在 `fact_card_interpret.py` 里自己拼系统提示替代 profile 的 TASK 槽。
- 不要给用户加「日期格式」选项；只有 `locale`。
- 不要改通知 body 的日期格式（本轮）。
- 不要把 `interpretation` 塞进 `assessment` 或通知。
- 不要为了让静息心率「有数」直接把昨天的值填到今天的行或去掉「不顶」断言；走 P10 的 `temporal` 声明并显示实际日期。
- 不要在 `fact_card.py` 里写 `if metric_id == "resting_heart_rate_bpm"`；时效语义只从注册表读。
- 不要让 ingest 接受空值并写 0 或 NULL 样本；空集在捷径侧跳过。
- 不要用别的隐式规则替代 `reveal_when_selected`（例如「勾了睡眠总时长就默认勾分期」写进 prefs）；卡 = 勾选，一个字都不多。
- 不要再给生成器留「按勾选生成」的开关或参数；FR-1.5 v1.7 只有一种口径：注册表全集。
- 不要为了「只同步用户关心的」在捷径里加 If 门控（方案 B 已作废）。
- 不要改 PRD FR-1.5 / FR-2.7 的 v1.7 措辞；那是维护者拍板的原文。
- P10 与 P11 的捷径改动不要分两次交付给维护者重装。
- 不要 push；不要在维护者没说「commit」前 commit。

---

## 9. 现场速查（2026-09-08 08:00）

- PHA `0.0.0.0:8788`，pid 见 `bash scripts/pha_restart_accept.sh` 输出；Ollama `127.0.0.1:11434` 在线，模型 `qwen2.5:7b-instruct`（`OLLAMA_MODEL`）。
- 库 `data/pha_storage.db`；`default` 9/8 08:00 卡：as_of 2026-09-08，覆盖 7/9；睡眠总时长 6.2h（365d n=267 below）、HRV 19.3 ms（n=274 below，一夜样本）、深睡 0.9h、REM 1.6h、清醒 0.1h、核心 3.7h（1/7）、活动消耗 13.5 kcal（below，进行中零头）；**静息心率无**（9/6=60，9/7、9/8 NULL）；在床无。顶部「上次同步失败 08:00:46 · quantity · unreadable_value」= RHR 空值 POST。
- 9/8 08:00 捷径四次 POST：三次 200 且「empty timestamp; using received_at」，一次 `rhr` 空值 400。捷径当前不带样本日期。
- `data/fact_card_interpret/` 三条缓存：9/7 23:29 done（近 90 天 7.6h）、9/8 08:01 done（近 90 天 6.9h）、9/8 08:04 failed `unauthorized_wearable_count:100`。P9.1 后全部清掉。
- 当前 prefs：已选 睡眠总时长 / HRV / 静息心率 / 深睡 / 活动消耗；评估要求为维护者 9/8 原文（静息心率 + HRV + 深睡 + 运动类型/强度）。
- 08:12 截图：卡列 9 项、勾选 5 项；多出的 4 项来自注册表 `reveal_when_selected`（`sleep_deep / sleep_rem / sleep_core / sleep_in_bed / sleep_awake` 均为 `[sleep_time_asleep, sleep_deep, sleep_rem]`）。数量捷径现有 Find：步数、活动消耗、静息心率、HRV 中的已选项；`spo2_percent` / `respiratory_rate` 无 `shortcut_health_type`，任何方案下都只能显示历史。
- 相关代码：`pha/fact_card_prefs.py`（`resolve_metric_specs` 的 reveal 追加分支、`FactCardMetricSpec.reveal_when_selected`）、`pha/healthkit_sync_plan.py`（`shortcut_sync_specs` 读 `load_enabled_metric_ids`）、`scripts/macos/build_pha_ingest_shortcuts.py` 第 671–673 行、`docs/wearable-metric-registry-v1.md` 第 64 行。
- 入口：`pha/fact_card_interpret.py`（`run_interpretation` / `start_interpretation` / `_unauthorized_numbers`）、`pha/fact_card_api.py`（`POST/GET /proactive/fact-card/interpret`）、`pha/fact_card_html.py`（`_interpret_status_html` + 轮询脚本）、`pha/fact_card_prefs.py`（`assessment_prompt`）。
- harness：profile 表在 `pha/harness_report.py`；registry `rules/harness_profile_registry.generated.json`；manifest 与日期归一化在 `pha/numerics_manifest.py`（`NumericsManifest.allowed_dates` 约 234 行，`_extract_normalized_dates` 约 511 行，`_audit_dates_and_citation` 约 751 行）；locale 在 `pha/response_language.py`（`resolve_response_locale`）；`response_locale` 参数已贯通 `chat_service` → `chat_turn_orchestrator` → `chat_turn_slots` → `chat_turn_compose`。
- 昨晚日志证据：`~/Library/Logs/pha/pha-8788.log` 中 23:24 与 23:29 两轮 `route=supplement_manifest`、`WARN: matrix_gap_supplement_text_matches_wearable_regex`。
- 浏览器验收 URL：`/proactive/fact-card/view?user_id=default&token=<PHA_INGEST_TOKEN>`，token 在 `~/Library/Application Support/pha/env-8788.sh`。
