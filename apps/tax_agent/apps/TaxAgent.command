#!/bin/bash
# 双击启动 Tax Agent（macOS）：后台服务 + 打开浏览器
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

export TAX_AGENT_LLM_ENABLED="${TAX_AGENT_LLM_ENABLED:-0}"
"$PY" -m tax_agent.launcher app --path /
echo ""
echo "报税助手: http://127.0.0.1:8790/"
echo "控制台:   http://127.0.0.1:8790/app"
read -r -p "按回车关闭此窗口（服务继续在后台运行）…" _
