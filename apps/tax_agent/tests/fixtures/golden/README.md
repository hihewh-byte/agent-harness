# Golden 测试集（v1）

发布 `cn_resident_us_equity` 规则快照为 `stable` 前，须满足 [eval-risk-manual-review-v1.md](../../docs/eval-risk-manual-review-v1.md) 中的用例数量。

## 目录

| 目录 | 用例数 | 说明 |
|------|--------|------|
| `deterministic/` | 20 | 期望 `netTaxDueCny` 精确 |
| `missing_data/` | 10 | 期望 `partial` + `medium` |
| `ambiguous/` | 5 | 期望 `high` |
| `credit_edge/` | 8 | 抵免边界 |
| `high_risk/` | 2 | 居民身份 / CRS 账户不一致 |

**合计 45 例**。生成：`python3 scripts/generate_golden_cases.py`；自检：`python3 scripts/run_golden_selfcheck.py`。

## 用例格式

见 `eval-risk-manual-review-v1.md` §4。
