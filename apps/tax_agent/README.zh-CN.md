# Tax Agent（报税 Agent）

> **状态**：v1 技术规格 + **可运行计算引擎** + 60 项 golden 自检  
> **模型说明**：本仓库由 **Composer** 编写与维护。  
> **首场景**：中国大陆税务居民 · CRS 语境 · 海外收入（优先美股）

## 快速开始（agent-harness monorepo）

```bash
cd agent-harness/apps/tax_agent
bash scripts/bootstrap_tax.sh    # 安装 harness_core + 38 项生产自检
tax-agent app                    # http://127.0.0.1:8790
```

独立开发仓同步到 monorepo：`bash scripts/sync_to_agent_harness.sh /path/to/agent-harness`  
发布门禁见 [docs/OSS_PUBLISH.md](docs/OSS_PUBLISH.md)。

## 快速开始（独立目录）

```bash
cd tax_agent
# 需要 Python 3.10+（见 pyproject.toml requires-python）
python3 --version
pip install -e .            # 含 openpyxl / FastAPI 等全部运行时依赖
python3 scripts/preflight_ci.py   # 可选：检查环境与生成 xlsx fixtures
python3 scripts/run_all_selfchecks.py   # 内含 preflight，19 项自检

# 推荐：稳定启动器（后台服务 + 浏览器）
tax-agent app          # 打开控制台 http://127.0.0.1:8790/app
tax-agent open --path /   # 直接打开报税助手

# 或 macOS 双击：apps/TaxAgent.command

# 低级：仅启动 API（Docker 等同此命令）
tax-agent-api

# 或 Docker（见 docs/deployment-docker-v1.md）
# cp .env.example .env && docker compose up --build -d
# 浏览器打开 http://127.0.0.1:8790/ 上传对账单并对话测算

# 复制 .env.example；LLM 与 PHA 共用 Ollama
# 16GB Mac 推荐：qwen2.5:7b-instruct（快、省内存）
# 复杂推演可设 TAX_AGENT_MODEL=deepseek-r1:14b（更慢，部分模型不支持 tool calling）
# 数据默认写入 tax_agent/.data/tax_agent.db（SQLite）
# 临时改用内存：TAX_AGENT_MEMORY=1 tax-agent-api
```

### API 示例

