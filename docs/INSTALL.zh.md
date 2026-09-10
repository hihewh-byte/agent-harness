# PHA 安装指南

> **Language / 语言**：[English](INSTALL.md) · 中文（本文）

对齐发布版本 **`v0.4.0-beta.1`**（HTTP **8788**，UI 默认 **English**，回复语言由 `PHA_RESPONSE_LOCALE` 控制）。

## 诚实耗时

| 路径 | 时间 |
|------|------|
| 本机 + Ollama 模型已拉取 | 打开 UI **约 3–5 分钟** |
| 本机 + 首次 `ollama pull qwen2.5:7b-instruct` | **15–40 分钟**（下载约 4–5 GB） |
| Docker 首次构建 | **10–20+ 分钟**（镜像构建 + 模型） |

---

## 环境要求

| 组件 | 版本 | 说明 |
|-----------|---------|-------|
| Python | 3.10+ | 推荐 3.11 |
| Ollama | latest | 本地 LLM 运行时 — **聊天必需** |
| Tesseract OCR | 4+ | 上传截图前可选 |
| Docker | 24+ | 可选 |

### 模型（经 Ollama）

| 模型 | 用途 | 第一次就拉？ |
|-------|---------|------------|
| `qwen2.5:7b-instruct` | 默认聊天 + 视觉解析 | **是 — 只拉这个** |
| `deepseek-r1:14b` | 全局深度审计 | 可选 / 慢 |
| `qwen2.5:1.5b-instruct` | Shadow 路由 | 可选 |

```bash
# 最小集（推荐首次运行）
ollama pull qwen2.5:7b-instruct

# 全量（可选）
bash scripts/pull-models.sh
```

---

## 方案 A — 本机 Python（最快出结果）

```bash
git clone https://github.com/hihewh-byte/agent-harness.git
cd agent-harness

bash scripts/bootstrap.sh          # Python 3.10+; 创建 .venv + golden PASS
source .venv/bin/activate          # Windows: .venv\Scripts\activate

ollama pull qwen2.5:7b-instruct    # 已安装则跳过
python scripts/doctor.py

python -m pha.main
# → http://127.0.0.1:8788
```

**macOS 说明：** 系统 `python3` 经常是 3.9。若 bootstrap 失败，请安装 Python 3.10+：

```bash
brew install python@3.12
PHA_PYTHON=python3.12 bash scripts/bootstrap.sh
```

验证：

```bash
curl -s http://127.0.0.1:8788/health
```

重启助手（若使用本机 daemon 脚本）：

```bash
bash scripts/pha_restart_accept.sh
```

---

## 方案 B — Docker + 宿主机 Ollama（Mac GPU）

适合希望通过本机 Ollama 走 GPU 推理的场景。

```bash
brew install ollama          # macOS
ollama serve                 # 或 Ollama Desktop
ollama pull qwen2.5:7b-instruct

cp .env.example .env
docker compose up -d --build

curl http://127.0.0.1:8788/health
docker compose logs -f pha
```

**容器内环境变量：**

- `PHA_HOST=0.0.0.0`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

数据持久化在 `./data` 与 `./storage`（挂载卷）。

---

## 方案 C — Docker 捆绑 Ollama（仅 CPU）

用于没有单独安装 Ollama 的 Linux 服务器。**macOS 上 Docker 内无 GPU。**

```bash
cp .env.example .env
docker compose --profile bundled up -d --build
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

---

## 首次数据导入

1. 在 iPhone/Mac 上把 **Apple Health** 导出为 `export.zip`。
2. 打开 PHA → **Data import** 抽屉（UI 默认 English）。
3. 拖入 `export.zip` → 开始全量导入。
4. 锻炼数据包含在全量 `export.zip` 导入中（首次运行无需单独同步）。

空数仓也可用于冒烟测试聊天 UI。

---

## 语言环境 / 回复语言（v0.4.0-beta.1）

| 变量 | 效果 |
|----------|--------|
| `PHA_UI_LANG=en\|zh` | Dashboard 界面语言 |
| `PHA_RESPONSE_LOCALE=en\|zh` | API 未传 `response_locale` 时的默认 LLM 回复语言 |
| 顶栏 Language 开关 | 更新 UI，并在 `/api/chat` 发送 `response_locale` |

回复优先级：用户显式指令 → API `response_locale` → 消息启发式 → 环境默认值。

---

## 故障排查

| 现象 | 处理 |
|---------|-----|
| `Python 3.10+ is required` / macOS 上 bootstrap 失败 | 系统 `python3` 经常是 3.9 — `brew install python@3.12`，然后 `PHA_PYTHON=python3.12 bash scripts/bootstrap.sh` |
| `.venv uses Python < 3.10` | `rm -rf .venv` 后重新执行 `bash scripts/bootstrap.sh` |
| clone 后 Golden run 失败 | 再跑 `bash scripts/bootstrap.sh`；仍失败则把输出贴到 Issue |
| :8788 `Connection refused` | 进程未起来 — 重跑 `python -m pha.main` / `docker compose ps` |
| Ollama timeout | 检查 `OLLAMA_BASE_URL`；执行 `ollama list` |
| OCR 空 / 视觉失败 | `brew install tesseract`（上传截图前可选） |
| Docker 连不上 Ollama | 使用 `host.docker.internal`（Mac/Win）或 `--profile bundled` |
| `doctor.py` 警告缺少模型 | `ollama pull qwen2.5:7b-instruct` |
| 升级后 UI 仍是中文 | 清除站点数据或设置 `PHA_UI_LANG=en`；检查顶栏 Language |

诊断：

```bash
python scripts/doctor.py --verbose
bash scripts/run_selfchecks.sh
```

---

## 端口与卷

| 项 | 默认 |
|------|---------|
| HTTP | `8788`（`PHA_PORT`） |
| Ollama | `11434` |
| DB | `./data/pha_storage.db` |
| 用户资产 | `./storage/users/` |
