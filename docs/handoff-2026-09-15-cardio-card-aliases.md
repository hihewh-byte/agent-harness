# 交接 · 有氧恢复事实卡勾选 + 中文别名（v1.28）

> 2026-09-15 · 维护者：M1 本切片先完成勾选与中文别名；P21c Find 不猜。

## 已落地

- `data/fact_card_prefs.json` `users.default.enabled_metric_ids` 含 `cardio_recovery_1min_bpm`。Registry `enabled_default` 仍为 false。
- catalog / `intent_hints` 含：有氧恢复、有氧恢复能力、心肺恢复、心率恢复、一分钟心率恢复、运动后心率恢复。
- build：`pha-v2.3.52-cardio-card`。PRD v1.28。
- 回归：`python scripts/pha_p21b_cardio_recovery_selfcheck.py`

## 未开

- **P21c**：捷径 Find 须真机抄录；`shortcut_skip_reason=shortcuts_find_unverified`。
- **步行稳定性**：英文 L0 账本可点名；中文「步行稳定性」无 catalog key，Loop A 不能挂钩，需另开升舱。

## Loop A 边界（本切片不改 Loop 代码）

Loop 只给**已有 catalog key**加口语别名。未知指标（无 key）= 人审拒绝。本机「同意」写 `data/loop_local_aliases.json`，不改仓库 catalog。
