# Tax Agent — OSS 发布说明

> 将 `tax_agent` 作为 [agent-harness](https://github.com/hihewh-byte/agent-harness) 第二参考应用公开时的检查清单。

## 绝不提交

| 路径 | 原因 |
|------|------|
| `docs/*.xlsx` | 真实富途税表（已 gitignore） |
| `.env` | 密钥与本地配置 |
| `.data/` | SQLite 会话与用户上传缓存 |
| `**/*.db` | 运行时数据库 |

## 公开 fixture

自检与演示仅依赖 `tests/fixtures/broker/`（合成或经 `build_futu_tax_2022_fixture.py` 脱敏生成）。

维护者本地从真实税表再生 fixture（**不提交源文件**）：

```bash
export FUTU_FIXTURE_SRC_ANNUAL=/path/to/Annual_Statement.xlsx
python scripts/build_futu_tax_2022_fixture.py
```

## 推送前门禁

```bash
python scripts/preflight_oss_publish.py          # 代码中无账号 token
python scripts/preflight_oss_publish.py --strict   # 发布树无 docs/*.xlsx、.env
python scripts/run_production_selfchecks.py
```

## Monorepo 布局

```text
agent-harness/
├── packages/harness_core/
├── pha/                    # 健康参考应用
└── apps/tax_agent/         # 税务参考应用（本仓库同步目标）
```

同步脚本（在 `tax_agent` 根目录）：

```bash
bash scripts/sync_to_agent_harness.sh /path/to/agent-harness
```

## 运行（克隆后）

```bash
cd agent-harness/apps/tax_agent
bash scripts/bootstrap_tax.sh
tax-agent app
```

LLM 可选：内置 `ollama_local`（无需 PHA）；同仓安装 PHA 时自动复用 `pha.llm_provider`。
