# 启动变更日志

> **Language / 语言**：[English](startup-change-log.md) · 中文（本文）

> 目的：启动/可用性相关改动的强制共享上下文日志。  
> 规则：改动启动关键文件时，必须在同一 PR 更新本日志。

---

## 2026-09-06

- **事实卡路由（M1-P0；listen bind 不变）**：
  - `pha/main.py`：为 `GET /proactive/fact-card` 增加 `include_router`（`pha/fact_card_api.py`）。
  - 与 ingest 使用同一 `PHA_INGEST_TOKEN`。无新进程，无 host/port 变更。
  - 回滚：去掉 include_router 那一行。

---

## 2026-08-31

- **HealthKit ingest 路由（M0-P0；listen bind 不变）**：
  - `pha/main.py`：为 `POST /ingest/healthkit` 增加 `include_router`（实现在 `pha/healthkit_ingest.py`）。
  - 2026-09-04：ingest 400 响应增加 `got` 预览；`GET /ingest/healthkit` 返回 use_post 说明。zip 全量导入改为 preserve healthkit 行。无新进程、无 listen 变更。
  - `.env.example`：记录 `PHA_INGEST_TOKEN`、`PHA_INGEST_TZ`；注明 iPhone ingest 需要 `PHA_HOST=0.0.0.0`（默认仍是 `127.0.0.1`）。
  - 默认 listen host/port 不变。无新进程，无 launchd 变更。
  - 回滚：去掉 include_router 那一行；取消 ingest 环境变量。

---

## 2026-07-15

- **CI 增加「Minimal attach demo」步骤（审计计划 P1.5-1）**：
  - `.github/workflows/ci.yml`：在 packages 单元测试之后 — 以 `PYTHONPATH=packages/harness_core/src` 运行
    `examples/attach_minimal/run_demo.py`，
    然后断言 `failures.jsonl` 存在且含有 `"passed": false` 行。
  - 原因：P1.5-1 DoD — 非健康最小 attach demo 必须在 CI 中独立证明 PASS 与 FAIL-CLOSED 两条路径。
  - 无 `pha/main.py` 启动序列变更。

---

## 2026-07-14

- **CI 增加「Harness packages unit tests」步骤**：
  - `.github/workflows/ci.yml`：在 selfcheck 套件之前新增步骤 —
    `pip install pytest` + `python -m pytest packages/harness_core/tests packages/harness_loop/tests -q`。
  - 原因：审计计划 P0-2 — packages 必须用包内 pytest 套件自证；同时把此前未覆盖的 `harness_core` 测试带进 CI。
  - 无 `pha/main.py` 启动序列变更。

---

## 2026-07-13

- **CI 安装 Harness Loop (Alpha)**：
  - `.github/workflows/ci.yml`：在 `harness_core` 之后增加 `pip install -e packages/harness_loop`。
  - 原因：suite selfcheck（`pha_harness_loop_suite_selfcheck`）与 `harness-loop` CLI 需要该包在 PATH 上。
  - 无 `pha/main.py` 启动序列变更。

- **CI checkout 深度供 consensus 门禁使用**：
  - `.github/workflows/ci.yml`：`actions/checkout@v4` 现使用 `fetch-depth: 0`。
  - 原因：默认 depth=1 使 `check_startup_consensus.py` / `check_harness_consensus.py`
    崩溃（`merge-base` 与 `HEAD~1` 都不可用），把绿灯 selfcheck 变成红 CI。
  - 脚本加固：回退到 `GITHUB_BASE_SHA`，再不行则软空而不是 traceback。
  - 无 `pha/main.py` 启动序列变更。

---

## 2026-06-24

- **Stage 3F-γ / 3F-δ flags 接入**（无 `pha/main.py` 启动序列变更）:
  - `PHA_CLARIFY_INTENT_SCOPE=1` — holistic 单域/缺域 clarify（依赖 `PHA_GOAL_CLASSIFIER=1`）。
  - `PHA_SHADOW_ROUTING=1` — Shadow `goal_class` / `suggested_domains` telemetry（zero-adopt）。
  - 建议写入 `env-8788.sh` 与 E2E 脚本；默认仍为 `0`。
  - 自检: `pha_clarify_turns_selfcheck.py` H-δ8/δ9 · `pha_stage3f_delta_shadow_selfcheck.py`。

