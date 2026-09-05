# PHA iOS / 主动 Agent 变更日志

> Purpose: 本轨道（HealthKit ingest、事实卡、iOS 同步、主动通知）的强制共享上下文。  
> 共识真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md)

改动 ingest 契约、日表来源、事实卡模板、通知文案或 iOS 同步协议时，**须同 PR 追加条目**。

---

## 2026-09-05 (今日槽绑定日表 · Hero 不再用末日顶今天)

- **类别**：时间槽 → 日表绑定（对话与仪表盘同一条规则）。
- **根因**：Hero「今日步数」读近 7 日窗口的 `rows[-1]`，把「窗口里最后有数的一天」标成今天。这和问答曾经忽略时间槽是同一类错误，不是缺一个 `if day == today`。
- **改动**：`pha/wearable_daily_bind.py` — 点日 grain 只取该日历日，缺行则空；7 日均值只平均 grain 内的行。`dashboard_api.hero_stats` 与 Patient State「今日步数」走同一绑定。
- **回滚**：去掉 `wearable_daily_bind.py`，还原 `dashboard_api.py` / `patient_state.py`。

---

## 2026-09-04 (WIP 快照 · 已并入本 PR)

- **Git**：维护者决定 **全部完成后再一次本地 commit + push**。当前工作区相对 `origin/main` 未提交（含 M0 ingest、日表 UPSERT、时间槽、skip 空窗拒绝）。**不要**把本快照理解成 `packages/harness_core` 已改；core 仍是 Plan → Compose → Post-Audit 集合闸。
- **已在本机跑通（未 push）**
  - M0-P0/P1：`POST /ingest/healthkit`；真机今日步数入库 **11259**（`healthkit|default|steps|2026-09-04|healthkit`）。
  - M0-P2 日表：同日 UPSERT；zip 保留 `healthkit|` 行。
  - skip-LLM：问「今天步数」→ **今日步数 11259**，不再用 90 天均值。
  - 时间槽：`pha/wearable_time_grain.py`（点日 / 周 / 月 / `过去N天`）；空窗口 skip 说无记录，不把笔交给 LLM。
- **真机已知缺口（数据，不是代码）**
  - `wearable_daily` 无 2026-09-03：昨天无 HealthKit 行。修前 LLM 曾把 **2019-09-26 的 14808** 写成昨晚。
  - 近 7 日窗口里往往只有 9/4 一条，均值会等于今天（n=1），除非再同步那几天。
- **代码未完成（下一刀，完成后再 commit）**
  - ~~LLM 若绕过 skip：C 层仍几乎只审化验小数~~ **已补（本机未 commit）**：非默认时间粒度下，稿子里 ≥100 的整步数必须 ∈ 本窗口 T0；否则 `unauthorized_wearable_count`，warn 模式也替换为「无记录、不用其他日期顶」。`packages/harness_core` 仍未改。
  - 待你验收：昨天无行不再出现 14808；今天 11259 仍可引用。通过后一次 commit + push。
- **不要做**：M1 主动推送；改公开 README 叙事；未获「请 commit」前 `git commit` / `git push`。

---

## 2026-09-04 (时间锚点绑到证据窗口)

- **类别**：问答读数（Harness 时间槽，不是「今天」特例）。
- **根因**：1E-a 规定 `TIME_ANCHOR_TOKENS`（今天/昨天/本周/近7天…）不得进 catalog 别名，只能当 Tier-C 时间槽。Catalog 正确剥掉「今天」只留下「走了多少步」→ steps；**没有任何一层把该时间槽绑到 wearable 窗口**。skip-LLM / Numerics 默认近 90 天均值，所以「今天」在答案里消失。
- **改动**：`pha/wearable_time_grain.py` 用同一组时间锚点解析窗口（点日 / 周 / 月 / 滚动天数）；`default_wearable_window` 与 HealthTurnResolver 共用；skip-LLM 在非默认 grain 时重建 manifest，禁止复用 90 天均值。泛问「步数呢」、截图「和上周比」仍走默认 90 天。
- **滚动天数**：`过去N天` / `近N天` / `last N days` 是同一类 duration，不是再加一条「过去7天」特例。空窗口 skip-LLM 直接说无记录，禁止 LLM 拿别的日期填数。
- **回滚**：去掉 `wearable_time_grain.py`，还原 `date_range_parser` / `health_turn_resolver` / `grounded_answer_composer`。

---

## 2026-09-04 (M0-P2 日表对齐 + skip-LLM 可读)

