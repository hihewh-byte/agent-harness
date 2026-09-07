# PRD / 共识 · PHA → iOS 主动健康管理 Agent

> **状态**：跨 agent **产品共识真源**（强制）  
> **版本**：v1.6 · 2026-09-07  
> **确认行**：`CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> **变更日志**：[`pha-ios-proactive-change-log.md`](pha-ios-proactive-change-log.md)（本轨道代码/契约改动须同 PR 更新）  
> **上位法**：[`pha-pm-constitution.md`](pha-pm-constitution.md) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) · 非医疗器械声明（README）  
> **相关 RFC**：[`rfcs/rfc-device-ingestion-adapter.md`](rfcs/rfc-device-ingestion-adapter.md)（L0 ingest，零生产代码直至本 PRD 阶段开工）

本文档是「把现在的 Mac PHA **逐步**做成 **iOS App + 主动健康管理 Agent**」的唯一产品执行真源。  
**不替代** harness / 启动稳定性方案；冲突时：**数值诚实与 fail-closed 优先于「更主动」「更像教练」**。

公开 GitHub 仓 `agent-harness` 仍以 **可移植 harness** 为第一屏；PHA iOS 是 **产品轨道**，不是把仓库再改回「健康 App 壳」。拆独立产品仓属后续决策（见 §8），本阶段 monorepo 内推进。

---

## 1. 共识结论（冻结）

1. **产品目标**：用户打开（或被通知）的是一台 **主动、本地优先的健康管理 Agent**，而不是「先导出 zip 再在浏览器里问答」的研究原型。  
2. **演进方式**：Mac 上的 PHA（FastAPI + SQLite + harness + 可选 Ollama）在中长期仍是 **账本与审计内核**；iOS 先做 **采集 + 通知 + 展示壳**，再视算力决定是否把推理搬进手机。禁止幻想「一个 PR 把 Python 仓编译成 App」。  
3. **主动 ≠ 诊疗**：主动推送的是 **无 LLM 事实卡（数字层）+ 规则分档与固定模板建议（评估层）+ 用户自登记提醒**。禁止诊断口吻、禁止编造数字、禁止把一次 HRV 写成处方。**主动路径不得用 LLM 写评估**；开口问答属 M3。**「主动路径」= 未经用户当次触发就生成/推送的内容**（定时通知、卡级评估、预生成）。用户在完整卡上**点按钮**要求解读，等价于「开口」，走既有 chat harness（TurnEvidencePlan + Numerics 审计），不属主动路径（v1.6，见 FR-6）。  
3a. **主动 agent 与 Mac PHA 是同一个产品，不得割裂**：事实卡评估必须用到 Mac 账本里 **全部** 可比历史（zip 导入 + HealthKit），不能因窄窗口把多年数据判成「基线不足」。个人基线按可用量递进回看（90 日 → 365 日 → 全历史），并在卡上明写用了哪段；个人基线之外再给 **通用参考层**（Tier 1 披露制，只做「参考范围内/外」，非医疗判定），保证用户从第一天起就能读懂数字（v1.6，见 FR-2.6 / FR-2.8）。  
4. **数据物理事实**：Watch 数据只存在 **iPhone HealthKit**。实时/近实时 = iPhone 网关 → 本机（或用户自有组网）上的 PHA。Mac **不能**直连 Watch。  
5. **第一刀冻结**：打通 **HealthKit 样本 → Mac `wearable_data` / `wearable_daily`**。未绿之前不得宣称「今日主动 Agent 已上线」。

---

## 2. 问题与用户

### 2.1 现状痛点（有证据，非空想）

- 采集：仅 `export.zip` 全量导入；增量 HTTP 已 410。事实卡若做，新鲜度 = 上次导出。  
- 交互：用户开口才答；无日程、无通知。  
- 形态：浏览器 + 本机 Ollama，无法作为「戴手表就能用」的日常产品。

### 2.2 目标用户（v1）

- 维护者本人及少数会装 TestFlight / 捷径的试验者。  
- **不是** App Store 大众医疗用户（审核、责任、云同步均未准备）。

### 2.3 成功标准（产品，不是 vanity）

| 信号 | 达标 |
|------|------|
| 管道 | 不经 zip，Watch 侧 HRV/睡眠/步数能进 Mac 库，且带 `source=healthkit` |
| 主动 | 用户未打开聊天、也未打开 Mac 浏览器时，**iPhone 能弹出一条本地通知**，文案来自无 LLM 事实卡（规则分档 + 固定模板） |
| 诚实 | 卡片展示 `as_of`；过期则标明 stale，不假装「此时此刻」 |
| 红线 | 无新增诊断标题；无 manifest 外精确数值；非医疗器械文案保留 |

---

## 3. 产品形态（分阶段，禁止跳级）

```text
Watch → iPhone HealthKit → [捷径 | iOS App]
                              ↓ HTTPS/HTTP + token
                         Mac PHA ingest
                              ↓
                    SQLite 账本 + C 层审计
                              ↓
              事实卡引擎（无 LLM：数字层 + 规则评估层）
                              ↓ GET /proactive/fact-card
              iPhone 捷径 / 自动化 → 系统本地通知
              M2 App UI 展示同一 JSON；聊天（harness）← 用户开口才走 LLM
