# PHA iOS / 主动 Agent 开发计划

> 上位法：[PHA 宪法](pha-pm-constitution.md)（反硬编码、Telemetry 驱动、确定性 Harness）  
> 产品真源：[PRD v1.3](prd-pha-ios-proactive-agent-v1.md)  
> 指标允许集：[穿戴注册表](wearable-metric-registry-v1.md)  
> 启动：[稳定性计划](stability-remediation-plan-2026-06-10.md) — 改 `main.py` / 监听 / 重启只用官方 `bash scripts/pha_restart_accept.sh`

冲突时：**数值诚实与 fail-closed 优先于「更主动」「更像教练」。**  
未完成 M1-P5 前，不得宣称主动评估已产品化。未开 M2 前，不要做 Watch App / APNs / 云。

---

## 已完成（到 2026-09-06）

| 卡 | 结果 |
|----|------|
| M0-P0～P2 | ingest + 真机步数入库 + 时间槽/空窗 fail-closed + Hero 点日绑定 |
| M1-P0～P2 | 无 LLM 事实卡 JSON + iPhone 捷径通知 + 评估层 |
| M1-P3 | 锁屏短通知 + `GET /proactive/fact-card/view` 完整卡（捷径「打开 URL」） |
| M1-P4 | 指标 = 注册表 `fact_card.eligible` + 用户勾选；禁止 Python 死列表 |

公开仓 README 第一屏仍是 harness-first。不改 `packages/harness_core`。

---

## 下一刀（按序，不要跳）

### 1. 你这边立刻要做的

1. **先 push** 当前已提交的 M1（若还没推）。agent 不代 push。
2. 本机拉起后重建捷径并 AirDrop：**旧「PHA 事实卡通知」不会打开完整卡**。
   ```bash
   python scripts/macos/build_pha_ingest_shortcuts.py
   ```
3. iPhone 再跑一次：应先出短通知，再打开 Safari 完整卡。在底部勾选指标并保存。
4. 锁屏通知仍然可能点不开（系统捷径通知没有自定义深链）。要「点通知进卡」属于 **M2 App**。过渡期：点捷径或等自动化跑完打开的页面。

### 2. M1-P5 多指标入库（下一张代码卡）

**痛点**：评估要五项有数才完整，但生产捷径只 POST 步数。HRV/睡眠/RHR/消耗显示「无」是诚实，不是 bug。

| 步骤 | 做法 | 禁止 |
|------|------|------|
| 读用户已选 ∩ FR-1.4 | 已选且 ingest 白名单有的才同步 | 为未选指标去 HealthKit 要权 |
| 每个指标一条「当日合计」 | 与步数相同：Find 当日 → Sum → 只 POST 一个数字 | 一次 Find 几百条；触发「共享大量健康数据」就停 |
| fail-closed | 某一项拿不到就跳过该项，不编 0、不用昨日 | 用 zip 旧日顶今日 |
| 文档 | 改捷径生成器 + `pha-fact-card.md` + change-log | 在未入库时改评估文案假装完整 |

建议顺序：睡眠小时 → 活动消耗 → 静息心率 → HRV（SDNN 日代表，需在文档写清与 RMSSD 列的落库约定，对不上就先不映射）。

### 3. M2 薄 App（P5 通了或捷径同步已不可忍受时）

- HealthKit 授权、服务器 URL、token、上次同步时间
- 前台「立即同步」= 捷径成功路径
- **事实卡页**（可点通知打开；不再靠 Safari + query token）
- 设置页改指标集（写同一份 prefs）
- 用药/补剂：仅用户登记表 → 本地通知
- 后台尽力同步，失败原因可见

### 4. M3 / M4（触发条件没到就不要开）

- M3：App 内问答才走 LLM；主动路径仍禁止 LLM 评估/填数
- M4：端侧推理，须有机型与模型方案

---

## 本轨道永远遵守

- Watch 数据只经 iPhone HealthKit → ingest → Mac 账本
- 主动路径无 LLM 填数；ingest fail-closed
- 新指标：先注册表一行 + 日列已存在，再让用户勾选；不要在 `fact_card.py` 加 if 特例
- 重启走官方脚本；不改公开 README 叙事
