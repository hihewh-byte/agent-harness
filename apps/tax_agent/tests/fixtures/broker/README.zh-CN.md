# 脱敏券商对账单 Fixtures

本目录包含**合成/脱敏**的券商导出样例，用于解析器自检与 `golden/anonymized_broker` 端到端测算回归。

| 文件 | 券商 | 说明 |
|------|------|------|
| `schwab_transactions_realistic.csv` + `schwab_realized_gl.csv` | Schwab | 流水 + 已实现盈亏 |
| `schwab_rsu_activity.csv` | Schwab | RSU 归属 / ESPP / RSU 出售自动识别 |
| `ibkr_dividends.csv` + `ibkr_trades.csv` | IBKR | 股息 + 交易 |
| `fidelity_activity_realistic.csv` + `fidelity_gains_losses.csv` | Fidelity | 账户活动 + G/L |
| `fidelity_rsu_activity.csv` | Fidelity | RSU VEST / RSU 出售 |
| `tiger_trades.csv` / `tiger_dividends.csv` | 老虎 | 成交 / 分红 |
| `futu_transaction_history.csv` | 富途 | Transaction History（CSV） |
| `futu_multiyear_tax_statement.xlsx` | 富途 | 2022–2024 年度账单（Excel，多年测算示例） |
| `vanguard_transaction_history.csv` | Vanguard | Transaction history |

重新生成 anonymized golden：

```bash
python3 scripts/build_anonymized_golden_cases.py
python3 scripts/run_golden_selfcheck.py
```