```

| 阶段 | 用户看见什么 | 计算在哪 |
|------|----------------|----------|
| **M0** | 无新 UI；库里有今日 Watch 数 | Mac |
| **M1** | **iPhone 本地通知**：事实卡数字 + 模板建议 | Mac 生成 JSON；iPhone 拉卡并通知 |
| **M2** | iOS App：授权、同步状态、**同一张事实卡**、提醒登记 | 采集在 iOS；账本在 Mac |
| **M3** | App 内接 **同一** 解读/问答接口（能力已由 M1-P9 在完整卡网页先落地；M3 只剩 App UI 接线） | 默认仍 Mac；端侧 LLM **另开任务卡** |
| **M4** | 可选：PHA 核心部分端侧化 | 仅当 M2 稳定且有明确算力方案 |

**v1 产品承诺止于 M2。** M3/M4 不是本 PRD 的 DoD。**M1-P9「按钮式解读」不是提前做 M3 的 App**，而是把 M3 的能力（用户开口 → Mac harness 回答）先挂在完整卡网页上；M3 因此缩成接线，顺序不变（触发仍是 M2 稳定）。

---

## 4. 范围

### 4.1 In scope（v1）

- `POST /ingest/healthkit` 及幂等写入、当日滚日表  
- iOS 捷径验证，随后薄原生 App（HealthKit + 同步 + 通知）  
- 无 LLM 每日事实卡：`as_of=MAX(day)` + **日历日当日行（缺则空，不顶）** + **递进个人基线（90 日 → 365 日 → 全历史，卡上标明所用窗口）**；规则分档  
- 事实卡两层：① 数字 / `as_of` / `stale` ② 规则分档 + **通用参考层（Tier 1 披露制）** + **固定模板建议**（非 LLM）  
- **我的评估要求**（用户自由文本，落本机 prefs）+ **按钮式解读**：用户点击后走既有 chat harness 生成、经 Numerics 审计、独立区块展示、按（日期 + 要求哈希）缓存；不进通知、不预生成  
- HRV 列语义纠正：zip 导入的 `hrv` 样本 `sample_id` 证明全为 Apple SDNN，`hrv_rmssd_ms` 列须改名/迁移为 SDNN 序列（单卡、叠 harness ACK）  
- M1 主动通道：**iPhone 快捷指令本地通知**（定时自动化拉 `GET /proactive/fact-card`）。APNs 远程推送不是 v1  
- 用药/补剂：**仅用户登记的时间表** → 本地通知  
- `as_of` / `source` 披露  
- 局域网或 Tailscale；ingest token

### 4.2 Out of scope（v1 禁止当需求塞进来）

- Watch 独立 App、运动中秒级教练  
- 云端保存健康数据、多租户 SaaS  
- 诊断、用药剂量建议、补剂疗效声称  
- 运行时 LLM 自愈、catalog 自动写入  
- 把 harness-core 产品叙事改回「本仓就是健康 App」（公开 README 第一屏不变）  
- 用截图 OCR 冒充实时采集  
- **主动推送 LLM 健康评估/建议**（属 M3 开口问答，或另立任务卡）  
- **LLM 解读的「每日自动预生成」**：会把 FR-6 重新变成主动路径；如需做，另立决定并登记 §11，默认不做  
- 让 LLM 解读绕开 chat harness 直接调 Ollama（「裸奔」）；解读中出现 facts / 基线之外的精确数字  
- APNs / 第三方推送云（v1 用 iPhone 本地通知）

### 4.3 与 zip 导入的关系

zip **保留** 作为冷启动/搬家。HealthKit 是增量通道。全量 zip **不删除** `healthkit|` 行；导入后按日重算，步数取各 source 合计的 max。细则见 change-log。

---

## 5. 功能需求

### FR-1 采集管道（P0 / 第一刀）

| ID | 需求 | 验收 |
|----|------|------|
| FR-1.1 | ingest JSON：`metric_type, timestamp, value, source=healthkit` | selfcheck 假数据入库 |
| FR-1.2 | 鉴权 token；无 token 401 | 单测或 selfcheck |
| FR-1.3 | 真机：捷径推送 Watch 已有指标 | 库中 `as_of` 与健康 App 同日、数值量级合理 |
| FR-1.4 | ingest 可写入的指标白名单（管道允许集，不是用户看见的死列表） | `hrv`, `hrv_sdnn`, `rhr`, `steps`, `sleep_hours`, `sleep_core`, `sleep_deep`, `sleep_rem`, `sleep_in_bed`, `sleep_awake`, `active_energy`。**M1-P8 后**：`hrv` 与 `hrv_sdnn` 均写入 `hrv_sdnn_ms`（Apple SDNN）；遗留 `hrv_rmssd_ms` 列保留但不进新写入。入睡总时长由分期相加 |
| FR-1.5 | **多指标入库**（数量型：步数 / 消耗 / RHR） | 捷径对用户已选且有 `shortcut_health_type` 的项，各 POST 一个当日数字；禁止 Find 原始列表 |
| FR-1.6 | **睡眠分期 + HRV SDNN**（另卡 M1-P6） | 见 [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md)。SDNN 不得写入 RMSSD 列。睡眠：分段落库、入睡 = 核心∪深∪REM 一次总并集、清醒 = 健康 App 原值不拆、在床只取 In Bed 样本（健康 App 无则 PHA 必须空）、醒来日由数据推导；**PHA 不判定某夜是否异常、不修正、不排除**，偏离个人基线时只出「请到健康 App 核对」提醒句；`入睡 + 清醒 ≤ 会话跨度`。验收：**只比健康 App 当天有、且用户已勾选的项**，各 ≤ ±10 分钟；健康 App 没有的项双方皆空算过，禁止为凑项硬编码必采列表（与 FR-2.7 一致）。产品真源 = **健康 App 展现**；M1 过渡可简化为单写入源（如仅 Watch），多源按系统优先级对齐属 M2 |
| FR-1.7 | **同步回执** | `GET /ingest/healthkit/last?user_id=` 返回最近一次成功/失败时间、指标、审计摘要；完整卡顶部显示「上次同步」。捷径 POST 成功响应含审计行，手机上可直接与健康 App 比对（呼应 §10「UI 必须显示上次成功时间」） |

### FR-2 事实卡引擎（无 LLM）

| ID | 需求 | 验收 |
|----|------|------|
| FR-2.1 | 读 `MAX(day)` + 当日行 + **递进基线窗口** 的 mean/min/max/分位 | 脚本输出 JSON，数字 ⊆ 查询结果；JSON 写出 `baseline_window`（`90d` / `365d` / `all`）与 `baseline_n` |
| FR-2.2 | HRV 等分档仅为规则（如 vs 分位），文案模板固定 | 无模型进程 |
| FR-2.3 | 过期：`as_of` 早于本地日历日则 `stale=true` | 卡片可见；通知须写「非今日」，禁止把末日标成今日 |
| FR-2.4 | 卡分两层：`facts`（数字）与 `assessment`（规则分档 + 模板建议 + 免责） | JSON 同时有两层；评估句不含诊断/处方 |
| FR-2.5 | JSON / 完整卡枚举 **用户已选** 的注册表指标；无记录写「无」，禁止省略、禁止用其他日顶 | 已选项都出现；未选不出现；默认五项可被用户改掉 |
| FR-2.6 | **卡级评估（v1.6 重写）**：覆盖率 + stale + **递进个人基线**分档 + 一句建议。基线窗口按可用量递进：近 90 日 ≥ 7 天用 90 日；否则近 365 日 ≥ 7 天用 365 日；否则全历史 ≥ 7 天用全历史；三者皆 < 7 才写「历史不足 n/7」。**同一定义才合并**：zip 时代与 HealthKit 的睡眠总时长/深/REM/清醒并集口径一致，视为同一序列；`sleep_core` / `in_bed` 历史为空就诚实写「无历史」。卡级综合三档（偏轻松 / 持平 / 偏好）由睡眠总时长、HRV、静息心率对个人基线的分位投票；任一缺项则写「不综合」而不是猜。分析 = 相对自己，不是 LLM 长文 | `assessment.summary` 含「相对你近 12 个月 268 夜」式的窗口说明；`baseline_short` 只在三级窗口都 < 7 时出现；selfcheck 覆盖 90d 空 → 365d 命中 |
| FR-2.7 | 指标集由用户指定，禁止 Python 硬编码死列表 | `GET/PUT /proactive/fact-card/prefs`；完整卡底部勾选；落 `data/fact_card_prefs.json`；允许集 = `wearable_metric_registry.json` 的 `fact_card.eligible` |
| FR-2.8 | **通用参考层（Tier 1 披露制）**：个人基线之外，对 **有人群参考意义** 的指标给一行参考范围内/外，格式沿用 `manifest-tier-v1` 的 T1 披露块：`【参考标准】<描述>（来源：<指南/组织>，请自行查证，非医疗建议）`。参考范围是 **数据**，放注册表 `fact_card.reference_range`（低/高/单位/来源），Python 不写死数字。v1 适用：睡眠总时长、深睡占比、REM 占比、静息心率、步数；**不适用**：HRV 绝对值（个体差异过大，只跟自己比）、清醒、在床 | 完整卡每个适用指标多一行参考句；数字 ⊆ 注册表；`fact_card_numeric_atoms` 把参考范围也纳入原子集；非医疗措辞；HRV 无参考句 |
| FR-2.9 | **我的评估要求**：完整卡有一个自由文本框，用户写「我想重点看什么 / 用什么口气 / 我在意的目标」，落 `data/fact_card_prefs.json` 的 `assessment_prompt`（本机、不出设备圈）。v1 只做 **保存 + 回显**，规则层不解析它（规则层不会因它变），它是 FR-6 解读的输入 | `GET/PUT /proactive/fact-card/prefs` 多一个字段；刷新回显；空字符串合法 |

### FR-3 主动触达

| ID | 需求 | 验收 |
|----|------|------|
| FR-3.1 | 每日一次（可配置时刻）生成事实卡并通知 | 用户未开聊天也能收到 |
| FR-3.2 | 提醒只来自用户登记表 | 无登记则无吃药/补剂项 |
| FR-3.3 | 通知文案含非医疗免责短句 | 固定字符串，非法条长文 |
| FR-3.4 | **M1 通道 = iPhone 本地通知 + 打开完整卡**：捷径 `GET /proactive/fact-card` 后短通知，再 `打开 URL` → `GET /proactive/fact-card/view`。每日用「快捷指令」自动化定时跑。不是 Mac 通知中心，不是 APNs | 锁屏能看到截至/覆盖率；Safari 能看到完整清单与评估；底部能改指标 |
| FR-3.5 | 锁屏正文只做导语。完整事实与评估只在 HTML/JSON。禁止靠加长通知正文硬撞 iOS 截断 | 通知含 `open_path`；完整卡数字 ⊆ JSON |

### FR-4 iOS App 壳（M2）

| ID | 需求 | 验收 |
|----|------|------|
| FR-4.1 | HealthKit 授权、服务器 URL、token、上次同步 | 设置页可改 |
| FR-4.2 | 前台「立即同步」 | 等价于捷径成功路径 |
| FR-4.3 | 展示最新事实卡 | 数字与 Mac 脚本一致 |
| FR-4.4 | 后台尽力同步 | 允许漏；须暴露失败原因（不假装成功） |

### FR-5 问答（沿用，不作为主动主路径）

现有 harness 聊天可继续跑在 Mac。主动路径 **不得** 为了「更聪明」绕过 Numerics 审计。App 内聊天属 M3。

### FR-6 用户触发的 LLM 解读（M1-P9 · 不是主动路径）

| ID | 需求 | 验收 |
|----|------|------|
| FR-6.1 | **触发**：仅用户在完整卡点「生成解读」。通知、卡级评估、定时任务 **不含** LLM 文字；不预生成 | 未点按钮时 JSON/HTML 无解读区块；日志无 LLM 调用 |
| FR-6.2 | **输入**：当日 `facts` JSON + 递进基线摘要（含窗口与 n）+ 通用参考层 + 用户 `assessment_prompt`。Mac 账本全部历史对 harness 可见（这是「不割裂」的落点） | 请求体只引用 facts / 基线 / prefs，不另查库编数 |
| FR-6.3 | **路径**：复用既有 chat harness（`/api/chat` 同一 `chat_service` 管线：TurnEvidencePlan → Compose → Numerics 审计），**禁止** 新开裸 Ollama 调用。输出中的精确数字必须 ⊆ facts ∪ 基线 ∪ 参考范围；否则整段丢弃，显示「未生成（审计未通过）」 | selfcheck：注入含外来数字的假回复 → 被拒；含 T1 块 → 通过 |
| FR-6.4 | **展示**：独立区块「AI 解读（实验）· 非医疗建议」，位于规则评估之后，不混排、不替代规则层；必须显示生成时间与所用模型名 | HTML 两块分离；规则层文案与未点按钮时逐字相同 |
| FR-6.5 | **时延**：本机 Ollama 一轮 30–170s（既有 e2e 记录）。网页必须 **异步**：点后立即返回「生成中」，结果按 `(user_id, as_of, sha256(assessment_prompt))` 缓存到本机 `data/`，刷新即见；同键重复点击复用缓存，不重复调 LLM | 点击后 HTTP < 1s 返回；缓存命中不产生 LLM 日志 |
| FR-6.6 | **fail-closed**：Ollama 未启动 / 超时 / 审计拒绝 → 区块显示原因，规则层照常；绝不回退成「模板文字冒充 AI」 | 停 Ollama 再点 → 区块写「模型不可用」，其余卡不变 |
| FR-6.7 | **M3 关系**：M2 App 的「解读」按钮调 **同一** 端点，不另写逻辑 | M3 任务卡只含 UI 接线 |

### 5.1 事实卡内容契约（v1.3 · 完整卡必须遵守）

主动通道不是「有数的那一项甩出去」。用户要看的是 **自己选定的事实清单 + 评估/建议**。主动路径的分析 **只允许** 规则：相对个人 **递进基线**（90 日 → 365 日 → 全历史）+ 通用参考层（Tier 1 披露）；禁止 LLM 写评语。LLM 解读只在用户点按钮后出现在独立区块（FR-6）。

| 块 | 必须出现 | 禁止 |
|----|----------|------|
| **事实** | 用户已选指标都出现：有数则写数字+单位，无数则「无」；`截至 as_of`；stale 写「非今日」 | 用昨日顶今日；编未入库数字；把未选项硬塞进卡 |
| **评估** | 覆盖率（已选里几项有数）；缺项点名；每项写 **基线窗口 + n**（如「相对你近 12 个月 268 夜」）；三级窗口皆 n&lt;7 才写「历史不足 n/7」；否则低于/持平/高于个人分位；卡级综合三档或「不综合」 | 诊断、病因、病理标题；因 90 日窗口为空就宣称「基线不足」 |
| **参考** | 注册表有 `reference_range` 的已选指标各一行 `【参考标准】…（来源：…，请自行查证，非医疗建议）`，并写「参考范围内/外」 | 给 HRV 绝对值人群范围；用参考层下诊断结论；Python 写死数字 |
| **建议** | 一句固定模板：缺项→先同步；有低于基线→偏轻松安排；否则持平/偏好 | 训练处方、补剂疗效、用药剂量 |
| **免责** | 固定：教育参考，非医疗建议，不能替代医师诊治 | 加长法律文 |
| **AI 解读**（仅按钮后） | 标题「AI 解读（实验）· 非医疗建议」；生成时间、模型名；正文经 Numerics 审计 | 混进规则层；进通知；预生成；外来精确数字 |

**数据完整性**：M0 捷径目前只 POST **步数**。已选但未入库的项必须打成「无」，不能假装评估完整。要把评估做实，须做 **FR-1.5 多指标入库**（任务卡 **M1-P5**）：每个已选且 ∈ FR-1.4 的指标，用与步数相同的「当日合计一个数字」再 POST。不要 Find 原始样本列表。未入库时禁止编数。

**两层触达**：

| 层 | 职责 |
|----|------|
| 锁屏通知 | 短导语：截至 / 是否今日 / 覆盖率 /「打开完整卡」。iOS 会截断长正文，禁止把清单塞进通知硬撞 |
| 完整卡 | `GET /proactive/fact-card/view`：清单 + 评估 + 建议 + 免责 + **勾选指标**。数字 ⊆ JSON |

默认勾选可以是注册表 `enabled_default`（当前：步数 / HRV / 睡眠 / 静息心率 / 活动消耗）。**默认 ≠ 不可改。**

---

## 6. 非功能与红线

| ID | 规则 |
|----|------|
| NFR-1 | **非医疗器械 / 非医嘱**。主动 Agent 不是医生。 |
| NFR-2 | 用户可见精确数字必须可追溯到 SQLite / ingest 样本（C 层精神）。事实卡禁止 LLM 填数。 |
| NFR-3 | 禁止诊断标题与病理推断（与双语压测语义债修复一致）。 |
| NFR-4 | 健康数据默认 **不出用户设备圈**（手机 ↔ 用户 Mac / 用户 VPN）。禁止默认上传到项目方服务器。 |
| NFR-5 | ingest 失败 **fail-closed**：丢本批，不编样本。 |
| NFR-6 | 不在 Chat Turn 内同步阻塞 ingest（设备 RFC）。 |
| NFR-7 | 端侧 M4 算力红线仍约束 **Mac 上 LLM**；iOS 侧 v1 不做本地 7B。 |

---

## 7. 业界先进范式对照（宪法第一条）

| 标杆 | 可吸收 | 不得照搬 |
|------|--------|----------|
| Apple HealthKit + `HKObserverQuery` / 后台任务 | 采集与增量观察 | 把 PHA 做成第二个「健康」App 替代系统健康 |
| health4.ai 等 HealthKit → 自有库 + MCP | 薄客户端 + 用户自有存储 | 托管云库；无审计的自然语言教练 |
| Whoop / Athlytic 恢复建议 | 用 **个人基线分位** 做分档 UX | 无证据的训练处方、订阅云分析 |
| 本仓 harness fail-closed | 事实卡与通知走同一账本 | 主动推送用第二 LLM「润色数字」 |
| 本地通知 / 日历提醒 | 用药时间表 | 用模型猜服药时间 |

---

## 8. 里程碑与任务卡

开工须改状态；完成须填写完成记录（日期）。**未完成 M0 不得宣称 M1。**

| ID | 里程碑 | 状态 | 完成记录 |
|----|--------|------|----------|
| **M0-P0** | `POST /ingest/healthkit` + selfcheck | `DONE` | 2026-08-31：假数据入库 `wearable_data`/`wearable_daily`；token 401/503；临时库自检 `scripts/pha_healthkit_ingest_selfcheck.py` |
| **M0-P1** | 捷径真机 Watch → Mac 库 | `DONE` | 2026-09-04：iPhone ingest 200；`user_id=default` 的 healthkit steps 入库；日表当天有 steps。limit-1 为单条增量（16），全日合计属 M0-P2 |
| **M0-P2** | 日表对齐；skip-LLM 问答能读到 healthkit 行 | `DONE` | 2026-09-05：真机今日 **14872** 入库；「今天」读当日行，「昨天」11259；空窗/非本窗整步数 fail-closed。Hero「今日步数」走同一点日绑定，不用窗口末日顶。未改 `harness_core` 包。 |
| **M1-P0** | 无 LLM 事实卡引擎 + `GET /proactive/fact-card` | `DONE` | 2026-09-06：`pha/fact_card.py`；selfcheck PASS；今日无行则 stale + today.steps=null，as_of 步数不标今日。 |
| **M1-P1** | iPhone 捷径本地通知（可配每日自动化） | `DONE` | 2026-09-06：LAN `192.168.77.219` `GET /proactive/fact-card` **200**；维护者确认 iPhone 弹出事实卡通知。每日自动化仍由「快捷指令」定时跑，未另验。 |
| **M1-P2** | 通知内容契约：五项事实 + 卡级评估/建议 | `DONE` | 2026-09-06：当时正文枚举白名单五项；`assessment.summary`；无记录写「无」。v1.3 起五项改为默认选择，完整清单改走 HTML。 |
| **M1-P3** | 完整卡可点开：短通知 + `GET /proactive/fact-card/view` | `DONE` | 2026-09-06：锁屏只保留导语；捷径「打开 URL」进移动完整卡。系统通知本身通常不能自定义点击深链，完整卡靠打开 URL / 以后 M2 App。 |
| **M1-P4** | 用户自选指标（反硬编码） | `DONE` | 2026-09-06：注册表 `fact_card.eligible` + `data/fact_card_prefs.json` + 完整卡勾选。 |
| **M1-P5** | 多指标入库（数量型） | `DONE` | 2026-09-06 18:58：真机 `active_energy` **701.69** kcal + `rhr` **60** 同日入库（日键 UPSERT）。先 Allow Access 后 Find 标签须为 `Active Calories`。睡眠/HRV 仍 **M1-P6**。 |
| **M1-P6** | 睡眠各项 + HRV SDNN | `IN_PROGRESS` | HRV 真机 40.97 已对上（健康 41）。睡眠：删近两日 Pillow 历史后（15:41）9/7 入睡 7.60 / 清醒 3.45 / 核心 4.90 / 深 1.65 / REM 1.05（相对健康 App 差 ≤8 分钟）；健康 App 与 PHA **在床皆无**（原 8.95 来自 Pillow，已删）。根因曾是 Pillow+Watch 双轨并集；捷径 Source 取不到。门禁改为「有则比、无则空」+ 真源=健康 App 展现。仍欠：连续多夜同口径、T7 回执、文档偏差表收口。见 review / 任务卡。 |
| **M1-P7** | **递进个人基线 + 通用参考层**（无 LLM） | `DONE` | 2026-09-07：按指标 90d→365d→all；真机睡眠 `365d` n=267；注册表 `reference_range`（睡眠/RHR/步数）+ T1 披露；卡级综合/不综合；selfcheck PASS。深睡/REM 占比参考未做（TODO）。 |
| **M1-P8** | **HRV 列语义纠正（SDNN）** | `DONE` | 2026-09-07：日表 1937→`hrv_sdnn_ms`；样本改标 `hrv_sdnn`；注册表主指标 SDNN；9/6 band=above n=275；ingest `hrv`→SDNN。叠 harness ACK。 |
| **M1-P9** | **我的评估要求 + 按钮式解读**（FR-2.9 / FR-6） | `TODO` | 顺序：① prefs 文本框保存 + 回显（无 LLM）；② `POST /proactive/fact-card/interpret` 异步入队 + `GET …/interpret` 读缓存；③ 走 `chat_service` 管线 + Numerics 审计；④ 完整卡独立区块。禁止裸 Ollama、禁止预生成、禁止进通知 |
| **M1** | （汇总）iPhone 主动事实卡：通道 + 完整卡 + 可选指标 | `DONE*` | P0–P4 已落地。`*` = 多指标入库仍缺，评估覆盖率会诚实偏低。未开 M2。 |
| **M2** | TestFlight 薄 App：授权、同步、事实卡、登记提醒、通知点开 | `TODO` | |
| **M3** | App 内接同一解读/问答端点（UI 接线） | `TODO` | 触发：M2 稳定。能力由 M1-P9 先在完整卡网页落地，M3 不重写逻辑 |
| **M4** | 端侧推理 | `TODO` | 触发：有明确机型与模型方案 |

M1 代码落点：`pha/fact_card.py`；`GET /proactive/fact-card` + `/view` + `/prefs`；`scripts/pha_fact_card_selfcheck.py`；`scripts/macos/build_pha_ingest_shortcuts.py`（`PHA 事实卡通知`）；`docs/pha-fact-card.md`；`docs/pha-ios-proactive-roadmap.md`。

---

## 9. 执行协议（对 coding agent）

1. 凡改 ingest / 事实卡 / iOS 同步契约 / 主动通知文案模板，**先读本文全文**，首条回复与 PR 描述输出：  
   `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
