# Tax Agent 部署与验证（D4）

## 环境要求

| 项 | 版本/说明 |
|----|-----------|
| Python | **3.10+**（推荐 3.12，与 CI 一致） |
| 依赖 | `cd tax_agent && pip install -e .` |
| Ollama（可选） | 本地 `11434`；叙述层模型如 `qwen2.5:1.5b-instruct` |

## 启动

```bash
cd tax_agent
python -m tax_agent.api.server --port 8790
```

浏览器打开 `http://127.0.0.1:8790/`。

## 生产门槛（28 项）

```bash
python scripts/run_production_selfchecks.py
```

## Ollama 真机叙述 smoke（D1，可选）

```bash
TAX_OLLAMA_SMOKE=1 python scripts/run_chat_ollama_smoke.py
```

通过标准：provenance 2 次内 ≥1 次 `narrated=true`；policy 2 次内 ≥1 次 narrated + `citationAudit.ok`。

## 主观抽测（D3）

见 `evals/chat_manual_rubric.json`（10 段样本 × 自然度/有用性/信任感 1–5 分，目标均分 ≥4）。

## CI

`.github/workflows/production-selfcheck.yml`：push/PR 跑 28 项；Ollama job 为 `continue-on-error`（无 GPU 环境不阻断合并）。
