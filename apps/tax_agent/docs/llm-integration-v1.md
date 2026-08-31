# Tax Agent · 本地 LLM 接入（PHA 模块）v1

## 架构

```text
tax_agent/llm_orchestrator.py
    → tax_agent/pha_llm.py（sys.path 挂载 personal_health_agent）
    → pha.llm_provider.OllamaProvider
    → Ollama http://127.0.0.1:11434
```

对话失败时**自动回退**规则引擎（`chat_orchestrator.py`），不影响上传与计税。

支持 **Ollama tool calling**（`compute_tax` / `request_upload` / `show_report` / `reply_only`）。
`deepseek-r1` 等模型不支持 tools 时自动回退 JSON 编排。

## 环境变量

| 变量 | 说明 |
|------|------|
| `TAX_AGENT_LLM_ENABLED` | `1` 启用（默认），`0` 仅规则 |
| `TAX_AGENT_MODEL` | 显式指定 Ollama 模型名 |
| `OLLAMA_MODEL` | 未设 `TAX_AGENT_MODEL` 时回退 |
| `OLLAMA_BASE_URL` | 与 PHA 相同 |
| `TAX_AGENT_LLM_TIMEOUT_SECONDS` | 默认 120 |
| `TAX_AGENT_LOW_RAM` | `1` 时优先 **qwen2.5:7b**（16GB Mac 默认） |
| `TAX_AGENT_UNLOAD_HEAVY_MODELS` | `1` 时对话前卸载 gemma4:26b / vision |

复制 [../.env.example](../.env.example)，或与 `personal_health_agent/.env` 共用。

## 推荐模型（Ollama 本地）

| 优先级 | 模型 | 适用场景 |
|--------|------|----------|
| **首选** | `qwen2.5:14b-instruct` / `qwen2.5:14b` | 中文说明、数值推理、JSON 编排；报税对话 **最均衡** |
| 轻量 | `qwen2.5:7b-instruct` | 机器内存 ≤16GB、响应更快 |
| 强推理 | `deepseek-r1:14b` / `deepseek-r1:8b` | 复杂场景推演、多轮澄清；**更慢** |
| 通用回退 | `llama3.1:8b` | 已安装时的兜底 |

**不推荐**：

- `llama3.2-vision` / `llava` — 视觉模型，不适合纯文本报税编排  
- 仅用于 PHA 化验单清洗的 `gemma4:e4b` — 医疗 JSON 向，非报税最优  

安装示例：

```bash
ollama pull qwen2.5:14b-instruct
# 或
ollama pull qwen2.5:7b-instruct
```

## API

- `GET /tax/llm/status` — 模型解析、`toolsSupported`、`tools` 列表、推荐说明  
- `POST /tax/llm/prepare` — 卸载占内存的大模型后再对话  
- `POST /tax/upload/batch` — 一次上传多个 CSV/xlsx（同 session）  
- `POST /tax/chat` — 响应含 `llm.mode`（`llm_tools` 表示已执行工具）；支持多轮历史（最近 8 条）

## 自检

```bash
python3 scripts/run_tool_executor_selfcheck.py
python3 scripts/run_llm_selfcheck.py
```

无 Ollama 时会 SKIP LLM 用例，规则回退仍须 PASS。
