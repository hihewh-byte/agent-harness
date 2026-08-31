# Tax Agent 文档路线图 v1

| 文档 | 状态 | 对应 Todo |
|------|------|-----------|
| v1-scope-crs-us-equity.md | Frozen | define-v1-scope |
| canonical-data-model-v1.md | Frozen | design-canonical-model |
| rule-versioning-pipeline-v1.md | Frozen | build-rule-versioning |
| cn-us-equity-calculation-spec-v1.md | Frozen | plan-cn-us-calculation |
| eval-risk-manual-review-v1.md | Frozen | set-eval-and-risk |
| tax-agent-architecture-v1.md | Frozen | 总览 |
| mappings-index-v1.md | Frozen | 券商模板库 |
| deployment-docker-v1.md | Frozen | Docker 部署 |
| rule-auto-update-v1.md | Frozen | 规则 Feed / 72h 监控 |

## 已实现运行时

- `tax_agent/compute_engine.py` + `domestic_income.py` — 境外分类计税 + 境内综合所得累进税率合并
- `tax_agent/stock_compensation.py` + `parser/stock_comp_detect.py` — RSU/ESPP 券商行自动识别 + 草稿计税（R007）
- `tax_agent/risk_engine.py` — 风险规则 + high-risk 自动建单
- `tax_agent/fx_rates.py` + `fx.py` — PBOC 中间价（Feed 快照注入）
- `tax_agent/parser/broker_parser.py` — 6 券商 + `template_unknown` 列映射提示
- `tax_agent/parser/{schwab,fidelity,tiger,futu,vanguard}_parser.py`
- `tax_agent/parser/template_mapper.py` + `generic_mapped_parser.py` — 列映射建议 + 确认后重解析
- `tax_agent/review_workflow.py` + `review_sla_monitor.py` — 专家复核 + SLA 预警/Webhook
- `tax_agent/auth.py` — RBAC（user / tax_expert / tax_rule_admin）
- `tax_agent/rule_publish_monitor.py` — 72h 监控与自动回滚
- `tax_agent/api/app.py` — REST + Web UI + 工单/映射 API
- `tax_agent/storage/sqlite_store.py` — 持久化 + mappingHints 存储
- `scripts/run_golden_selfcheck.py` — **60** 例 golden（含 RSU/ESPP + domestic merge）
- `scripts/run_all_selfchecks.py` — **23** 项自检汇总
- `tax_agent/llm_orchestrator.py` — LLM + `template_unknown` 映射引导

## 待编码（后续 PR）

- 稿酬/特许权使用费其他高级场景（捐赠扣除等）
- 专家 UI 工作台增强（批量处理、邮件模板）
- Feed 生产 gh-pages 完整发布（用户 fork + CDN）
- 数据留存/删除 API、TLS、压测
- 工单邮件/Slack 富文本模板
- CI：`.github/workflows/tax-agent-ci.yml`（Python 3.10/3.12 + `preflight_ci`）
