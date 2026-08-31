# Tax Agent 规则 Feed 仓库模板

将本目录 **复制为独立 Git 仓库**（或由法务团队 fork），用于维护税法 YAML 并自动生成 Tax Agent 可消费的 `feed.json`。

## 目录结构

```text
manifest.yaml                 # 规则包元数据
snapshots/
  2026.06.01/
    snapshot_meta.yaml          # status=review|stable、生效日
    rules.yaml                  # 税率与税目（核心）
    fx_policy.yaml
    fx_rates.yaml              # CI 从 PBOC 数据集自动生成
    disclaimers.yaml
data/
  pboc_usd_cny_middle.yaml     # 美元/CNY 中间价（人工维护）
scripts/
  build_fx_rates.py
  build_feed.py
  validate_feed.py
.github/workflows/
  publish-feed.yml              # push 后构建 + 可选 webhook
dist/
  feed.json                     # CI 产出（勿手改）
```

## 法务如何更新税法

1. 复制最新快照目录，例如 `snapshots/2026.09.01/`
2. 修改 `rules.yaml` 中的 `rate`、`appliesTo` 等
3. 在 `snapshot_meta.yaml` 中设置：
   - `status: review`（首次提交，待 Tax Agent 回归）
   - `effectiveFrom: "2026-01-01"`
   - `changelog_zh: 变更说明`
4. `git push` 到 `main`

## CI 行为

`publish-feed.yml` 在 push 后：

1. 运行 `build_fx_rates.py` → 各快照目录 `fx_rates.yaml`
2. 运行 `build_feed.py` → `dist/feed.json`
3. `validate_feed.py` 校验结构
4. 上传 Artifact
5. （可选）`curl` 触发 Tax Agent `POST /rules/webhook`

### GitHub Secrets（可选）

| Secret | 说明 |
|--------|------|
| `TAX_AGENT_WEBHOOK_URL` | 如 `https://tax.example.com/rules/webhook` |
| `TAX_AGENT_WEBHOOK_SECRET` | 与 Tax Agent `.env` 中 `TAX_AGENT_RULES_WEBHOOK_SECRET` 一致 |

### Tax Agent 侧配置

```bash
# 方式 A：拉取 raw feed URL（公开仓库或内网静态站）
TAX_AGENT_RULES_FEED_URL=https://raw.githubusercontent.com/YOUR_ORG/tax-rules-feed/main/dist/feed.json
TAX_AGENT_AUTO_PUBLISH=1
TAX_AGENT_RULES_SYNC_ON_STARTUP=1

# 方式 B：仅 webhook（push 后 Agent 自己 sync）
TAX_AGENT_RULES_WEBHOOK_SECRET=...
```

## 本地构建

```bash
pip install pyyaml
python scripts/build_fx_rates.py
python scripts/build_feed.py --output dist/feed.json
python scripts/validate_feed.py dist/feed.json
```

或在 tax_agent 主仓库：

```bash
python scripts/build_rules_feed.py --repo examples/rules-feed-repo
```

## 注意

- 本模板 **不** 自动解读国税网站条文；法务负责 YAML 正确性。
- 新快照默认 `review`；Tax Agent 回归通过且 `TAX_AGENT_AUTO_PUBLISH=1` 后才会升为 `latestStable`。
