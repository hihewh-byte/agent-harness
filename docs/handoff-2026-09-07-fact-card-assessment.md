# 交接 · 事实卡评估层重做（M1-P7 / P8 / P9）

> 写给接替的 coding agent · 2026-09-07 16:50 · 维护者已批准方案，**尚无一行代码**  
> 首条回复必须输出：`CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> 碰 `hrv_rmssd_ms` / numerics / skip-LLM 时叠加：`CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> 真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.6**（§1.3 / §1.3a / FR-2.1 / FR-2.6 / FR-2.8 / FR-2.9 / FR-6 / §8）

---

## 0. 一段话背景

PHA 的 iPhone 主动事实卡已经能收到通知、打开完整卡、勾选指标、同步步数/消耗/静息心率/HRV/睡眠（M1-P0～P6）。但完整卡的**评估层几乎是空的**，只写「个人基线不足 7 天，不做分档」。维护者今天定了三件事：

1. **「基线不足」是错的**。Mac 库里 `default` 用户有睡眠 642 夜、HRV 1936 天、静息心率 2255 天、消耗 2286 天（2016 起，zip 导入止于 2026-06-09）。`pha/fact_card.py` 的 `BASELINE_DAYS = 90` 从 `as_of` 回看，正好把 zip 全排除，n 变成 0/1。主动 agent 是 PHA 的一部分，**不得与 Mac 账本割裂**：基线窗口要按可用量递进（90d → 365d → 全历史），并在卡上写清用了哪段。
2. 个人基线之外要有**通用参考层**，让用户第一天就读懂数字；格式用已实现的 `manifest-tier-v1` T1 披露块（`【参考标准】…（来源：…，请自行查证，非医疗建议）`），范围放注册表，不写死在 Python。HRV 绝对值**不给**人群范围。
3. 同意「**我的评估要求**」（用户自由文本）+「**按钮式解读**」（用户点了才调 LLM）。这不是主动路径（用户点 = 开口），**必须复用 chat harness**（TurnEvidencePlan + Numerics 审计），禁止裸 Ollama、禁止预生成、禁止进通知。M3「App 内问答」因此缩成 App 接同一端点，顺序不变。

顺带查实一个旧账：`wearable_data` 里 11650 条 `metric_type=hrv` 的 `sample_id` 全是 `HKQuantityTypeIdentifierHeartRateVariabilitySDNN|…|Wind’s Apple Watch`。也就是 `hrv_rmssd_ms` 这列**自始就是 Apple SDNN**，库里从来没有 RMSSD。今天真机入库的 `hrv_sdnn_ms=40.97` 和那 7 年历史是同一物理量，只是列名把基线挡住了。

---

## 1. 做事顺序（不要并行、不要跳）

| 序 | 卡 | 要点 | 完成标志 |
|----|----|------|----------|
| 1 | **M1-P7** 递进基线 + 参考层 | 纯规则、无 LLM、不碰 numerics | 完整卡对 `default` 立刻有「相对你近 12 个月 N 夜 → 低于/持平/高于」+ 参考句；selfcheck 绿 |
| 2 | **M1-P8** HRV 列语义纠正 | 碰数值路径，叠 harness ACK | 今日 SDNN 对上历史基线；skip-LLM「HRV」问答与 numerics selfcheck 绿；无 RMSSD 字样冒充 |
| 3 | **M1-P9** 评估要求 + 解读 | ① prefs 文本框（无 LLM）→ ② 异步端点 + 缓存 → ③ 走 `chat_service` → ④ HTML 独立区块 | 点按钮 <1s 返回「生成中」；刷新可见；停 Ollama 显示「模型不可用」；审计拒绝显示「未生成」 |

每张卡完成：跑 selfcheck → 官方重启 `bash scripts/pha_restart_accept.sh` → 真机/浏览器看完整卡 → 同 PR 写 [`pha-ios-proactive-change-log.md`](pha-ios-proactive-change-log.md) → 改 PRD §8 状态。**只本地 commit，不 push**（维护者说「请 commit」才 commit）。

---

## 2. M1-P7 具体做法

### 2.1 递进基线（`pha/fact_card.py`）

现状：`compose_fact_card` 用 `rolling_n_grain(BASELINE_DAYS, baseline_end)` 取一段 `baseline_rows`（排除 `as_of` 当日），`_metric_row` 对每个指标在这同一段里取样本，`< MIN_BASELINE_N(7)` 就 `band="unknown"`。

要改成：