2. 同 PR 更新 [`pha-ios-proactive-change-log.md`](pha-ios-proactive-change-log.md)。  
3. 触及 harness 数值路径时 **叠加** `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`。  
4. 触及启动/监听地址/`pha/main.py` 进程时 **叠加** 启动共识与 `startup-change-log.md`。  
5. **不扩 scope**：本 PRD 未写的功能（云同步、Watch App、秒级心率）先登记本文 §11 或审计方案 §4，人审后再开卡。  
6. 禁止用「主动更智能」削弱 TurnEvidencePlan / Numerics 审计。  
7. agent 只本地 commit；push 由维护者执行。

---

## 10. 风险与诚实边界

| 风险 | 产品态度 |
|------|----------|
| iOS 后台漏同步 | v1 接受；UI 必须显示上次成功时间 |
| 手机打不到 Mac | 文档默认 Tailscale；打不通则 M0 未完成 |
| 审核医疗声称 | 文案冻结为 wellness / 教育参考 |
| 与「harness 开源叙事」张力 | 公开仓继续 harness-first；PHA 产品不靠改仓库名骗流量 |
| 一人兼 iOS + Python | 捷径验证先于 Xcode；避免未通管道先写 App |

---

## 11. 新发现登记（执行中追加，勿改历史行）

