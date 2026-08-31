# Tax Agent Docker 部署（v1）

## 前置条件

- Docker 20+ / Docker Compose v2
- （可选）宿主机已运行 Ollama，供对话编排使用

## 快速启动

```bash
cd tax_agent
cp .env.example .env
# 按需编辑 .env（规则 Feed、Webhook、Admin Token 等）

docker compose up --build -d
open http://127.0.0.1:8790/
```

健康检查：`curl http://127.0.0.1:8790/health`

## 镜像说明

| 项 | 说明 |
|----|------|
| 基础镜像 | `python:3.12-slim` |
| 监听 | `0.0.0.0:8790` |
| 数据卷 | `/data/tax_agent.db`（SQLite） |
| 规则包 | 构建时 COPY `rules/`；compose 可挂载宿主机 `./rules` 只读覆盖 |

## 环境变量（生产建议）

```bash
# 规则自动同步
TAX_AGENT_RULES_FEED_URL=https://your-cdn.example.com/feed.json
TAX_AGENT_AUTO_PUBLISH=1
TAX_AGENT_RULES_SYNC_ON_STARTUP=1
TAX_AGENT_RULES_ADMIN_TOKEN=<强随机串>
TAX_AGENT_RULES_WEBHOOK_SECRET=<与 GitHub webhook 一致>

# LLM（容器访问宿主机 Ollama）
OLLAMA_BASE_URL=http://host.docker.internal:11434
TAX_AGENT_MODEL=qwen2.5:7b-instruct
TAX_AGENT_LLM_ENABLED=1

# 纯规则引擎模式（无 LLM）
# TAX_AGENT_LLM_ENABLED=0

# RBAC（启用后普通用户需 TAX_AGENT_USER_TOKEN）
TAX_AGENT_AUTH_ENABLED=1
TAX_AGENT_USER_TOKEN=<user-secret>
TAX_AGENT_EXPERT_TOKEN=<expert-secret>
TAX_AGENT_RULES_ADMIN_TOKEN=<admin-secret>

# 规则发布后自动回滚
TAX_AGENT_RULES_AUTO_ROLLBACK=1
TAX_AGENT_RULES_MONITOR_HOURS=72
```

请求头：`Authorization: Bearer <token>` 或 `X-Tax-Agent-Token: <token>`。  
`GET /auth/me` 可查看当前角色。

Linux 宿主机若 `host.docker.internal` 不可用，可在 `docker-compose.yml` 改为 `extra_hosts: ["host.docker.internal:host-gateway"]` 或填写宿主机局域网 IP。

## 规则 Feed 联动

1. 将 `examples/rules-feed-repo` fork 为独立仓库
2. CI `publish-feed.yml` 在 push 时生成 `fx_rates.yaml` + `feed.json`
3. Tax Agent 配置 `TAX_AGENT_RULES_FEED_URL` 指向 `feed.json` 静态 URL
4. 可选配置 `TAX_AGENT_WEBHOOK_URL` 在 push 后立即触发 `POST /rules/webhook`

详见 [rule-auto-update-v1.md](rule-auto-update-v1.md)。

## 运维命令

```bash
docker compose logs -f tax-agent
docker compose restart tax-agent
docker compose down
docker compose exec tax-agent curl -s http://127.0.0.1:8790/rules/status
```

## 非目标（v1）

- 镜像内不包含 Ollama 模型（体积过大）；LLM 仍建议宿主机或独立推理服务
- 未内置 TLS 终止；生产应在反向代理（Caddy / Nginx）后部署 HTTPS