- 基线候选窗口有序：`("90d", 90)`, `("365d", 365)`, `("all", None)`。**按指标**（不是按卡）取第一个 `len(samples) >= MIN_BASELINE_N` 的窗口；三个都不够才 `unknown`。
- `_metric_row` 输出多两个字段：`baseline_window`（`"90d"|"365d"|"all"|null`）与既有 `baseline_n`。`fact_card_numeric_atoms` 把 `baseline_n` 已经收进原子集了，窗口字符串不是数字，不用进。
- 文案：`_advice` / `sleep_verify_copy` / `compose_assessment_summary` 里写死的「近90日」全部改为从窗口生成：`90d → 近 90 日`，`365d → 近 12 个月`，`all → 全部历史（自 {首日年月}）`，并带 n：「相对你近 12 个月 268 夜」。**不要**再出现固定「近90日」字样。
- `unknown` 的文案改成进度：「个人历史 {n}/7 天，暂不分档」，不再叫「基线不足」。
- **同一定义才合并**：`sleep_hours` / `sleep_deep_hours` / `sleep_rem_hours` / `awake_duration_hours` 的 zip 口径与 HealthKit 并集口径一致，直接同序列；`sleep_core_hours` 与 `in_bed_hours` 历史全空（查过：core 只有 9/7 一天，in_bed 0 天）→ 自然落到 unknown，文案写「无历史」即可，不要特判。
- 卡级综合三档（FR-2.6）：`compose_assessment_summary` 里新增：取 `sleep_hours`、HRV（P8 前用 `hrv_sdnn_ms`/fallback 后的实际 field）、`resting_heart_rate_bpm` 三项的 `band`，都在 `{below, typical, above}` 才投票出「偏轻松 / 持平 / 偏好」；任一 missing/unknown → `"不综合"`。用户没勾其中某项也算缺项，不要偷用未选指标。
- 性能：`load_fact_card` 目前只查 90 天行；改为按需加载（先 90 天，不够再 365，再全部），或一次拉全历史 3504 行（SQLite 本地，可接受）。选简单可读的。

### 2.2 通用参考层（注册表 + `fact_card.py` + `fact_card_html.py`）

- `storage/registry/wearable_metric_registry.json` 每个适用指标的 `fact_card` 下加：
  ```json
  "reference_range": { "low": 7, "high": 9, "unit": "h", "source": "National Sleep Foundation 成人建议", "note": "常见建议范围" }
  ```
  v1 建议填：睡眠总时长 7–9 h；深睡占入睡 13–23%；REM 占入睡 20–25%；静息心率 60–100 bpm；步数 7000–10000。**HRV、清醒、在床、核心不填**。占比型的需要 `kind: "ratio_of", "of": "sleep_hours"`——如果实现太绕，v1 先只做绝对值四项（睡眠总时长、RHR、步数），占比留 TODO 写进 change-log，不要硬凑。
- `fact_card_prefs.FactCardMetricSpec` 增字段承接它；`_metric_row` 输出 `reference: {"low","high","unit","source","status": "within|below|above"}`；`fact_card_numeric_atoms` 把 low/high 纳入原子集（否则完整卡数字 ⊆ JSON 的自检会红）。
- 文案严格用 T1 块格式（`pha/numerics_manifest.py` 有正则 `【参考标准[^】]*】…（来源：…，请自行查证，非医疗建议）`，可直接拿来做自检）：  
  `【参考标准】成人睡眠常见建议 7–9 h，你今日 7.6 h 在范围内（来源：National Sleep Foundation，请自行查证，非医疗建议）`
- HTML：规则评估每项下方一行小字；不做颜色红绿（避免诊断感）。

### 2.3 自检（`scripts/pha_fact_card_selfcheck.py`）

新增用例：90d 空、365d 有 30 行 → `baseline_window="365d"` 且 band 非 unknown；三级皆空 → unknown 且文案含 `/7`；`reference.status` 三态；HRV 无 `reference`；文案不含「近90日」硬字符串；卡级综合缺项 → 「不综合」。

---

## 3. M1-P8 具体做法（叠 harness ACK）

- 先跑并保存基线：`python3 scripts/pha_numerics_manifest_selfcheck.py`、skip-LLM selfcheck、`python3 scripts/pha_fact_card_selfcheck.py`。
- 方案选一（写进 change-log 为什么）：
  - **A. 迁移**：`wearable_daily.hrv_rmssd_ms` 的历史值复制到 `hrv_sdnn_ms`（只在 `hrv_sdnn_ms IS NULL` 时），`wearable_data` 的 `metric_type='hrv'` 改 `hrv_sdnn`；注册表删 `hrv_rmssd_ms` 行或标 `deprecated`；`display_fallback_metric_id` / `include_when_selected` 取消。
  - **B. 改名**：列保留，注册表 `hrv_rmssd_ms` 的 label 改「HRV (SDNN，历史)」并 `merge_into: hrv_sdnn_ms`。
  - 推荐 A，一次性、以后不再解释。迁移脚本放 `scripts/`，幂等，先 `--dry-run` 打印计数。
- 迁移只做 `sample_id` 含 `HeartRateVariabilitySDNN` 的行；若将来有第三方真 RMSSD 样本，不受影响。
- 回归：问答「我的 HRV 怎么样」skip-LLM 路径的数字必须来自新列；事实卡 HRV 行 `baseline_n` 应 ≥ 200（近 365 天 274）。

---

## 4. M1-P9 具体做法

### 4.1 我的评估要求（无 LLM）

