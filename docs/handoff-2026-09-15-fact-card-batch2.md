# 交接 · 事实卡第二批 19 项（v1.29）

> 2026-09-15 · 维护者同意 19 项进卡；Find 从 Apple 官方文档查找。

## Find

Apple `HKQuantityTypeIdentifier` 文档只有 identifier 与 cumulative/discrete 聚合，**没有** Shortcuts「查找健康样本」选择器字面量。本切片 Find 仍 `skipped` / `shortcuts_find_unverified`，未写捷径。

## 已落地

- 腕温勾选；18 项 zip 升舱（日表 + registry + catalog 中文别名）。
- 累计型 `daily_agg=sum`（锻炼分钟不再被做成日均 1）。
- default prefs **32** 项（原 13 + 19）。build `pha-v2.3.53-batch2-19`。
- 回归：`python3 scripts/pha_m1_batch2_selfcheck.py`

## 日表回灌

```bash
PYTHONPATH=. python3 -c "from pha.sqlite_storage import backfill_passthrough_daily_from_l0, init_schema; init_schema(); print(backfill_passthrough_daily_from_l0('default'))"
```
