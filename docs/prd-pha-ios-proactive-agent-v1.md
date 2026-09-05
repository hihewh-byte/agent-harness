# PRD / 共识 · PHA → iOS 主动健康管理 Agent

> **状态**：跨 agent **产品共识真源**（强制）  
> **版本**：v1.0 · 2026-08-31  
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
3. **主动 ≠ 诊疗**：主动推送的是 **无 LLM 事实卡 + 规则分档 + 用户自登记提醒**。禁止诊断口吻、禁止编造数字、禁止把一次 HRV 写成处方。  
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
| 主动 | 用户未打开聊天时，能收到 **一条基于库内数字的事实卡通知**（规则生成） |
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
              事实卡引擎（无 LLM）→ 通知 / 小组件 / 日后 App UI
              聊天（现有 harness）← 用户主动问才走 LLM
```

| 阶段 | 用户看见什么 | 计算在哪 |
|------|----------------|----------|
| **M0** | 无新 UI；库里有今日 Watch 数 | Mac |
| **M1** | 通知或小组件：今日事实卡 | Mac 生成，iOS 展示 |
| **M2** | iOS App：授权、同步状态、事实卡、提醒登记 | 采集在 iOS；账本在 Mac |
| **M3** | App 内问答（调本机 PHA 或日后端侧模型） | 默认仍 Mac；端侧 LLM **另开任务卡** |
| **M4** | 可选：PHA 核心部分端侧化 | 仅当 M2 稳定且有明确算力方案 |

**v1 产品承诺止于 M2。** M3/M4 不是本 PRD 的 DoD。

---

## 4. 范围

### 4.1 In scope（v1）

- `POST /ingest/healthkit` 及幂等写入、当日滚日表  
- iOS 捷径验证，随后薄原生 App（HealthKit + 同步 + 通知）  
- 无 LLM 每日事实卡：最新 `wearable_daily` 行 vs 90 日基线；规则分档（如 HRV 分位）  
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
| FR-2.3 | 过期：`as_of` 早于本地日历日则 `stale=true` | 卡片可见 |

### FR-3 主动触达

| ID | 需求 | 验收 |
|----|------|------|
| FR-3.1 | 每日一次（可配置时刻）生成事实卡并通知 | 用户未开聊天也能收到 |
| FR-3.2 | 提醒只来自用户登记表 | 无登记则无吃药/补剂项 |
| FR-3.3 | 通知文案含非医疗免责短句 | 固定字符串，非法条长文 |

### FR-4 iOS App 壳（M2）

| ID | 需求 | 验收 |
|----|------|------|
| FR-4.1 | HealthKit 授权、服务器 URL、token、上次同步 | 设置页可改 |
| FR-4.2 | 前台「立即同步」 | 等价于捷径成功路径 |
| FR-4.3 | 展示最新事实卡 | 数字与 Mac 脚本一致 |
| FR-4.4 | 后台尽力同步 | 允许漏；须暴露失败原因（不假装成功） |

### FR-5 问答（沿用，不作为主动主路径）

现有 harness 聊天可继续跑在 Mac。主动路径 **不得** 为了「更聪明」绕过 Numerics 审计。App 内聊天属 M3。

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
| **M1** | 无 LLM 事实卡脚本 + 至少一种主动通道（通知或本机文件+捷径展示） | `TODO` | |
| **M2** | TestFlight 薄 App：授权、同步、事实卡、登记提醒 | `TODO` | |
| **M3** | App 内问答对接 PHA（可选） | `TODO` | 触发：M2 稳定 |
| **M4** | 端侧推理 | `TODO` | 触发：有明确机型与模型方案 |

建议第一周只认领 **M0-P0 + M0-P1**（第一刀）。

代码落点：`pha/healthkit_ingest.py`；`POST /ingest/healthkit`；复用 `WearableDataBatchWriter` + `rebuild_wearable_daily_for_days`；`scripts/pha_healthkit_ingest_selfcheck.py`；`docs/healthkit-ingest.md`。

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

---

## 12. 修订记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-31 | v1.0 | 初版共识：管道优先、事实卡无 LLM、iOS 为壳、Mac 为账本 |