```bash
# 上传对账单
curl -F "file=@tests/fixtures/broker/ibkr_mini.xlsx" http://127.0.0.1:8790/tax/upload

# 测算（按规则快照月度汇率折算）
curl -X POST http://127.0.0.1:8790/tax/compute \
  -H "Content-Type: application/json" \
  -d '{"datasetId":"<上一步返回>","taxYear":2024,"residentStatus":"cn_tax_resident","fxPolicy":"safe_harbor_monthly"}'

# 报告 / 审计包 / 人工复核工单
curl http://127.0.0.1:8790/tax/report/<runId>
curl http://127.0.0.1:8790/tax/audit/<runId>
curl -X POST http://127.0.0.1:8790/tax/review/tickets \
  -H "Content-Type: application/json" \
  -d '{"runId":"<runId>","reason":"需专家复核"}'
curl http://127.0.0.1:8790/tax/review/tickets

# 规则状态与同步
curl http://127.0.0.1:8790/rules/status
curl -X POST http://127.0.0.1:8790/rules/sync -H "X-Tax-Agent-Admin-Token: <token>"
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [tax-agent-architecture-v1.md](docs/tax-agent-architecture-v1.md) | 总览架构、API、MVP |
| [v1-scope-crs-us-equity.md](docs/v1-scope-crs-us-equity.md) | v1 场景边界（冻结） |
| [canonical-data-model-v1.md](docs/canonical-data-model-v1.md) | 标准数据模型与审计追溯 |
| [rule-versioning-pipeline-v1.md](docs/rule-versioning-pipeline-v1.md) | 法规版本化发布流程 |
| [rule-auto-update-v1.md](docs/rule-auto-update-v1.md) | 规则 Feed 自动同步、Webhook、CI |
| [cn-us-equity-calculation-spec-v1.md](docs/cn-us-equity-calculation-spec-v1.md) | 中国口径 · 美股测算 |
| [eval-risk-manual-review-v1.md](docs/eval-risk-manual-review-v1.md) | 评估、风险、人工复核 |
| [llm-integration-v1.md](docs/llm-integration-v1.md) | 本地模型推荐与 tool calling |
| [mappings-index-v1.md](docs/mappings-index-v1.md) | 券商模板索引 |
| [examples/rules-feed-repo/README.zh-CN.md](examples/rules-feed-repo/README.zh-CN.md) | 独立规则仓库 + Feed CI 模板 |
| [deployment-docker-v1.md](docs/deployment-docker-v1.md) | Docker / Compose 部署 |

## 运行时模块

| 模块 | 职责 |
|------|------|
| `tax_agent/compute_engine.py` | 计税、抵免、净亏损钳制、审计包 |
| `tax_agent/fx_rates.py` + `fx.py` | 按交易日月度/年度中间价折算（Feed 下发 `fx_rates.yaml`） |
| `tax_agent/risk_engine.py` | R001–R010 风险分级 |
| `tax_agent/rules_loader.py` | YAML 规则快照（含 `snapshot_meta.status`） |
| `tax_agent/rule_registry.py` | 快照校验、发布、回滚 |
| `tax_agent/rule_auto_updater.py` | Feed 同步 + golden 回归 + 自动发布 |
| `tax_agent/report_composer.py` | Markdown 报告 |
| `tax_agent/storage/sqlite_store.py` | SQLite 持久化 + 复核工单 |
| `tax_agent/llm_orchestrator.py` | Ollama tool calling + JSON/规则引擎回退 |
| `tax_agent/static/index.html` | Web 对话 UI（报告卡片、审计包下载、规则状态） |

## Schema、规则、映射

- `schemas/` — JSON Schema  
- `rules/cn_resident_us_equity/snapshots/2026.06.01/` — 规则包（`rules.yaml`、`fx_policy.yaml`、`fx_rates.yaml`、`disclaimers.yaml`）  
- `mappings/` — 6 家券商模板（IBKR / Schwab / Fidelity / Tiger / Futu / Vanguard 均已实现解析器）  
- `data/pboc_usd_cny_middle.yaml` — PBOC 美元/CNY 中间价数据集（经 `scripts/build_fx_rates_snapshot.py` 生成 `fx_rates.yaml`）  
- `templates/advisory_report_v1.yaml`  
- `db/tax_agent_schema.sql`  

### v1 已知简化（文档与实现一致）

- **境外税收抵免**：当前为 `per_item_limit`（分项限额 `min(境外税, 应纳税)`）近似，非完整「分国不分项」或综合所得汇算逻辑。  
- **credit_limit**：抵免上限规则合并在 `rules.yaml` 的 `credit` 段，未拆独立 `credit_limit.yaml`。  
- **境内综合所得**：`filingScope=includes_domestic` + `domesticIncome` 字段可合并工资薪金等（累进税率），与境外分类所得分别计税后合计；未填境内收入时仍触发 R008。  
- **股权激励**：Schwab/Fidelity 等解析器自动识别 RSU 归属、ESPP 折扣、RSU 出售行 → `STOCK_COMPENSATION`；按 20% 草稿计税，触发 R007 须专家复核。  
- **汇率（合规申报）**：默认 `cn_annual_filing` / `cn_supplemental`；每次测算附带 **多口径对照**、**分月明细**、**滞纳金估算**；见 [cn-fx-filing-rules-v1.md](docs/cn-fx-filing-rules-v1.md)。
- **汇率/规则更新**：`scripts/sync_pboc_fx_rates.py` 拉取 PBOC 中间价；规则 Feed 同步见 [pboc-fx-sync-v1.md](docs/pboc-fx-sync-v1.md) 与 `TAX_AGENT_RULES_FEED_URL`。

## 自检脚本

```bash
python3 scripts/run_production_selfchecks.py   # **生产门槛**（富途 v1，必须通过）
python3 scripts/run_all_selfchecks.py   # 全量（含已弃用多券商脚本）
python3 scripts/run_golden_selfcheck.py # 60 项 golden（含 RSU/ESPP + 境内合并 + 7 项脱敏 + 5 项 high_risk）
python3 scripts/build_anonymized_golden_cases.py  # 从 broker fixtures 再生 anonymized golden
python3 scripts/run_rule_publish_monitor_selfcheck.py
python3 scripts/run_auth_rbac_selfcheck.py
python3 scripts/run_fx_provider_selfcheck.py
python3 scripts/run_review_ticket_selfcheck.py
python3 scripts/run_review_sla_selfcheck.py
python3 scripts/run_rule_registry_selfcheck.py
python3 scripts/run_feed_builder_selfcheck.py
python3 scripts/run_tiger_parser_selfcheck.py
python3 scripts/run_futu_parser_selfcheck.py
python3 scripts/run_vanguard_parser_selfcheck.py
python3 scripts/build_fx_rates_snapshot.py  # 从 PBOC 数据集生成 fx_rates.yaml
```

## 非目标（v1）

- 不向税务机关自动申报  
- 不替代持证税务师法律意见  

## 合规提示

本系统为**信息服务 / 辅助决策**；高风险场景自动创建人工复核工单（`POST /tax/review/tickets`），未输出最终税额前需专家确认。