- `data/fact_card_prefs.json` 每用户多一个 `assessment_prompt: str`（可空）。`fact_card_prefs.py` 的 `prefs_payload` / `save_*` 扩展；`PUT /proactive/fact-card/prefs` body 多字段（`fact_card_api.FactCardPrefsBody`）。
- HTML 完整卡底部「我的评估要求」textarea + 保存；刷新回显。长度上限 2000 字，超出 400。
- 规则层**不读**这个字段。

### 4.2 解读端点（异步 + 缓存）

- `POST /proactive/fact-card/interpret?user_id=`（同 ingest token）：读当前卡 JSON + prefs；算 `key = sha256(user_id|as_of|assessment_prompt)`；缓存 `data/fact_card_interpret/{key}.json` 存在则 200 直接返回；否则写 `status=pending` 并起后台线程/任务生成，200 返回 `{status:"pending"}`。
- `GET /proactive/fact-card/interpret?user_id=`：返回 `{status: pending|done|failed, text, model, generated_at, error}`。
- **生成路径**：调 `pha.chat_service.stream_pha_chat_events(user_id=…, user_message=<固定指令 + 用户 assessment_prompt>, model=<配置的本机模型>, extra_system_context=<facts JSON + 基线摘要 + 参考层，标注「以下数字是唯一可引用数字」>, session_id=None)`，收集 SSE 直到 final。这样 TurnEvidencePlan / Compose / Numerics 审计自然生效。**不要**直接 import Ollama 客户端。
- 审计：final 事件若带 violation（`unauthorized_value` 类）→ `failed` + `error="audit_rejected"`；正文出现 facts ∪ 基线 ∪ 参考范围之外的精确数字也按拒绝（用 `fact_card_numeric_atoms` 做补充白名单校验）。允许 T1 块（`【参考标准…`）。
- Ollama 未起 / 超时 → `failed` + `error="model_unavailable"`。规则层照常，**绝不**用模板文字冒充 AI 解读。
- 缓存键含 `as_of`，第二天自动失效；用户改了要求文本也自动失效。

### 4.3 HTML

- 规则评估之后新增独立区块「AI 解读（实验）· 非医疗建议」：按钮「生成解读」→ fetch POST → 轮询 GET（每 5s，最多 4 分钟）→ 渲染 `text` + 「模型 {model} · {generated_at}」。pending 显示「生成中，可先关掉，稍后刷新」；failed 显示原因。
- 通知 body / `assessment` 字段一律不含解读；`GET /proactive/fact-card` JSON 里解读放顶层 `interpretation`（无缓存时为 `null`），不放进 `assessment`。

### 4.4 自检

- 假 chat 管线（monkeypatch `stream_pha_chat_events`）：返回含外来数字 → failed/audit_rejected；返回含 T1 块 → done；抛异常 → failed/model_unavailable。
- 不点按钮时 JSON `interpretation is None` 且无 LLM 调用。
- 同键二次 POST 不触发第二次生成。

---

## 5. 不要做的事

- 不要把「近90日」改成另一个写死的数字；窗口必须递进且写进 JSON。
- 不要为了让评估「有内容」发明数字、用昨日顶今日、或用未勾选指标凑综合。
- 不要在通知里放 LLM 文字；不要预生成；不要绕开 `chat_service` 直连 Ollama。
- 不要改 `packages/harness_core`；不要改公开 README 叙事；不要 push。
- 参考范围不进 Python 常量；进注册表。HRV 绝对值不给人群范围。
- P8 迁移前不要把 `hrv_rmssd_ms` 与 `hrv_sdnn_ms` 在事实卡里混成一个基线（现有 fallback 只是显示回退，不是合并）。

---

## 6. 现场事实速查（2026-09-07 16:45）

- PHA 在 `0.0.0.0:8788`，重启只用 `bash scripts/pha_restart_accept.sh`。
- 库：`data/pha_storage.db`；`default` 的 `wearable_daily` 3504 行（2016-09-26～2026-09-07）。
- 今日真机：9/7 入睡 7.60 / 清醒 3.45 / 核心 4.90 / 深 1.65 / REM 1.05 / 在床空；9/6 SDNN 40.968、RHR 60、消耗 703.6。
- 事实卡入口：`pha/fact_card.py`（`compose_fact_card`、`_metric_row`、`compose_assessment_summary`）、`pha/fact_card_prefs.py`、`pha/fact_card_api.py`（`/proactive/fact-card`、`/view`、`/prefs`）、`pha/fact_card_html.py`、`scripts/pha_fact_card_selfcheck.py`。
- 同步回执（T7）已落地：`GET /ingest/healthkit/last`、完整卡顶部「上次同步」。
- chat 管线入口：`pha.chat_service.stream_pha_chat_events` → `chat_turn_orchestrator.orchestrate_chat_turn_events`；`/api/chat` 是它的 SSE 壳。
- T1 披露正则：`pha/numerics_manifest.py`（`block_open_re`、`t1_disclosure_incomplete`）。
- 睡眠 M1-P6 仍 IN_PROGRESS（欠连续多夜验收 T9），与本交接并行，互不阻塞；不要改 `pha/healthkit_ingest.py` 的睡眠路径。