| 日期 | 发现 | 处置 |
|------|------|------|
| 2026-08-31 | 立 PRD：PHA 逐步 iOS 化 + 主动 Agent | 本文 v1.0 |
| 2026-08-31 | M0-P0：`source` 无独立列，编入 `sample_id`；`sleep_hours` 落库 `metric_type=sleep` | 记入 change-log；日表用标量 max 回填 |
| 2026-09-04 | M0-P1 真机通：捷径会触发 iOS「共享大量健康数据」若一次 Find 几百条；limit 1 可入库 | M0-P2 改为日合计数字再 POST，避免把 329 条 Health 项发给 URL |
| 2026-09-06 | M1 通道在表里写成「通知或小组件」，未写明 iPhone；评估/建议未分层 | v1.1：M1 = iPhone 本地通知；卡分 facts / assessment；LLM 评估不进主动路径 |
| 2026-09-06 | 真机捷径 `GET /proactive/fact-card` 200，iPhone 弹出通知 | M1-P1 通道 DONE |
| 2026-09-06 | 首版通知只甩出有数的步数，评估层不可见 | v1.2 内容契约 + M1-P2：五项都列出；卡级评估/建议 |
| 2026-09-06 | iPhone 通知截断且无法点开；五项写死在 Python | v1.3：完整卡 HTML；指标改注册表+用户勾选；多指标入库立为 M1-P5 |
| 2026-09-06 | 要把评估做实须多指标入库；HRV 列名是 RMSSD，手表是 SDNN | M1-P5 数量型；睡眠/HRV 各项另立 M1-P6，禁止 SDNN→RMSSD |
| 2026-09-07 | Shortcuts 睡眠列表：日期串 `7 Sep 2026 at 12:01 AM`（AM 前窄空格）；分钟精度使短段 end==start；自造 If/Count/JSON 字典与 `last 1 day` 大列表会让捷径中断 | 解析器容错；校验粒度改为「结构错整批拒、装饰瑕疵按段跳」；捷径退回 `is today` 过渡；坑全部记入 change-log |
| 2026-09-07 | 首次真机睡眠 200，但 12h 窗口内入睡+清醒=13.3h（各分期并集相加，跨分期重叠重复计入）；成功不落分段、不留审计，无法定位重叠来源；健康 App 清醒 3.35h 含入睡前约 2h（Apple 定义：会话内未睡着都算 Awake） | 立 [`pha-sleep-ingest-review-2026-09-07.md`](pha-sleep-ingest-review-2026-09-07.md)：分段落库 + 审计行；入睡改一次总并集 + `stage_overlap`；醒来日由数据推导 + 正午窗口；M1-P6 保持 IN_PROGRESS 并冻结完成门禁。（同日 12:34–12:37 维护者定口径：健康 App 无「入睡前」概念，清醒取原值不拆；9/7 会话由一段 4 分钟 Deep 开启后 ≈2.2h 清醒，App 与规则均无误；12:42 定稿：PHA 不判定采集失误、不打标签、不修正、不排除，只在偏离个人基线时提醒用户到健康 App 核对——这正是主动提醒 agent 的职责；「在床 = 会话跨度」被 9/7 真值否决） |
| 2026-09-07 | 12:13 维护者重跑捷径，Mac 无 POST，手机侧无处可查上次同步 | 增 FR-1.7 同步回执；9/6 半截 POST 残留 `in_bed=0.73` 需清理并立「bundle 成功即清同日旧睡眠日键行」规则 |
| 2026-09-07 | 健康 App 9/7 截图：在床 8.95 / 入睡 7.72 / 清醒 3.58 / REM 1.10 / 核心 4.98 / 深 1.63；入睡+清醒 11.30 ≠ 在床（Apple 在床不含入睡前那块）。库同夜深睡精确一致，REM ×2.7、核心 +20% | 否决「在床 = 会话跨度」推导，在床只取 In Bed 样本；问题收敛为重复/重叠段去重；review §7 立 T0–T9 任务表交 coding agent 按序执行 |
| 2026-09-07 | 「显示所有数据」证明 9/7 = Pillow + Watch 双轨；关掉 Pillow 写入后历史仍在；删近两日 Pillow 后库对齐 Watch/健康 App 展现（在床双方皆无）。维护者定：验收有则比、无则空；禁止硬编码必采项（FR-2.7）；真源=健康 App 展现，M1 先单源简化，多源优先级对齐属 M2 | v1.5：改 FR-1.6 / M1-P6 门禁与任务卡；不改代码 |
| 2026-09-07 | 完整卡评估层空/只写「基线不足」。查库：`default` 睡眠 642 夜（近 365 日 268）、HRV 1936 天、RHR 2255 天、消耗 2286 天，但 `BASELINE_DAYS=90` 从 as_of 回看正好把 zip（止 6/9）全排除，n=0/1。维护者定：**主动 agent 是 PHA 一部分，不得与 Mac 账本割裂**；「基线不足」不成立；需要通用评估规则让信息有意义 | v1.6：§1.3a；FR-2.1 / FR-2.6 递进基线 + 窗口披露；FR-2.8 通用参考层（T1 披露制、注册表数据）；立 M1-P7。不改代码 |
| 2026-09-07 | zip 导入的 `metric_type=hrv` 11650 条 `sample_id` 全为 `HKQuantityTypeIdentifierHeartRateVariabilitySDNN|…|Wind’s Apple Watch`：`hrv_rmssd_ms` 列自始就是 Apple SDNN，库中没有 RMSSD。9/6 起「SDNN 不进 RMSSD」的隔离是对的，但两列其实同一物理量，HRV 7 年基线被列名挡住 | 立 M1-P8 列语义纠正（叠 harness ACK，单卡）；FR-1.4 的「SDNN 不进 RMSSD」保留到 P8 完成前 |
| 2026-09-07 | 维护者同意「我的评估要求（自由文本，给 LLM）」；问 M3 原计划阶段与「按钮式解读」是否冲突。结论：M3 原为 M2 稳定后的 App 内问答；按钮式解读 = 用户开口，不属主动路径；复用 chat harness 而非裸 Ollama；M3 缩成 App 接线，顺序不变 | v1.6：§1.3 定义「主动路径」；§3 M3 改义；FR-2.9 / FR-6；立 M1-P9；§4.2 增「禁止预生成 / 禁止裸奔」。不改代码 |

