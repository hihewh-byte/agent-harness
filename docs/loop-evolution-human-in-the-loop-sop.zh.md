# Loop + Reflection 人机协同 SOP

> **定位**：harness-core **Harness Loop** 的 **参考实现插件**（可运行脚本暂由 PHA 托管，直至抽离至 `packages/harness_loop`）。  
> **运维手册**：在**禁止 auto-merge** 前提下，安全演进 catalog 别名（Loop A / R2）与 T0 事实（Loop B）。
> 配套 [`harness-loop-reflection-architecture.zh.md`](harness-loop-reflection-architecture.zh.md) ·
> 挂载指南 [`examples/loop_reference_pha.md`](../examples/loop_reference_pha.md)。

**铁律（不可豁免）：**

1. **禁止 auto-merge** — 脚本只产出 proposal / verdict；合入必须人工 PR。
2. **合入前 full-veto** — catalog 别名须 `pha_loop_promote_candidate.py --full-veto` 通过。
3. **写盘前 confirm** — T0 apply 必须 `--apply --confirm YES`。
4. **拒毒性 token** — 非结构化字符串（如 `Query`、裸英文碎片）不得进入 `metric_aliases`。
5. **Loop 不改路由/registry** — 仅 catalog 别名与 T0 事实；Loop PR 不得改 harness profile。

---

## 角色

| 角色 | 职责 |
|------|------|
| **运维** | 跑 harvest / promote / adopter；压测时保持 PHA + Ollama |
| **审阅人** | 人审 proposal；剔除 deferred/毒性行；批准 PR |
| **CI** | 每 PR 跑离线 selfcheck + consensus 门禁 |

---

## 路径 A — Catalog 别名（Loop A → R2）

### A1. 生成 proposal（离线）

```bash
cd agent-harness
export PYTHONPATH=.

PHA_E2E_JSONL=/path/to/en_stress_50x_*.jsonl \
  bash scripts/pha_loop_run_from_e2e.sh
```

产物：`reports/loop/proposals/alias_proposal_*.json`、`reflection_*.json`。

### A2. 人审（强制）

打开 proposal JSON，对每条 `accepted_catalog` / `patch_ops`：

| 检查项 | 通过 | 拒绝 |
|--------|------|------|
| 目标 metric 存在于 catalog | `steps`、`hrv` 等 | 未知 metric |
| 别名符合人类直觉 | `多少步` | `Query`、OCR 垃圾 |
| 无跨 metric 重复 | 每 metric 唯一 | `hrv←Query` 类噪声 |
| 仅 Tier-A | catalog 层 | slot 误升为 catalog |

必要时整理为 `scripts/fixtures/loop_alias_proposal_curated.json`（见现有样例）。
拒绝的 harvest 写 `*.REJECTED.json` 侧车并注明原因。

### A3. Promote / full-veto

```bash
python3 scripts/pha_loop_promote_candidate.py \
  --proposal scripts/fixtures/loop_alias_proposal_curated.json \
  --full-veto
```

依赖：8788 PHA、测试资产、`PHA_UNIVERSAL_ATTACHMENT_LANE=1`（3H nightly）。

Verdict：`reports/loop/verdicts/promote_verdict_*.json` 须 `passed: true`。

### A4. 合入 catalog（人工 PR）

1. 改 `rules/health_intent_catalog.json` — 在对应 metric 下追加别名。
2. 里程碑时更新 `docs/harness-loop-reflection-architecture.*.md` §7。
3. 开 PR → CI 全绿 → merge（PR 正文引用 verdict 文件）。
4. **首条范例：** PR #2，`steps←多少步`，verdict `promote_verdict_20260713T045002Z`。

---

## 路径 B — T0 事实 + CHB（Loop B）

### B1. 生成 ingest proposal（仅提案）

```bash
python3 scripts/pha_t0_ingest_proposal.py \
  --input /path/to/parsed_or_e2e_payload.json \
  --user-id <user_id>
```

产物：`reports/loop/t0_ingest_proposals/t0_ingest_proposal_*.json`。

生产验证须用**真实 3H 附件解析 JSON**，勿用 demo fixture。

### B2. Gated apply + CHB 重编译

```bash
PROPOSAL=reports/loop/t0_ingest_proposals/t0_ingest_proposal_*.json
python3 scripts/pha_t0_gated_adopter.py \
  --proposal "$PROPOSAL" \
  --apply --confirm YES --recompile-chb
```

验证：

```bash
python3 scripts/pha_persona_personalization_battery.py
# 检查 reports/chb/<user_id>/brief_*.json
```

### B3. CHB 日更（可选 cron — P2）

```bash
python3 scripts/pha_chb_daily_recompile.py
```

在真实数据上至少跑通一次 Path B 前，勿上无人值守 cron。

---

## Allowlist 摘要

| 动作 | 无需 PR | 须人工 PR + CI |
|------|---------|----------------|
| 跑 harvest / distiller | ✅ | — |
| 写 proposal JSON | ✅（reports 不入库） | — |
| `--full-veto` verdict | ✅（仅证据） | — |
| 改 `health_intent_catalog.json` | — | ✅ |
| 生产用户 T0 `--apply` | — | ✅（运维 + confirm） |
| 改 harness profile / 路由 | — | ❌（Loop 范围外） |

