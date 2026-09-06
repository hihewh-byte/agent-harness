# PHA 事实卡（M1）

Mac 从 `wearable_daily` **无 LLM** 生成 JSON；iPhone 捷径拉取后发 **系统本地通知**。  
不是聊天，不是诊断，不是 APNs。

```bash
python scripts/pha_fact_card_selfcheck.py
python scripts/pha_fact_card.py          # 打印当前用户 default 的卡
```

## JSON 两层

| 层 | 字段 | 含义 |
|----|------|------|
| 数字 | `facts.as_of` / `facts.stale` / `facts.metrics` | `as_of = MAX(day)`；日历日无行则 `today.present=false`，**不用末日顶今日** |
| 评估 | `assessment.advice` | 相对近 90 日个人分位的规则分档 + **固定模板**；基线 n&lt;7 只展示数字 |

通知正文四行（锁屏可能截断，JSON 仍完整）：

1. `截至 {as_of}`（过期加「非今日」）
2. **五项都出现**：步数 / HRV / 睡眠 / 静息心率 / 活动消耗（无数写「无」）
3. `评估：` 覆盖率 + 缺项 + 是否相对个人基线分档
4. `建议：` 一句模板 + 免责

M0 捷径若只同步步数，其余四项必须显示「无」，不能编评估完整。

## HTTP

```text
GET /proactive/fact-card?user_id=default
Header: X-PHA-Ingest-Token: <与 ingest 同一 token>
```

未配置 token → 503；错 token → 401。

## iPhone 怎么每天收到

1. 本机生成捷径（token 只进 gitignored `data/local_shortcuts/`）：

```bash
python scripts/macos/build_pha_ingest_shortcuts.py
```

得到 `pha-fact-card.shortcut`（「PHA 事实卡通知」）。AirDrop 到 iPhone。

2. 先手动跑一次：应弹出通知（Mac PHA 须在听、手机能打到局域网/`.local`）。

3. **每日主动**：快捷指令 App → 自动化 → 特定时间 → 运行「PHA 事实卡通知」→ 打开「立即运行」（不要问是否运行）。

未同步今日 HealthKit 时，通知会写「截至昨天（非今日）」，数字仍是账本末日，不会假装是今天。
