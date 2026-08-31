# 规则本地入库 (inbox)

将待发布快照放在：

`cn_resident_us_equity/YYYY.MM.DD/`

包含 `rules.yaml`、`fx_policy.yaml`、`disclaimers.yaml`，并添加 `.ready` 文件。

然后执行：

```bash
python3 scripts/sync_rules_auto.py
```

或调用 `POST /rules/sync`（需 `TAX_AGENT_RULES_ADMIN_TOKEN`）。