---

## 故障处理

| 现象 | 处理 |
|------|------|
| `static_veto` 非空 | 修 proposal，禁止 merge |
| full-veto nightly 失败 | 先修基线（3H/Bank），再重跑 veto |
| CI selfcheck 红 | 本地 `bash scripts/run_selfchecks.sh` 定位 |
| 毒性 harvest 行 | 拒绝 + 侧车记录；做人审子集 |
| apply 后 CHB stale | 重跑 `--recompile-chb`；跑 persona battery |

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-09-11 | v1.2 — 路径 B：同意 → 本机 `data/loop_local_aliases.json`（不落仓库 catalog） |
| 2026-09-11 | v1.1 — 周更 harvest + 多渠道通知 + 人审批准页（不落 catalog） |
| 2026-07-13 | v1.0 — 首条人审 alias 已合入（`steps←多少步`，PR #2） |

---

## 路径 W — 每周自动 harvest + 通知 + 审批（不落库）

> **铁律**：自动部分只到「提案 + 通知」；**永不**自动改仓库 `health_intent_catalog.json`。
>
> **路径 B（本机生效）**：事实卡 / 审批页点「同意」→ 写入 gitignored 的 `data/loop_local_aliases.json`，本机 `catalog_metric_aliases` / 意图匹配立刻可用。可选 `PHA_LOOP_APPROVE_FULL_VETO=1` 或 `--full-veto` 另跑 full-veto；合入仓库 catalog 仍需人工 Ready PR。

### W1. 本机一键（先 dry-run）

```bash
cd personal_health_agent
source .venv/bin/activate
export PYTHONPATH=.
export PHA_LOOP_APPROVE_TOKEN="与 .env 中 PHA_INGEST_TOKEN 相同或单独密钥"
export PHA_LOOP_BASE_URL="http://127.0.0.1:8788"   # 手机同网可用 Mac.local:8788

# 通知 dry-run（不发邮件/webhook；仍写 PHA inbox + pending）
python3 scripts/pha_loop_weekly_harvest.py \
  --e2e-jsonl reports/e2e/某次失败.jsonl

# 真正推送：Mac 通知 / 邮件 / webhook（飞书·Slack·Pushover 等）
export PHA_LOOP_NOTIFY_APPLY=1
export PHA_LOOP_WEEKLY_CHANNELS=pha_inbox,mac,email,webhook
export LOOP_NOTIFY_WEBHOOK_URL="https://…"          # 手机可达的 webhook
export LOOP_NOTIFY_WEBHOOK_FORMAT=feishu            # 或 slack / generic
export PHA_LOOP_SMTP_HOST=smtp.example.com
export PHA_LOOP_NOTIFY_EMAIL_TO=you@example.com
export PHA_LOOP_SMTP_USER=…
export PHA_LOOP_SMTP_PASSWORD=…
python3 scripts/pha_loop_weekly_harvest.py --e2e-jsonl … --notify-apply
```

产物：`reports/loop/approvals/pending/loopapr_*.json` · `data/loop_inbox/` · 通知里的 **Approve URL**。

### W2. 审批（任选其一）

| 渠道 | 做法 |
|------|------|
| **PHA 事实卡（推荐）** | 打开完整卡 → **Loop 审批** 区块 → 同意 / 拒绝（锁屏通知会短提示「Loop 待审」） |
| 手机 / Mac Safari | 打开通知里的 `/ops/loop/approvals/<id>/view?token=…` → **Approve** |
| CLI | `python3 scripts/pha_loop_weekly_approve.py --id loopapr_… --approve --confirm YES` |
| PHA 收件箱 API | `GET /ops/loop/inbox?token=…` 列出 pending |

**Approve 实际执行（路径 B）**：合并提案别名到 `data/loop_local_aliases.json`（本机 only）。**不**改仓库 catalog。可选 `--full-veto` / `PHA_LOOP_APPROVE_FULL_VETO=1`；可选 `--draft-pr`（需 `PHA_LOOP_WEEKLY_DRAFT_PR=1`）。仓库合入仍需人工 Ready PR。

拒绝：页面 **Reject** 或 `--reject`。

### W3. launchd 每周一 09:30

示例：`scripts/macos/com.pha.loop-weekly.plist.example` → 拷到 `~/Library/LaunchAgents/` 后改路径与环境变量，再 `launchctl load …`。

PHA 服务需在听（审批页 / inbox）；Mac 通知不依赖 PHA；邮件与 webhook 不依赖 PHA。

### W4. 手机通知建议

- **飞书 / Slack / Discord webhook**：设 `LOOP_NOTIFY_WEBHOOK_URL`
- **Pushover / Bark / ntfy**：用 generic JSON webhook 或中间 Shortcuts
- **iOS 捷径**：收到 webhook 后「打开 URL」→ 审批页（同网 `http://Mac.local:8788/...`）

Selfcheck：`python3 scripts/pha_loop_weekly_selfcheck.py`
