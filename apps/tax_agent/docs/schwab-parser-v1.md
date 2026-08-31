# Schwab 对账单解析说明 v1

> **模板 ID**：`broker_schwab_v1`  
> **实现**：`tax_agent/parser/schwab_parser.py`

## 支持的导出类型

### 1. Transaction History CSV（官网主路径）

路径：Schwab.com → **Accounts** → **History** → 选账户与日期 → **Export** → CSV。

**文件特征**：

- 前几行为账户元数据（账户号、导出名、时间戳），**不是**表头。
- 真实表头含：`Date`, `Action`, `Symbol`, `Description`, `Quantity`, `Price`, `Fees & Comm`, `Amount`。

**解析规则**：

| Action 示例 | TaxEvent |
|-------------|----------|
| Qualified Dividend / Cash Dividend | DIVIDEND |
| Bank Interest / Credit Interest | INTEREST |
| Foreign Tax Paid / NRA Tax Adj | WITHHOLDING_TAX |
| Sell | CAPITAL_GAIN（**inferred**，见下） |
| Buy / Transfer / Deposit | 跳过 |

**Sell 行说明**：`Amount` 为成交回款，**不是**已实现损益。系统标记 `classification_status=inferred`，并提示上传 Realized Gain/Loss 报告。

### 2. Realized Gain/Loss CSV（推荐用于资本利得）

路径：Reports → **Realized Gain/Loss** → Export。

表头含 `Closed Date`、`Gain/Loss ($)` 等 → 直接解析为 **CAPITAL_GAIN**（`confirmed`）。

### 3. 多文件合并

同一会话 `sessionId` 先上传 Transaction History，再上传 G/L CSV：

- 自动 **dedupe**：存在 G/L 时丢弃 Transaction 中 inferred 的 Sell 行。
- 分红、利息、预扣税保留。

## 自检

```bash
python3 scripts/run_schwab_parser_selfcheck.py
```

样例文件：

- `tests/fixtures/broker/schwab_transactions_realistic.csv`
- `tests/fixtures/broker/schwab_realized_gl.csv`

## 限制（v1）

- 不支持 PDF 月结单 OCR。
- Buy 行不进入资本利得（无卖出实现）。
- Reinvest Dividend 按分红处理，不展开再投资买入成本。