---

## 12. 修订记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-31 | v1.0 | 初版共识：管道优先、事实卡无 LLM、iOS 为壳、Mac 为账本 |
| 2026-09-06 | v1.1 | 冻结 M1 通道为 iPhone 捷径本地通知；事实卡两层（数字 + 模板评估）；主动路径禁止 LLM 评估 |
| 2026-09-06 | v1.2 | §5.1 内容契约：通知必须五项事实 + 卡级评估/建议；分析=个人基线规则，不是 LLM |
| 2026-09-06 | v1.3 | 完整卡可点开；指标用户自选（宪法反硬编码）；FR-1.5 / M1-P5 多指标入库写入计划 |
| 2026-09-06 | v1.3 | 增 FR-1.6 / M1-P6：睡眠各项 + HRV SDNN 另卡 |
| 2026-09-07 | v1.4 | FR-1.6 验收细化（分段落库、总并集、醒来日推导、清醒取原值、在床只取 In Bed、不判定异常只提醒核对、±10 分钟）；增 FR-1.7 同步回执；M1-P6 行更新为真机 200 但未对上；§11 追加发现。文档改动，无代码 |
| 2026-09-07 | v1.5 | FR-1.6 / M1-P6：验收「有则比、无则空」；真源=健康 App 展现；M1 单源过渡、多源属 M2；与 FR-2.7 勾选一致，禁止硬编码必采睡眠项。文档改动，无代码 |
| 2026-09-07 | v1.6 | §1.3 定义主动路径 + §1.3a 不割裂原则；FR-2.1 / FR-2.6 递进个人基线（90d→365d→all）+ 窗口披露；FR-2.8 通用参考层（T1 披露、注册表 `reference_range`）；FR-2.9 我的评估要求；FR-6 用户触发 LLM 解读（harness 复用、审计、异步缓存、fail-closed）；M3 改为 App 接线；立 M1-P7 / P8 / P9；§4.2 增禁止预生成与裸奔；§11 三条。文档改动，无代码。交接：[`handoff-2026-09-07-fact-card-assessment.md`](handoff-2026-09-07-fact-card-assessment.md) |
