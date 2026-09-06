# PHA 事实卡（M1）

Mac 从 `wearable_daily` **无 LLM** 生成 JSON；iPhone 捷径拉短通知后 **打开完整卡网页**。  
不是聊天，不是诊断，不是 APNs。

```bash
python scripts/pha_fact_card_selfcheck.py
python scripts/pha_fact_card.py          # 打印当前用户 default 的卡
```

## 两层触达

| 层 | 用途 |
|----|------|
| 锁屏通知 | 截至 / 是否今日 / 覆盖率 /「打开完整卡」。iOS 会截断，不要把清单塞进 body |
| 完整卡 | `GET /proactive/fact-card/view`：已选指标清单 + 评估 + 建议 + 勾选设置 |

## JSON 两层

| 层 | 字段 | 含义 |
|----|------|------|
| 数字 | `facts.as_of` / `facts.stale` / `facts.metrics` | `as_of = MAX(day)`；日历日无行则 `today.present=false`，**不用末日顶今日** |
| 选择 | `facts.selection.enabled_metric_ids` | 用户已选；允许集来自注册表，不是 Python 列表 |
| 评估 | `assessment.advice` | 相对近 90 日个人分位的规则分档 + **固定模板**；基线 n&lt;7 只展示数字 |

`notification.body` 是锁屏导语；`notification.open_path` 指向完整卡。

M0 捷径若只同步步数，已选的其余项必须显示「无」，不能编评估完整。扩大同步见 [路线图 M1-P5](pha-ios-proactive-roadmap.md)。

## 指标怎么改（不要改代码）

1. **用户**：打开完整卡底部「我要看哪些指标」，勾选后保存。偏好在 gitignored 的 `data/fact_card_prefs.json`。
2. **新增可选指标**：日列已存在 → 在 `storage/registry/wearable_metric_registry.json` 加 `fact_card.eligible`。不要在 `fact_card.py` 加 if。
3. **入库白名单**仍是 PRD FR-1.4；能看 ≠ 已能从 HealthKit POST。

```text
GET/PUT /proactive/fact-card/prefs?user_id=default
Header: X-PHA-Ingest-Token
```

## HTTP

```text
GET /proactive/fact-card?user_id=default
GET /proactive/fact-card/view?user_id=default
Header: X-PHA-Ingest-Token: <与 ingest 同一 token>
```

Safari 从捷径打开时可用 query `token=`（与 header 二选一）。未配置 token → 503；错 token → 401。

## iPhone 怎么每天收到

1. 本机生成捷径（token 只进 gitignored `data/local_shortcuts/`）：

```bash
python scripts/macos/build_pha_ingest_shortcuts.py
```

得到新的 `pha-fact-card.shortcut`（「PHA 事实卡通知」）。**必须重新 AirDrop**，旧捷径不会打开完整卡。

2. 先手动跑一次：短通知之后应打开 Safari 完整卡（Mac PHA 须在听、手机能打到局域网/`.local`）。若只出通知并写「无 URL」，是旧捷径：把桌面新文件再 AirDrop 一次。

3. **每日主动**：快捷指令 App → 自动化 → 特定时间 → 运行「PHA 事实卡通知」→ 打开「立即运行」。

4. 系统锁屏通知通常 **不能**自定义点进 URL。要点通知进卡，等 M2 App。过渡期靠捷径打开的页面，或再跑一次捷径。

未同步今日 HealthKit 时，会写「截至昨天（非今日）」，数字仍是账本末日，不会假装是今天。
