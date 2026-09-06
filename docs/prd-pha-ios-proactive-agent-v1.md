# PRD / 共识 · PHA → iOS 主动健康管理 Agent

> **状态**：跨 agent **产品共识真源**（强制）  
> **版本**：v1.2 · 2026-09-06  
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
3. **主动 ≠ 诊疗**：主动推送的是 **无 LLM 事实卡（数字层）+ 规则分档与固定模板建议（评估层）+ 用户自登记提醒**。禁止诊断口吻、禁止编造数字、禁止把一次 HRV 写成处方。**主动路径不得用 LLM 写评估**；开口问答属 M3。  
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
| **M3** | App 内问答（调本机 PHA 或日后端侧模型） | 默认仍 Mac；端侧 LLM **另开任务卡** |
| **M4** | 可选：PHA 核心部分端侧化 | 仅当 M2 稳定且有明确算力方案 |

**v1 产品承诺止于 M2。** M3/M4 不是本 PRD 的 DoD。

---

## 4. 范围

### 4.1 In scope（v1）

- `POST /ingest/healthkit` 及幂等写入、当日滚日表  
- iOS 捷径验证，随后薄原生 App（HealthKit + 同步 + 通知）  
- 无 LLM 每日事实卡：`as_of=MAX(day)` + **日历日当日行（缺则空，不顶）** + 90 日基线；规则分档  
- 事实卡两层：① 数字 / `as_of` / `stale` ② 规则分档 + **固定模板建议**（非 LLM）  
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
| FR-1.4 | 指标 v1 白名单 | `hrv`, `rhr`, `steps`, `sleep_hours`, `active_energy`（申请不到则文档降级，管道仍算通） |

### FR-2 事实卡引擎（无 LLM）

| ID | 需求 | 验收 |
|----|------|------|
| FR-2.1 | 读 `MAX(day)` + 当日行 + 90 日 mean/min/max | 脚本输出 JSON，数字 ⊆ 查询结果 |
| FR-2.2 | HRV 等分档仅为规则（如 vs 分位），文案模板固定 | 无模型进程 |
| FR-2.3 | 过期：`as_of` 早于本地日历日则 `stale=true` | 卡片可见；通知须写「非今日」，禁止把末日标成今日 |
| FR-2.4 | 卡分两层：`facts`（数字）与 `assessment`（规则分档 + 模板建议 + 免责） | JSON 同时有两层；评估句不含诊断/处方 |
| FR-2.5 | 通知与 JSON **枚举 FR-1.4 全部五项**；无记录写「无」，禁止省略、禁止用其他日顶 | 正文同时出现步数/HRV/睡眠/静息心率/活动消耗 |
| FR-2.6 | 卡级评估：覆盖率 + stale + 个人基线分档；一句建议。分析 = 相对近90日自己，不是 LLM 长文 | `assessment.summary`；通知有「评估：」「建议：」 |

### FR-3 主动触达

| ID | 需求 | 验收 |
|----|------|------|
| FR-3.1 | 每日一次（可配置时刻）生成事实卡并通知 | 用户未开聊天也能收到 |
| FR-3.2 | 提醒只来自用户登记表 | 无登记则无吃药/补剂项 |
| FR-3.3 | 通知文案含非医疗免责短句 | 固定字符串，非法条长文 |
| FR-3.4 | **M1 通道 = iPhone 本地通知**：捷径 `GET /proactive/fact-card`（同源 ingest token）后「显示通知」；每日用「快捷指令」自动化定时跑。不是 Mac 通知中心，不是 APNs | 真机能看到五项事实 + 评估/建议（无记录也要出现） |

### FR-4 iOS App 壳（M2）

| ID | 需求 | 验收 |
|----|------|------|
| FR-4.1 | HealthKit 授权、服务器 URL、token、上次同步 | 设置页可改 |
| FR-4.2 | 前台「立即同步」 | 等价于捷径成功路径 |
| FR-4.3 | 展示最新事实卡 | 数字与 Mac 脚本一致 |
| FR-4.4 | 后台尽力同步 | 允许漏；须暴露失败原因（不假装成功） |

### FR-5 问答（沿用，不作为主动主路径）

现有 harness 聊天可继续跑在 Mac。主动路径 **不得** 为了「更聪明」绕过 Numerics 审计。App 内聊天属 M3。

### 5.1 事实卡内容契约（v1.2 · 主动通知必须遵守）

主动通知不是「有数的那一项甩出去」。用户要看的是 **事实清单 + 评估/建议**。分析在 v1 **只允许**相对个人 90 日基线的规则，禁止 LLM 写评语。

| 块 | 必须出现 | 禁止 |
|----|----------|------|
| **事实** | FR-1.4 五项都出现：有数则写数字+单位，无数则「无」；`截至 as_of`；stale 写「非今日」 | 只列步数；用昨日顶今日；编 HRV/睡眠 |
| **评估** | 覆盖率（几项有数）；缺项点名；基线 n&lt;7 则「不做分档」；n≥7 则低于/持平/高于个人分位 | 诊断、病因、病理标题 |
| **建议** | 一句固定模板：缺项→先同步；有低于基线→偏轻松安排；否则持平/偏好 | 训练处方、补剂疗效、用药剂量 |
| **免责** | 固定：教育参考，非医疗建议，不能替代医师诊治 | 加长法律文 |

**数据完整性**：M0 捷径目前只 POST **步数**。卡必须把其余四项打成「无」，不能假装评估完整。要把评估做实，须扩大同步（捷径或 M2 App 按日合计再 POST 白名单）。扩大同步 **另开任务卡**，不在未入库时编数。

通知正文固定四行：`截至…` / `五项清单` / `评估：…` / `建议：…` + 免责。锁屏截断可接受，JSON 仍是完整真源。

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
| **M1-P2** | 通知内容契约：五项事实 + 卡级评估/建议 | `DONE` | 2026-09-06：正文枚举白名单五项；`assessment.summary`；无记录写「无」。M0 捷径仍只同步步数，其余项诚实为无。 |
| **M1** | （汇总）iPhone 主动事实卡：通道 + 内容契约 | `DONE` | M1-P0 + P1 + P2。未开 M2；多指标入库另开卡。 |
| **M2** | TestFlight 薄 App：授权、同步、事实卡、登记提醒 | `TODO` | |
| **M3** | App 内问答对接 PHA（可选） | `TODO` | 触发：M2 稳定 |
| **M4** | 端侧推理 | `TODO` | 触发：有明确机型与模型方案 |

M1 代码落点：`pha/fact_card.py`；`GET /proactive/fact-card`；`scripts/pha_fact_card_selfcheck.py`；`scripts/macos/build_pha_ingest_shortcuts.py`（`PHA 事实卡通知`）；`docs/pha-fact-card.md`。

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

---

## 12. 修订记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-31 | v1.0 | 初版共识：管道优先、事实卡无 LLM、iOS 为壳、Mac 为账本 |
| 2026-09-06 | v1.1 | 冻结 M1 通道为 iPhone 捷径本地通知；事实卡两层（数字 + 模板评估）；主动路径禁止 LLM 评估 |
| 2026-09-06 | v1.2 | §5.1 内容契约：通知必须五项事实 + 卡级评估/建议；分析=个人基线规则，不是 LLM |
