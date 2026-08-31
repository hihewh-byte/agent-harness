# 规则自动更新 v1

> **状态**：Implemented（基础版）  
> **修订日期**：2026-06-04

## 能否完全无人运维？

**可以自动化「同步 → 校验 → 回归 → 发布」**，但有一个前提：

- 税率/税目变更必须来自 **可信规则源**（内部 Git、法务维护的 JSON Feed、加密对象存储），而不是让 LLM 或爬虫随意解读国税网站。

本实现 **不会** 自动从互联网抓取并解释法律条文；它自动执行的是 **已结构化的规则包发布流水线**。

## 架构

```text
可信 Feed / 本地 inbox
        ↓
RegulationMonitor (sync_from_feed / sync_from_inbox)
        ↓
RuleRegistry.validate_snapshot_dir
        ↓
Golden 回归 (run_golden_selfcheck.py)
        ↓ 通过且 TAX_AGENT_AUTO_PUBLISH=1
RuleRegistry.publish_stable → manifest.latestStable
        ↓
ComputeEngine 使用 latest_stable 测算
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `TAX_AGENT_RULES_FEED_URL` | 远程 JSON Feed URL（HTTPS） |
| `TAX_AGENT_RULES_FEED_TOKEN` | 可选 Bearer Token |
| `TAX_AGENT_RULES_INBOX_DIR` | 本地入库目录，默认 `rules/inbox/cn_resident_us_equity/` |
| `TAX_AGENT_AUTO_PUBLISH` | `1` = 回归通过后自动 `publish_stable` |
| `TAX_AGENT_RULES_AUTO_SYNC_INTERVAL_SECONDS` | API 启动后周期同步（如 `3600`） |
| `TAX_AGENT_RULES_SYNC_ON_STARTUP` | `1` = 启动时立即跑一次同步 |
| `TAX_AGENT_RULES_ADMIN_TOKEN` | 保护 `/rules/sync`、`/rules/publish` |

## 远程 Feed 格式

```json
{
  "rulePackId": "cn_resident_us_equity",
  "snapshots": [
    {
      "snapshotFolder": "2026.09.01",
      "status": "review",
      "effectiveFrom": "2026-01-01",
      "source": "internal-legal-git",
      "files": {
        "rules.yaml": "...",
        "fx_policy.yaml": "...",
        "disclaimers.yaml": "..."
      }
    }
  ]
}
```

也可用 `fileUrls` 指向各 YAML 的 HTTPS 地址。

## 本地 inbox（无需 HTTP）

```text
rules/inbox/cn_resident_us_equity/2026.09.01/
  rules.yaml
  fx_policy.yaml
  disclaimers.yaml
  .ready          ← 标记可导入
```

同步任务会把目录移入 `snapshots/` 并标为 `review`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/rules/status` | 稳定版、上次同步、待审核（Web UI 轮询） |
| GET | `/rules/snapshots` | 列出快照与 `latestStable` |
| POST | `/rules/sync` | 执行完整自动更新周期 |
| POST | `/rules/webhook` | Git push / 自定义触发同步 |
| POST | `/rules/publish` | 手动发布指定文件夹为 stable |
| POST | `/rules/rollback` | 回退到最近 deprecated 快照 |
| GET | `/rules/monitor/status` | 发布后 72h 监控状态 |

### 发布后监控与自动回滚

环境变量（见 `.env.example`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `TAX_AGENT_RULES_MONITOR_HOURS` | 72 | 监控窗口（小时） |
| `TAX_AGENT_RULES_ROLLBACK_ERROR_RATE` | 0.01 | 测算 `status=failed` 占比阈值 |
| `TAX_AGENT_RULES_ROLLBACK_MIN_SAMPLES` | 5 | 判定前最少测算次数 |
| `TAX_AGENT_RULES_AUTO_ROLLBACK` | 0 | `1` 启用自动回退到 `previousStable` |
| `TAX_AGENT_RULES_MONITOR_INTERVAL_SECONDS` | 3600 | 后台评估间隔 |

每次 `publish_stable` 会开启监控；`/tax/compute` 会记录该快照下的失败率。

### GitHub Webhook

1. Payload URL：`https://your-host/rules/webhook`
2. Secret：与 `TAX_AGENT_RULES_WEBHOOK_SECRET` 相同
3. 事件：`push`（默认分支 `main`，可用 `TAX_AGENT_RULES_WEBHOOK_BRANCH` 改）

也可用请求头 `X-Tax-Agent-Webhook-Secret: <secret>` 触发。

Web UI 侧栏会显示当前 `latestStable`；规则变更时弹出提示。

## CLI

```bash
python3 scripts/sync_rules_auto.py
```

## 推荐部署

1. Fork 模板仓库：[examples/rules-feed-repo](../examples/rules-feed-repo/README.zh-CN.md)（含 GitHub Actions）。  
2. 法务改 `snapshots/` 下 YAML → push → CI 生成 `dist/feed.json` → 可选 webhook。  
3. Tax Agent 设置 `TAX_AGENT_RULES_FEED_URL` + `TAX_AGENT_AUTO_PUBLISH=1`。  
4. 回归失败则 **不发布**，旧 `latestStable` 继续服务。  
5. 生产环境务必设置 `TAX_AGENT_RULES_ADMIN_TOKEN` 与 `TAX_AGENT_RULES_WEBHOOK_SECRET`。

## 自检

```bash
python3 scripts/run_rule_registry_selfcheck.py
python3 scripts/run_feed_builder_selfcheck.py
python3 scripts/build_rules_feed.py
```
