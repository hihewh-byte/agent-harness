# PBOC 汇率同步与规则自动更新 v1

> **状态**：Active — 2026-06

---

## 1. 汇率数据链路

```text
中国外汇交易中心 / chinamoney 月末中间价
        ↓ scripts/sync_pboc_fx_rates.py（或 tax_agent.pboc_fetcher）
data/pboc_usd_cny_middle.yaml          # 人工可校对的主数据集
        ↓ scripts/build_fx_rates_snapshot.py
rules/.../snapshots/YYYY.MM.DD/fx_rates.yaml
        ↓ scripts/build_rules_feed.py
远程 Feed JSON（inline fx_rates.yaml）
        ↓ regulation_monitor.sync_from_feed（含可选文件）
本地规则快照 → FxRateProvider → 测算
```

### 手动 / CI 更新

```bash
# 拉取近 3 个月并写入快照
.venv/bin/python scripts/sync_pboc_fx_rates.py

# 仅用本地 data 重建 fx_rates.yaml（离线）
.venv/bin/python scripts/sync_pboc_fx_rates.py --skip-fetch
```

环境变量（与规则 Feed 共用）：

| 变量 | 说明 |
|------|------|
| `TAX_AGENT_RULES_FEED_URL` | 远程规则 Feed URL |
| `TAX_AGENT_RULES_SYNC_ON_STARTUP` | 启动时同步 |
| `TAX_AGENT_RULES_AUTO_SYNC_INTERVAL_SECONDS` | 周期同步间隔 |
| `TAX_AGENT_AUTO_PUBLISH` | Golden 通过后自动发布 stable |

---

## 2. 规则自动更新（已有）

1. **远程 Feed** / **inbox 目录** 导入 `review` 快照  
2. `run_golden_regression` 回归  
3. 可选 `publish_stable`  

**v1 修复**：`sync_from_feed` 现已同步 **`fx_rates.yaml`**（`OPTIONAL_SNAPSHOT_FILES`），避免远程更新后汇率丢失、回退 7.10 兜底。

---

## 3. 数据准确性建议

1. **自动抓取**仅覆盖近月；历史月份以 `data/pboc_usd_cny_middle.yaml` 为准，重大申报前人工核对 [SAFE 中间价发布](https://www.safe.gov.cn)。
2. 抓取失败时脚本非零退出，测算仍用快照内已有 `fx_rates.yaml`。
3. 测算结果 `notes` 会标记「样例/兜底汇率」；`auditBundle.fxRateSources` 可追溯每笔折算来源。

---

## 4. 免责声明

自动同步的汇率与规则版本仅供辅助；正式申报前应以税务机关要求及官方当日中间价为准。