---

## 2026-06-17

- **Stage 3F-α 编码**（GoalClassifier + Harness Arbiter）:
  - Flag: `PHA_GOAL_CLASSIFIER=1`（默认 `0`）。
  - 模块: `pha/goal_classifier.py`, `pha/harness_arbiter.py`。
  - 自检: `scripts/pha_goal_arbiter_selfcheck.py`（H5–H8）。
  - 无 `pha/main.py` 启动序列变更。
- **Stage 3F 意图解析完整性 RFC 锁定**（文档-only）：
  - 新增 [`docs/stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md)。
  - 规划 flag（默认均为 `0`，编码阶段接入）：`PHA_GOAL_CLASSIFIER` · `PHA_GOAL_SESSION_ANCHOR` · `PHA_CLARIFY_INTENT_SCOPE`。
  - 与 Stage 3C-α～ε 并存；不修改 `pha/main.py` 启动序列。

---

## 2026-06-08

- 建立跨 agent consensus 护栏：
  - 新增 Cursor always-apply 规则：`.cursor/rules/startup-consensus.mdc`
  - 新增 PR 模板：`.github/PULL_REQUEST_TEMPLATE/startup-consensus.md`
  - 新增 CI 门禁脚本：`scripts/ci/check_startup_consensus.py`
  - 把 CI 接到：改动启动关键文件时强制更新启动 changelog
- 基线引用：
  - `docs/startup-availability-remediation-plan-2026-06-08.md`
  - `docs/startup-stability-2026-06-07.md`
- 已落地启动/可用性修复：
  - 启动瘦身：默认把重维护（`run_startup_data_audit`、`backfill_wearable_data_from_daily`）移出关键启动路径（`pha/main.py` 中异步后台线程）。
  - 去掉 `store.hydrate_from_sqlite` 中重复的启动 backfill 调用（只保留单一维护入口）。
  - 在 `pha/store.py` 中用 `effective_query_reference_date()` 替换硬编码 hydrate 参考日期。
  - 在 `scripts/pha_restart_accept.sh` 增加可选 keepalive watchdog（默认开；设 `PHA_ENABLE_KEEPALIVE=0` 关闭）。
  - 在 `.env.example` 增加启动模式/环境文档（`PHA_RUN_MODE`、`PHA_STARTUP_MAINTENANCE_SYNC`、`PHA_ENABLE_KEEPALIVE`）。
  - 用 Python supervisor `scripts/pha_keepalive.py` 替换不稳定的 shell watchdog，以获得持久 keepalive。
  - 删除已弃用的 macOS restart/stop 启动器，强制单一启动路径：
    - 删除 `scripts/macos/PHA-Restart.command`
    - 删除 `scripts/macos/PHA-Stop.command`
    - 删除 `macos-apps/PHA-Restart.app/*` 与 `macos-apps/PHA-Stop.app/*`
  - 启动 consensus 门禁已更新，去掉已删除启动器路径。

## 2026-06-09

- 修复 keepalive supervisor `scripts/pha_keepalive.py`：
  - **缺陷**：`_spawn_app` 把 `Path(py).parents[1]`（`.venv`）当作 cwd — 应用无法可靠重启。
  - **修复**：把显式项目 `ROOT` 作为第一个参数传入；以 `cwd=ROOT` spawn。
  - 增加 spawn/restart 时的 heartbeat 日志。
- 统一停止路径：新增 `scripts/pha_stop.sh`（替代已删除的 PHA-Stop.command）。
- `scripts/pha_restart_accept.sh`：
  - 启动前调用 `pha_stop.sh`（清理 port/pid/watchdog）。
  - 默认 `PHA_ENABLE_KEEPALIVE=1`；经 `scripts/pha_detach_spawn.py`（`start_new_session`）spawn，这样父 shell 退出不会杀掉 PHA。
  - 长驻前台替代：`scripts/macos/PHA-Serve.command`。
  - 验收后核验 app pid 仍存活。
- 删除过时的 `scripts/macos/create-pha-launcher-apps.sh`（Restart/Stop apps 已删；稳定后再重建）。
- 在 :8788 验证（2026-06-09）：`pha_restart_accept.sh` 验收通过 + 60s `/health` 探针（全程 app + watchdog 存活）。

## 2026-06-10

- **Stage 3C 多轮连贯性优化 RFC 正式评审通过**：
  - `docs/stage3c-multi-turn-episodic-focus-rfc.md` → **Approved · 架构师锁定版（2026-06-10）**。
  - 范围：**仅单会话内 episodic**；跨 Session 长期记忆明确放入远期 Backlog，本波次禁止混入。
  - 分期路线：3C-α `HealthTurnResolver` + 黄金自检 → 3C-β 全 profile episodic → 3C-γ catalog → 3C-δ clarify → 3C-ε Composer。
  - 开工分支：`stage3c-alpha-health-turn-resolver`；flag `PHA_HEALTH_TURN_RESOLVER=1`。
- **Stage 3C-α 已实现（HealthTurnResolver 骨架）**：
  - 新增：`pha/health_turn_resolver.py`、`pha/health_episodic_focus.py`、`pha/health_intent_catalog.py`、`pha/turn_scope_report.py`、`rules/health_intent_catalog.json`。
  - 自检：`scripts/pha_health_turn_resolver_selfcheck.py`（H1–H4 + H-A1–A3 + turnScope report）。
  - 尚未接到 `chat_service`（flag 门控集成在 3C-β）。
  - 验收：`bash scripts/run_selfchecks.sh` → **29/29 PASS**。
- **Stage 3C-β 已实现（episodic 写回 + chat harness turnScope）**：
  - 扩展 `chat_session_turn_focus` schema（profile/metric/lab_years/wearable window/last turn digest）。
  - 新增：`pha/health_session_focus_store.py`（`record_health_turn_focus`、`revive_health_session_focus`、`EPISODIC_BRIDGE`）。
  - `chat_service.py`：由 `PHA_EPISODIC_ALL_PROFILES=1` 门控；`turnScope` 经 `PHA_HEALTH_TURN_RESOLVER=1` 或 episodic flag。
  - `harness_report` schema **v1.2** + `turnScope` / `episodic` 节点；Tier0 `EPISODIC_BRIDGE` 槽。
  - 自检：`scripts/pha_health_episodic_selfcheck.py`。
  - 回滚：关掉 flags；schema 迁移列可选回退（旧行仍可读）。
  - 验收：`bash scripts/run_selfchecks.sh` → **30/30 PASS**。
- **Stage 3C-γ 已实现（catalog episodic profile 继承 + 补剂 R1 路由）**：
  - Flag：`PHA_HEALTH_INTENT_CATALOG=1`（完整效果需要 `PHA_HEALTH_TURN_RESOLVER=1` / episodic）。
  - 扩展 `rules/health_intent_catalog.json` v1.1（`weak_followup`、`supplement_families`）。
  - `pha/health_intent_catalog.py`：`resolve_inherited_focus_profile`、`should_prefer_attachment_qa_over_wearable`、`explicit_profile_shift`。
  - `wearable_harness.py`：catalog 打开时，补剂 R1 不再输给 `wearable_screenshot_review`。
  - `health_turn_resolver.py`：感知 catalog 的 `_topic_continues`（弱追问继承；阻断跨 profile revive）。
  - `chat_service.py`：把继承的 `focus_profile` 应用到 `turnScope`；focus 激活时走 attachment episodic bridge。
  - 自检：`scripts/pha_health_intent_catalog_selfcheck.py`（H-γ1–γ4）。
  - 回滚：关掉 `PHA_HEALTH_INTENT_CATALOG`；此前 3C-β 行为不变。
- **Stage 3C-δ 已实现（clarify SSE 短路 + 前端 chips）**：
  - Flag：`PHA_CLARIFY_TURNS=1`（`needs_clarification` 范围需要 `PHA_HEALTH_TURN_RESOLVER=1`）。
  - 新增：`pha/clarify_turns.py`（`build_clarify_sse_payload`、`resolve_scope_from_clarify_choice`、harness emit）。
  - `harness_plan.py`：`build_clarify_turn_plan()` — profile `clarify`，slots `MASTER_ANCHOR`+`TASK`，禁止 Patient State。
  - `chat_service.py`：resolver 后 `needs_clarification` 短路 LLM，yield `clarify` + `done`; chip 回传 `clarify_choice_id` 覆盖 episodic。
  - `main.py` `ChatRequest.clarify_choice_id`；`app.js` clarify chips UI。
  - 自检：`scripts/pha_clarify_turns_selfcheck.py`（H-δ1–δ6，对齐 RFC §6.4/§7/§8 H4）。
  - E2E：`scripts/pha_e2e_clarify_multiturn_report.py` + 浏览器 chips 真机验收（API + Console PASS 2026-06-10）。
  - 回滚：unset `PHA_CLARIFY_TURNS`；clarify 轮恢复为普通 LLM 路径（仍可能有 resolver 歧义标记但不短路）。
- **Stage 3C-ε 已实现（GroundedAnswerComposer SSE v2）**：
  - Flag：`PHA_GROUNDED_COMPOSER=1`（非 clarify 短路轮；不改变 Harness forbidden）。
  - 新增：`pha/grounded_answer_composer.py` — `meta` / `fact_card` / `follow_ups`（数字 ⊆ Manifest）。
  - `chat_service.py`：LLM 前 yield meta+fact_card；done 前 yield follow_ups；catalog 二轮刷新 fact_card。
  - `app.js` + `index.html`：数字卡 + 追问 chips UI。
  - 自检：`scripts/pha_grounded_composer_selfcheck.py`（H-ε1–ε4）。
  - 回滚：unset `PHA_GROUNDED_COMPOSER`。
- **Stage 3C P0 E2E 修复（wearable fact_card + clarify chip 路由）**：
  - P0-1：`chat_service.py` — `wearable_only` composer 轮单独 `build_numerics_manifest` 构建 `fact_card`（RFC §6.6 红线）。
  - P0-2：`harness_plan.py` — `build_turn_evidence_plan(..., turn_scope=...)` + `_plan_from_turn_scope`；clarify chip 后续强制 `lab_cross_year`（不再落 `lifestyle`）。
  - 自检：H-δ7（chip→plan）、H-ε5（wearable manifest fact_card）；E2E clarify R2 profile 断言。
  - 验收（2026-06-10）：API clarify PASS `lab_cross_year`；HRV API/浏览器 `fact_card` PASS；`run_selfchecks.sh` **33/33 PASS**。
  - 报告：`docs/stage3c-composer-e2e-report-2026-06-10.md`。
- **P2-4 已实现（结构化日志 + 稳定性路径上更窄的 except）**：
  - 新增：`pha/structured_log.py`（`format_context`、`log_warning`、`log_exception`，带 `event=` 前缀）。
  - 启动/导入/keepalive：`main._run_startup_maintenance`、`_run_import_background`、Ollama probes → `httpx.HTTPError`/`OSError`/`TimeoutError`；`data_importer.run_import_from_path`；`store` SQLite persist/wipe；`chat_service` 顶层 SSE catch；`pha_keepalive._read_pid` → `(OSError, ValueError)`。
  - 新增自检：`scripts/pha_structured_log_selfcheck.py`（manifest id `structured_log`）。
  - 回滚：回退 `structured_log.py` + 上述调用点；去掉 manifest 条目。
  - 验收：`create_app()` OK；`bash scripts/run_selfchecks.sh` → **28/28 PASS**。
- **P2-1 / P2-2 已实现（死代码 + 版本/端口对齐）**：
  - P2-1：删除 `main.py` delta/workout 后台助手（`_run_delta_sync_background`、`_run_workout_backfill_background`、`_enqueue_*`）；410 端点不变。
  - P2-2：默认 `PHA_PORT` **8788**，在 `pha/main.py`、`pha_process_lib.sh`、`docker-compose.yml`、`docker/entrypoint.sh`；README/INSTALL build `pha-v2.3.32-full-import-only`；E2E 脚本读 `PHA_PORT`。
  - P2-3：已在 P0-4 交付（日志在 `~/Library/Logs/pha`）。
  - 回滚：恢复删除的 `main.py` 助手；把端口默认改回 8787。
  - 验收（2026-06-10）：`create_app()` OK；`POST /data/sync-module/*` + `/data/backfill-workouts` → **410**；:8788 服务不变。
- **P1-4 已实现（selfcheck 统一入口）**：
  - 新增：`scripts/selfcheck_manifest.json`（27 项检查）、`scripts/pha_selfcheck_runner.py`（汇总表 + `--list`/`--only`/`--json`）。
  - `scripts/run_selfchecks.sh` 委托给 runner；`tests/test_selfcheck_suite.py` pytest 参数化；`pyproject.toml` pytest 配置。
  - 加入 manifest：`sqlite_connection`、`wearable_daily_aggregator`、`wearable_p15`、`harness_golden_run`、`wearable_golden_fixture`。
  - 修复：`pha_wearable_compare_table_selfcheck` 在数仓已填充时接受 May-30 workout 行的 `comparable_90d`。
  - 回滚：恢复旧的 `run_selfchecks.sh` 硬编码列表；去掉 manifest/runner/pytest 测试。
  - 验收（2026-06-10）：`bash scripts/run_selfchecks.sh` → **27/27 PASS**，带汇总表。
- **P1-3 已实现（SQLite 连接管理）**：
  - 新增：`pha/sqlite_connection.py` — 线程局部 `connect_pooled`、BatchWriters 专用 `open_connection`、`ensure_schema` 一次性守卫。
  - `WearableDataBatchWriter` / `SleepSegmentBatchWriter` / `WorkoutSessionBatchWriter` 不再每个实例调用 `init_schema()`；迁移每进程跑一次。
  - 回滚：回退 `sqlite_connection.py` + `sqlite_storage.py` + `workout_storage.py` 的连接改动。
  - 验收（2026-06-10）：`pha_sqlite_connection_selfcheck.py` PASS（schema×1，10-worker 并发读/写/batch，无 `database is locked`）；`pha_restart_accept.sh` PASS。
- **P1-2 已实现（wearable daily rollup 统一）**：
  - 新增：`pha/wearable_daily_aggregator.py` — 共享指标累加器、睡眠分段 rollup、`build_wearable_daily_summary`。
  - `data_importer._build_summaries`、`rebuild_wearable_daily_for_days`、`rebuild_daily_sleep_from_segments` 委托给 aggregator（行为保持）。
  - 新增自检：`scripts/pha_wearable_daily_aggregator_selfcheck.py`。
  - 回滚：回退 `wearable_daily_aggregator.py` + `data_importer.py` / `sqlite_storage.py` 中的三处调用。
  - 验收（2026-06-10）：aggregator selfcheck PASS；`pha_sleep_stage_rollup_selfcheck.py` PASS。
- **P1-1 已实现（chat_service.py 拆分）**：
  - 新模块：`pha/chat_message_stack.py`（229 行）、`pha/chat_attachments.py`（621 行）、`pha/chat_agent_runtime.py`（325 行）。
  - `pha/chat_service.py` 瘦身为 SSE 编排 + 向后兼容 re-exports（1487 行，原先 2589）。
  - 公开 API 不变：`main.py` / `harness_report.py` / `perception_worker.py` 仍从 `pha.chat_service` import。
  - 回滚：把上述四个文件回退到拆分前版本。
  - 验收（2026-06-10）：import smoke PASS；`pha_harness_report_v11_selfcheck.py` + `pha_stage3a_vision_selfcheck.py` PASS；`pha_restart_accept.sh` PASS；SSE `POST /api/chat`（`你好`，`qwen2.5:7b-instruct`）→ `event: done` PASS。
- **P0-4 / P0-5 已实现（launchd + 统一运维）**：
  - 新增：`scripts/pha_install_launchd.sh`（install|uninstall|status|verify）、`scripts/macos/pha-launchd-wrapper.template.sh`。
  - Wrapper + env 镜像在 `~/Library/Application Support/pha/`（TCC-safe；WorkingDirectory 不在 Documents）。
  - `pha_process_lib.sh`：launchd bootout/kickstart 助手；有 plist 时 `pha_restart_accept.sh` 使用 `kickstart -k`；`pha_stop.sh` 使用 bootout。
  - `.env.example` 默认端口 8788；文档统一在 `docs/macos-pha-launcher.md`。
  - 回滚：`bash scripts/pha_install_launchd.sh uninstall`，然后 `PHA_USE_LAUNCHD=0 bash scripts/pha_restart_accept.sh`。
  - 验收（2026-06-10）：TCC verify PASS；`kill -9` → 10s 内 `/health`；restart ×3 PASS；stop → 不再复活。
- **P0-2 已实现（rebuild 链重构）**：
  - `sync_wearable_data_from_daily`：只删除精确正午 daily-mirror 行 `(user_id, metric_type, timestamp)`；保留颗粒 `heart_rate` 等。
  - `rebuild_daily_sleep_from_segments`：单连接 batch；`upsert_wearable_daily_batch` + 安全 sync（不全表重载）。
  - `rebuild_wearable_daily_for_days`：经 `query_sleep_segments_in_range` batch 睡眠分段；共享 `_sleep_metrics_from_segment_rows`。
  - `rebuild_workout_daily_rollup`：单连接 batch；只 upsert 受影响的天。
  - `compute_sleep_hours_union`：扫线 O(n log n)（legacy 保留为 `_compute_sleep_hours_union_legacy` 供回归）。
  - 回滚：回退 `pha/sqlite_storage.py`、`pha/sleep_aggregator.py`、`pha/workout_storage.py`。
  - 验收（`export 3.zip`，2026-06-10）：全量导入约 107s；`wearable_data` **2,839,227**（HR 颗粒 **976,700**）；`wearable_daily` 3500；sweep vs legacy sleep union PASS。
- **P0-1 已实现（导入 GC/内存修复）**：
  - 去掉内存 `_seen_samples` 去重（`data_importer.py`）；去重依赖 `INSERT OR IGNORE` + unique index。
  - 从 `WearableDataBatchWriter`、`SleepSegmentBatchWriter`、`WorkoutSessionBatchWriter`、`upsert_wearable_daily_batch` 去掉周期性 `gc.collect()`。
  - 非白名单 `Record` 类型在 `_consume_record` 之前跳过；去掉 `_count_records_in_zip` 预扫描；进度使用 ZIP XML 字节预算。
  - 回滚：回退 `pha/data_importer.py`、`pha/sqlite_storage.py`、`pha/workout_storage.py`。
  - 验收（`export 3.zip`，2026-06-10）：90s 探针 t1/t2/t3 = 929,947 → 1,979,942 → 2,829,915 行（单调）；RSS 峰值 472 MB；全量导入墙钟约 4 min exit 0。rebuild 后 `wearable_data` 缩到 ~14k（已知 P0-2 `sync_index_from_daily` 问题 — 不是 P0-1）。
- **P0-0 已实现（phase B — suicide-restart 修复）**：
  - 新增 `scripts/pha_process_lib.sh`（被 source 的助手，不是用户入口）：kill 前预检、仅 LISTEN 的端口身份检查、restart mutex lock、身份核验后的 stop、失败恢复 trap。
  - `scripts/pha_restart_accept.sh`：pre-flight → lock → stop → spawn → health → acceptance；若 stop 成功但 health/acceptance 失败则 `trap` 恢复（exit 70）；恢复尽量复用存活 keepalive（不重复 supervisor）。
  - `scripts/pha_stop.sh`：委托给身份核验后的 stop；对陈旧 pidfiles 做孤儿 keepalive/app sweep。
  - 回滚：把上述三个脚本回退到 2026-06-10 之前版本；无 DB/schema 变更。
  - 故障注入演练（2026-06-10）：(1) 坏 PY 预检 → 旧 `/health` 不变 PASS；(2) `PHA_RESTART_WAIT_SECS=0` → 经现有 keepalive 恢复，rc=70 PASS；(3) 非 PHA LISTEN 拒绝 PASS；(4) 并发 restart → 一次 lock-reject PASS；(5) 10× restart → 全部验收 PASS（墙钟 8–12s 含 curls；stop→health 间隔约 3s）。
- 审计 + consensus（同日更早，无代码）：
  - 杀掉卡住的全量导入进程（pid 82831，17h，GC-thrash 死锁；SQLite 保留：2.83M samples，`wearable_daily`=0 待重导）。
  - 导入挂起根因：内存 `_seen_samples` 去重集 + batch writers 中周期性 `gc.collect()`（运行时栈采样证据）。
  - 识别「自杀重启」缺陷：`pha_restart_accept.sh:34` 在任何预检之前无条件跑 `pha_stop.sh`；启动失败留下无恢复的死窗口。端口清理 `lsof -ti | xargs kill -9` 不看身份。
  - 新的执行真相源：`docs/stability-remediation-plan-2026-06-10.md`（P0-0..P0-5 / P1 / P2 任务、验收标准、铁律 R1-R12、强制 agent prompt）。
  - 更新 `.cursor/rules/startup-consensus.mdc`：ACK token 升到 `stability-plan-v2026-06-10`；restart/stop 改动现在要求任务 ID 认领 + 故障注入演练证据。

## 2026-06-15 (skip_llm 架构扩展 · 真机回归)

- **Harness P1**（详见 `docs/harness-change-log.md` 2026-06-15）:
  - 纯数仓单指标：`try_warehouse_metric_focus_skip` → manifest 聚焦 skip_llm（~1–11s）。
  - 截图首轮：`build_compare_first_upload_answer` → CompareTable SSO + 运动建议模板，跳过 LLM 整段分析（OCR 仍 ~150–210s）。
  - 截图会话短追问：`build_catalog_followup_focus_answer` + `_EPISODIC_SHORT_METRIC_RE`。
- **E2E 验收**:
  - `scripts/pha_e2e_jun11_realdevice_multiturn.py` **PASS 7/7**（P2 并行 OCR：T1 **55.3s**，较 136s 降 ~60%）
  - `scripts/pha_e2e_browser_battery_20x.py` 精简 6 会话 **32/32 PASS**；完整 20× 复跑中
  - Report: `docs/stage3c-browser-e2e-report-2026-06-15.md`
- **P2 感知并行**：`PHA_PERCEPTION_PARALLEL=1`（默认）；`perceive_chat_attachment_paths`；`wearable_only` + `NUMERICS_MANIFEST` 槽位。
- **无启动路径变更**；`pha_restart_accept.sh` 行为不变。

## 2026-06-10 (wearable OCR / 多轮)

- **穿戴截图 OCR 修复**（`wearable_snapshot_v1.py`、`wearable_metric_candidates.py`）：
  - 新增共享 **`normalize_wearable_ocr_text()`**（真机 Tesseract：`nr→hr`、`ins→ms`、`sem→bpm`、紧凑时长规范化）。
  - `TIME ASLEEP` 宽松窗口匹配；不再误读 **Awake 1 hr 55 min**（真值 **6 hr 32 min**）。
  - Workouts 页优先解析 **「You worked out on N days in the last 4 weeks」**（真值 **20 天**）。
  - 支持 **During your last workout, heart rate was 68–116** 文案。
- **多轮纠正**（`chat_service.py`、`wearable_compare_table_v1.py`、`chat_storage.py`）：
  - 用户说「重新分析/核实/不对」时 **无需重传图**：从会话 OCR 重新 `remerge` 并写回 `parsed_json`。
  - 纠正轮 fallback 改为 **聚焦摘要**，避免每轮重复整段「根据您上传的 Apple Watch 截图…」。
- **单指标追问聚焦**（`wearable_compare_table_v1.py`、`grounded_answer_composer.py`、`chat_service.py`）：
  - `infer_single_metric_focus_ids()`：窄意图推断（不做 broad wearable 扩展）。
  - 截图会话 follow-up（如「HRV 怎么样」）**skip_llm** 返回 CompareTable 单行摘要；数仓指标（如「最近步数」）走 Manifest 聚焦。
  - 纠正轮同样 skip_llm；`skip_llm` 后跳过 compare 审计覆写。
- 验收：`scripts/pha_stage3c_wearable_selfcheck.py` PASS；`scripts/run_selfchecks.sh` **33/33 PASS**；`scripts/pha_e2e_jun11_realdevice_multiturn.py` 6 轮真图 API E2E PASS；`pha_restart_accept.sh` PASS。

## 2026-06-09 (ingest)

- **取消增量同步产品入口**（Apple Health 无官方增量 export；全量 zip 扫描+水位线伪增量性价比差）：
  - `ingest_modules` 置空；`POST /data/sync-module/*` 与 `POST /data/backfill-workouts` 返回 410。
  - Dashboard 移除增量模块下拉，仅保留「开始导入」全量路径。
  - CLI：`scripts/pha_full_import_from_zip.py`；删除 `pha_delta_sync_from_zip.py`。
  - 后端 `delta_sync_from_zip` 代码保留未接线，供日后如需内部实验。
