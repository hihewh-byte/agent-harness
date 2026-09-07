# PHA iOS / 主动 Agent 开发计划

> 上位法：[PHA 宪法](pha-pm-constitution.md)（反硬编码、Telemetry 驱动、确定性 Harness）  
> 产品真源：[PRD v1.6](prd-pha-ios-proactive-agent-v1.md)  
> 指标允许集：[穿戴注册表](wearable-metric-registry-v1.md)  
> 启动：[稳定性计划](stability-remediation-plan-2026-06-10.md) — 改 `main.py` / 监听 / 重启只用官方 `bash scripts/pha_restart_accept.sh`

冲突时：**数值诚实与 fail-closed 优先于「更主动」「更像教练」。**  
未完成睡眠/HRV（M1-P6）前，评估覆盖率会诚实偏低，不得假装已产品化。未开 M2 前，不要做 Watch App / APNs / 云。

---

## 已完成（到 2026-09-06）

| 卡 | 结果 |
|----|------|
| M0-P0～P2 | ingest + 真机步数入库 + 时间槽/空窗 fail-closed + Hero 点日绑定 |
| M1-P0～P2 | 无 LLM 事实卡 JSON + iPhone 捷径通知 + 评估层 |
| M1-P3 | 锁屏短通知 + `GET /proactive/fact-card/view` 完整卡（捷径「打开 URL」） |
| M1-P4 | 指标 = 注册表 `fact_card.eligible` + 用户勾选；禁止 Python 死列表 |
| M1-P5 | 数量型真机入库：2026-09-06 活动消耗 **701.69** kcal + 静息心率 **60** |

公开仓 README 第一屏仍是 harness-first。不改 `packages/harness_core`。

---

## 下一刀（按序，不要跳）

### 1. M1-P6 真机：PHA 同步睡眠

1. AirDrop 桌面 **PHA 同步睡眠**（不要并进已通的「PHA 同步健康」）。
2. 编辑捷径，对第一条 Find Sleep 点 **Allow Access**，再跑。
3. 对健康 App 昨晚：在床 / 核心 / 深睡 / REM / 清醒。库中同日对应列应量级合理；`sleep_hours` = 核心+深睡+REM。
4. 跨夜窗口为昨午→今午，见 [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md)。

### 1b. M1-P7 递进个人基线 + 通用参考层（无 LLM）· DONE 2026-09-07

- 按指标 90d → 365d → all；卡上写「相对你近 12 个月 N 夜/天」
- 注册表 `reference_range`（睡眠总时长 / RHR / 步数）→ T1 披露；HRV 不给；深睡/REM 占比 TODO
- 卡级综合三档；缺项「不综合」

### 1c. M1-P8 HRV 列语义纠正（叠 harness ACK）· DONE 2026-09-07

- 日表历史复制进 `hrv_sdnn_ms`；样本 `hrv`→`hrv_sdnn`；注册表主指标 SDNN
- 脚本：`scripts/pha_migrate_hrv_rmssd_to_sdnn.py`（先 `--dry-run`）

### 1d. M1-P9 我的评估要求 + 按钮式解读（FR-2.9 / FR-6）· 下一刀

- prefs `assessment_prompt` 保存回显 → `POST/GET /proactive/fact-card/interpret` 异步 + 缓存 → 走 `chat_service` + Numerics 审计 → 完整卡独立区块
- 禁止裸 Ollama、预生成、进通知；M3 App 只接同一端点

### 2. M2 薄 App（捷径同步已不可忍受时）

- HealthKit 授权、服务器 URL、token、上次同步时间
- 前台「立即同步」= 捷径成功路径
- **事实卡页**（可点通知打开；不再靠 Safari + query token）
- 设置页改指标集（写同一份 prefs）
- 用药/补剂：仅用户登记表 → 本地通知
- 后台尽力同步，失败原因可见

### 3. M3 / M4（触发条件没到就不要开）

- M3：App 内接 **同一** 解读/问答端点（能力由 M1-P9 在完整卡网页先落地）；主动路径仍禁止 LLM 评估/填数；用户点按钮 = 开口，不算主动路径
- M4：端侧推理，须有机型与模型方案

---

## 本轨道永远遵守

- Watch 数据只经 iPhone HealthKit → ingest → Mac 账本
- 主动路径无 LLM 填数；ingest fail-closed
- 新指标：先注册表一行 + 日列已存在，再让用户勾选；不要在 `fact_card.py` 加 if 特例
- 重启走官方脚本；不改公开 README 叙事
