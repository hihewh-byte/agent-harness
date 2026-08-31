# 券商 Excel 模板映射索引 v1

| templateId | 文件 | 优先级 |
|------------|------|--------|
| `broker_ibkr_v1` | [broker_ibkr_v1.yaml](../mappings/broker_ibkr_v1.yaml) | P0 |
| `broker_schwab_v1` | [broker_schwab_v1.yaml](../mappings/broker_schwab_v1.yaml) · [解析说明](schwab-parser-v1.md) | P0 |
| `broker_fidelity_v1` | [broker_fidelity_v1.yaml](../mappings/broker_fidelity_v1.yaml) | P0 · History CSV |
| `broker_tiger_v1` | [broker_tiger_v1.yaml](../mappings/broker_tiger_v1.yaml) · 成交/分红 CSV | P1 · 已实现 |
| `broker_futu_v1` | [broker_futu_v1.yaml](../mappings/broker_futu_v1.yaml) · Transaction History CSV | P1 · 已实现 |
| `broker_vanguard_v1` | [broker_vanguard_v1.yaml](../mappings/broker_vanguard_v1.yaml) · Transaction history CSV | P1 · 已实现 |

未匹配模板时使用 `template_unknown`，风险等级至少为 **medium**（R005）。

编码阶段 Parser 应读取上述 YAML，将行映射为 `TaxEvent`（见 [canonical-data-model-v1.md](canonical-data-model-v1.md)）。