- **类别**：ingest 日键、zip 冲突、问答读数。
- **步数**：按日历日一条 `sample_id`；同日重复同步 UPSERT，不把多次 POST 加总。写入前丢掉同日旧的 timestamp 键 healthkit 行。
- **zip 全量导入**：`clear_wearable_storage(..., preserve_healthkit=True)`，导入后再 `rebuild_wearable_daily_for_days` 含 healthkit 日（max-by-source）。
- **skip-LLM**：selfcheck「最近步数」须出现 healthkit 日表数字。
- **捷径**：Find → Get Details Value → Get Numbers → Statistics Sum；JSON **只带合计数字**。steps 若误带「合计+分样本换行」，服务端先把换行收成合法 JSON，再用领先合计（避免加两遍）。
- **回滚**：还原 `healthkit_ingest.py` / `sqlite_storage.py` / `data_importer.py` / `store.py` 与捷径生成脚本。

---

## 2026-09-04 (M0-P1 ingest value coerce + shortcut number)

- **类别**：ingest 解析 + 本机捷径制品。
- **原因**：iPhone `POST /ingest/healthkit` 已通（非 401/422），但 `value` 仍是健康 Quantity / 空对象替换符，400 `unreadable_value`，库无 `healthkit|default|`。
- **服务端**：`_finite_number` 收 `16 count`、Magnitude 字典；400 响应带 `got`；日志打 body 预览。空值仍 fail-closed，不编造步数。`GET /ingest/healthkit` 返回说明 JSON（浏览器打开不再是生硬 405）。
- **捷径**：今日步数 **Statistics Sum** 后只 POST 一个数字（避免 iOS「共享 329 条健康数据」）。
- **回滚**：还原 `pha/healthkit_ingest.py` 与 `scripts/macos/build_pha_ingest_shortcuts.py`，再 `bash scripts/pha_restart_accept.sh`。

---

## 2026-09-02 (M0-P1 local bind + shortcut files)

- **类别**：本机运行配置（`.env` gitignored）+ 捷径制品（`data/local_shortcuts/` gitignored）。
- **PHA_HOST**：本机改为 `0.0.0.0`，经 `pha_restart_accept.sh` / launchd kickstart；仓库默认仍是 `127.0.0.1`。
- **验收**：局域网 `http://192.168.77.21:8788/ingest/healthkit` fixture 200；无 token 401。
- **捷径**：`scripts/macos/build_pha_ingest_shortcuts.py` 默认写入 `$(scutil --get LocalHostName).local`，避免 DHCP 换 IP 后旧地址 timeout。Health 捷径 **只** `Find Health Samples` 类型 `Steps`。value 在 JSON 里加引号，服务端把 `"16 count"` 收成数字。
- **回滚**：`.env` 改回 `PHA_HOST=127.0.0.1` 再 `bash scripts/pha_restart_accept.sh`。

---

## 2026-08-31 (M0-P0 ingest)

- **类别**：生产代码（HealthKit JSON → SQLite）。
- **路由**：`POST /ingest/healthkit`（`pha/healthkit_ingest.py`）。
- **鉴权**：`PHA_INGEST_TOKEN`；Header `X-PHA-Ingest-Token` 或 body `token`；未配置 503，错 token 401。
- **时区**：`PHA_INGEST_TZ` 默认 `Asia/Shanghai`；timestamp 转成 naive 本地时间，日表用 `substr(timestamp,1,10)`。
- **白名单**：`hrv` / `rhr` / `steps` / `sleep_hours` / `active_energy`（`sleep_hours` 落库为 `metric_type=sleep`）。未知指标丢样本不编造；时间戳/数值无法解析则整批 400、不写入。
- **幂等**：`sample_id = healthkit|{user}|{metric}|{local_iso}|healthkit`（v1 无 source 列，来源编在 sample_id）。
- **日表**：写入后 `rebuild_wearable_daily_for_days`。rebuild 跳过 noon daily-mirror 行，避免同日多次 ingest 把 `active_energy` 加两遍。
- **自检**：`scripts/pha_healthkit_ingest_selfcheck.py`（临时库，不碰 `data/pha_storage.db`）。
- **回滚**：去掉 `main.py` 的 ingest router；删除 `pha/healthkit_ingest.py`。

---

## 2026-08-31 (PRD v1.0 ratified)

- **类别**：产品共识（尚无生产代码）。
- **真源**：`docs/prd-pha-ios-proactive-agent-v1.md`。
- **第一刀**：HealthKit → Mac `wearable_daily`（M0-P0/P1）。
- **铁律**：主动路径无 LLM 填数；非医嘱；数据不出用户设备圈。
