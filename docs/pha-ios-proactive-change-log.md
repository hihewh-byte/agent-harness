## 2026-09-08 22:50 (M1-P9.5：解读专用 soul，消三步看诊焦点跑偏)

- **类别**：P1（解读大纲）。英文解读强制 `Trend review / Related markers / Recommendations`，把卡上 SpO2/呼吸率当「相关指标」念出。
- **根因**：`fact_card_interpret` 走完整 `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` 三步看诊法第二步。
- **改动**：`PHA_FACT_CARD_SOUL_MINIMAL`；`select_soul_base`；缓存键哈希含 soul；`harness_report` dry-run 路径未并轨（解读不经该入口，记待办）。
- **证据**：selfcheck PASS。运行验收（build `pha-v2.3.33-fact-card-soul-p95`）中英各 3 轮：

| id | 审计 | 三步标题 | SpO2/呼吸率 | RHR | HRV | VO2 |
|---|---|---|---|---|---|---|
| enP1–3 | 3/3 过 | 0/3 | 0/3 | 3/3 | 3/3 | 2/3 |
| zhP1–3 | 3/3 过 | 0/3 | 0/3 | 3/3 | 3/3 | 0/3 |

  VO2 漏提为已知模型偶发，非本轮门槛。prefs 已恢复 zh-CN。
- **回滚**：删 `select_soul_base` 中 fact_card 分支；缓存键自动失效。

## 2026-09-08 22:20 (M1-P9.4.1：英文无年日期遮罩)

- **类别**：P1（audit）。`September 3` 无年时未当日期，日数字 `3` 被拒。
- **改动**：fact_card 审计用 `_extract_fact_card_dates` 把无年 EN/CN 月日对齐卡上 `allowed_dates`；遮罩生成 `September 3` / `9月3日` 等表面形。策略版本 `v1.1`。
- **证据**：`FC-en-yearless-ok/bad` selfcheck PASS。
- **回滚**：还原 `_extract_fact_card_dates` 调用与 `FACT_CARD_AUDIT_POLICY_REV`。

## 2026-09-08 20:40 (M1-P9.4 落地：fact_card 数字分级审计)

- **类别**：P1（audit）/ 事实卡解读。
- **改动**：`numerics_manifest` 新增 `fact_card` 策略（子句级 S/E/T1）；卡侧 `_audit_interpretation_text` 委托同一函数；`rejected_text`；TASK 分条 + `{T1_TEMPLATE}` 按 locale；Tier0 `slot_floor` + min 保留 values；失败文案归并。
- **证据**：`pha_numerics_manifest_selfcheck.py` / `pha_fact_card_selfcheck.py` / `pha_chat_turn_fsm_selfcheck.py` PASS；§2.4 十八例本机复现对齐。
- **回滚**：还原 `numerics_manifest` fact_card 分支与 `fact_card_interpret` 委托；缓存键随 TASK/policy hash 自动失效。

## 2026-09-08 20:11 (M1-P9.4 立卡：卡外数字分级放宽 + 单一审计 · 仅文档)

- **类别**：产品共识 / 审计契约。**无代码改动。**
- **发现**：真机解读连续被拒 `2、95、2、3、95`。`2` 来自 `SpO2`/`VO2max` 标签（卡侧 `\d+` 无边界）；`96.0` 因上下文块给原值、白名单只有 `96`；`95`/`70–80`/`2–3` 是科普整数，7b 写不出 T1 模板；卡侧 T1 正则只认中文。harness 审计对同文本 `passed=True`。
- **决定**：PRD v1.10 FR-6.10 由「只进 T1」改为语境三级（S 必对账 / E 放行记 telemetry / T1 中英同权）；FR-6.3 审计只有一道。尺度与 18 条用例见交接 v3 §2。
- **待执行**：[`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) §9 执行顺序；8462695 未推送，先 amend。

## 2026-09-08 (M1-P9.3：解读大纲改在 TASK，撤掉指标解析器)

- **类别**：事实卡解读 / 反硬编码。上一刀用评估要求别名匹配收窄 manifest，并拒焦点外数字，是针对「只看 RHR/HRV/血氧」的路由，违反宪法第四条与 FR-6.8（整张卡是证据源）。
- **证据**：交接 §4.3：TASK 写在 profile，评估要求是大纲不是数值来源。selfcheck：TASK 含 outline 句、不含具体指标名、不含 `FACT_CARD_CONTEXT.focus`；上下文仍保留卡上全部行。
- **改动**：`fact_card_interpret` TASK：USER_ASSESSMENT_PROMPT 为大纲；点名则只谈这些行；`value` 非空不得说缺失。槽序仍是 TASK → 评估要求 → 卡 → manifest（注意力顺序，不是指标白名单）。撤掉 alias/deny list/focus 过滤与 `focus_missing_but_present`。缓存键 `task_outline_v2`。
- **回滚**：还原 `harness_plan._FACT_CARD_INTERPRET_TASK`。
- **维护者下一步**：刷新完整卡后重新点「生成解读」。仍欠停 Ollama 与跨日真看。

## 2026-09-08 (i18n：仪表盘黄金指标 + 主动卡 git 默认英文)

- **类别**：Dashboard / 事实卡展示。维护者：英文界面下黄金指标条仍是中文；主动 agent 需要中英两套，仓库默认英文。
- **证据**：`GOLDEN_WEARABLE` 曾写死「每日步数」等；`label_zh` 未随顶栏语言切换。iPhone Safari 16:21 解读已出（与 Mac 同文）。
- **改动**：黄金指标 / 分组 git 默认英文 + `label_zh`/`label_en`；`GET /available_metrics?locale=` 把 `label`/`unit`/`hint` 收成当前语言；切语言后先按内存双语字段重绘再重拉目录。静态资源 cache bust `i18n1`。事实卡 `DEFAULT_LOCALE=en-US`；`fact_card_copy.py` 中英两套 chrome/规则/通知文案。现有 `data/fact_card_prefs.json` 仍是 zh-CN，真机中文不变。T1 披露块外壳仍是 `【参考标准】…（来源：…请自行查证）`（审计正则依赖）。化验项名仍来自 SQLite 原文，不在此轮英化。
- **回滚**：还原 `metric_catalog_ui.py` / `metrics_api.py` / `app.js` / `fact_card_copy.py` / `DEFAULT_LOCALE`。
- **维护者下一步**：仪表盘切 English 后黄金条应为 Daily steps / Resting HR；切回中文应为「每日步数」。事实卡底部改 English 会换解读缓存。仍欠停 Ollama 与跨日缓存真看。

## 2026-09-08 (M1-P9.3：卡上参考范围可进解读正文)

- **类别**：事实卡解读审计。Mac Safari 点「生成解读」被卡侧第二道审计以 `unauthorized_value:60/100` 整段丢弃。
- **证据**：harness `numerics_audit.passed=true` 且 cited 60/100（manifest `domain=reference`）；卡面 T1 已写「60–100 bpm」。卡侧曾把参考上下限从正文白名单抠掉，与 FR-6.3「⊆ facts ∪ 基线 ∪ 参考范围」和 harness 不一致。失败文案「卡上没有的数字」对这两数不成立。selfcheck PASS；`pha_restart_accept.sh` PASS（pid 863）。Mac Safari 第三轮「重试」于 16:21 生成成功（前两轮分别因 60/100 卡侧过严、模型编了 1.2 被 harness 拒）。
- **改动**：`_body_numeric_atoms` 保留卡上 `reference.low/high`。selfcheck：正文「60–100」过；卡外「80」仍拒；T1 包 120–140 仍拒。
- **回滚**：还原 `_body_numeric_atoms` 对参考 token 的剔除。
- **维护者下一步**：仍欠 iPhone Safari 全流程、停 Ollama 真测（确认时间窗）。跨日缓存需过 0 点或改 `calendar_day` 真看。

## 2026-09-08 (M1-P9.3：跨日缓存 + 英文日期审计；真机门禁未完)

- **类别**：事实卡解读边界。P9.2 后继续。
- **证据**：`pha_fact_card_selfcheck.py` PASS：`Sep 7, 2026` / `9月7日` 视为 as_of；`Jun 10, 2026` 拒；`calendar_day` 进缓存键；失败态 HTML「本机模型未响应」+「重试」。16:03 真机数量捷径已带 `pack_version=2026.09.08.priority-1e`。
- **改动**：解读缓存键加入 `calendar_day`（跨日即使 as_of 未变也失效）。`_extract_normalized_dates` 收英文月名带年；卡侧再收无年「9月7日 / Sep 7」。§6 决定 5：通知 body 日期**仍用 ISO**（捷径与 selfcheck 依赖），不本地化。
- **回滚**：还原 `fact_card_interpret.py` 缓存键与日期抽取；还原 `numerics_manifest.py` 的 `_DATE_EN_RE`。
- **维护者下一步**：同一 Wi-Fi 用 iPhone Safari 打开完整卡走一遍解读；若要验收「模型不可用」，确认时间窗后停 Ollama 再点「生成解读」（不停 PHA）。en-US 可在完整卡底部改语言后刷新。

---

## 2026-09-08 (Find 总表 + 腕温跳过捷径 + M1-P9.2 展示层)

- **类别**：捷径 Find 真源 / 事实卡展示。维护者再跑一次后腕温仍无权限开关；事实卡已能同步。
- **证据**：9/8 日表有步数 6219、消耗 144.6、RHR 65、HRV 32.9、血氧 96.0、呼吸率 13.0、入睡 6.2h；VO2max 51.48 @ 9/3；`wrist_temp_c` 仍空。Find 标签错一次权限开关就不会出现。
- **改动**：新增 `storage/registry/shortcut_health_find_catalog.json`，只有 `device_verified` 写入捷径。腕温 `shortcut_skip_reason=shortcuts_find_unverified`。数量捷径 7 个 Find。`shortcut_pack_version` → `2026.09.08.priority-1e`。VO2 `latest` 不再算「前一日值」。P9.2：prefs `locale`、HTML 日期按语言、解读剥 Markdown、band 标签改数值方向（高于/持平/低于）、缓存键含 locale。
- **回滚**：还原 Find 总表 / 注册表 pack / `healthkit_sync_plan` / `fact_card_html` / `fact_card_locale.py`。
- **维护者下一步**：桌面 `PHA同步健康.shortcut` **替换一次**（腕温 Find 已去掉）。同一 Wi-Fi 打开完整卡核对中文日期。P9.3 再做 iPhone Safari / 停 Ollama / en-US 真机。

---

## 2026-09-08 (腕温 Find 标签：Wrist Temperature)

- **类别**：捷径 Find。15:16 跑完 7/8 入库；腕温无 POST。真机报无权限且面板无开关。
- **证据**：`Apple Sleeping Wrist Temperature` 是 SDK 名；Find 选择器与权限面板用 `Wrist Temperature`（与 Blood Oxygen / Oxygen Saturation 同坑）。
- **改动**：注册表腕温 Find 改为 `Wrist Temperature`。`shortcut_pack_version` → `2026.09.08.priority-1d`。
- **维护者下一步**：再替换一次「PHA 同步健康」；腕温 Find 上点 Allow Access。

---

## 2026-09-08 (Find 标签：血氧是 Oxygen Saturation)

- **类别**：捷径 Find 选择器标签。真机：权限面板无 Blood Oxygen；Find Type=`Blood Oxygen` 报 No Samples Found；VO2 报无 Cardio Fitness 权限。
- **证据**：iOS 26.2 ActionKit 选择器真名是 `Oxygen Saturation` / `Apple Sleeping Wrist Temperature` / `VO2 Max`。健康 App 英文 UI「Blood Oxygen」不能当 Find 标签（与 Active Calories 同坑）。账本血氧最后一日 2026-06-09，近 2 天本就空。
- **改动**：注册表 Find 改为上述真名；VO2 `freshness_days` 90→180（最后一次 6/3 已超 90 天）。`shortcut_pack_version` → `2026.09.08.priority-1c`。
- **维护者下一步**：替换「PHA 同步健康」；血氧/腕温/VO2 的 Find 上点 **Allow Access**（开关会在授权后才出现在面板里）。

---

## 2026-09-08 (捷径 Get Details Unit 把整表单位拼在一起)

- **类别**：ingest 单位 / 捷径包。真机：事实卡顶栏 `unknown_unit:count count count…`；「PHA 同步健康」在呼吸率 Find 处 *There's a problem*。
- **证据**：14:52 POST 步数 5985 / 消耗 130.339 被拒，`unit` 为每条样本单位用换行拼成；呼吸率 last-2-days 无 Limit，Get Details 拖垮捷径。自检 PASS。
- **改动**：JSON `unit` 改为注册表字面量，不再 Get Details Unit；一夜指标 Find Limit 150（与睡眠同帽）+ First Item 取 Start Date；服务端对拼接单位只取第一个词。`shortcut_pack_version` → `2026.09.08.priority-1b`。
- **回滚**：还原 `build_pha_ingest_shortcuts.py` / `healthkit_units.py` / 注册表 pack 版本。
- **维护者下一步**：桌面 `PHA同步健康.shortcut` **再替换一次**。事实卡捷径不必为这次再换。5G 下 `.local` 会超时，须同一 Wi-Fi。

---

## 2026-09-08 (M1-P12：优先级包一期 + zip 为最终真值)

- **类别**：注册表 / ingest 单位 / 捷径包 / zip 覆盖增量 / 事实卡覆盖率。
- **证据**：`pha_wearable_registry_selfcheck.py`、`pha_fact_card_selfcheck.py`、`pha_healthkit_ingest_selfcheck.py` PASS。
- **改动**：血氧/呼吸率/VO2max/腕温进入 eligible 并接线捷径；POST 带 `unit` 与 `pack_version`；未知单位/越界 400；VO2max `temporal.kind=latest` 不计覆盖率；zip 导入删除 `xml_max` 当日及之前的 healthkit 行并写对账 JSON。PRD v1.8。不启动 Pulso。
- **回滚**：还原注册表 `shortcut_pack_version`、ingest 白名单、捷径生成器、`zip_healthkit_overlay.py`。
- **维护者下一步**：真机核对 Find 标签（血氧 / 呼吸率 / VO2 Max / 腕温）后替换「PHA 同步健康」；每季度回灌 export.zip。

---

## 2026-09-08 (捷径 If 空 Condition：WFInput 必须 Type=Variable)

- **类别**：捷径生成器。
- **证据**：真机「PHA 同步健康」打开即报 *Please choose a value for each parameter*，If 的 Condition 空白。plist 里 `WFInput` 是裸 `WFTextTokenAttachment`，编辑器当空参数。`python3 scripts/pha_healthkit_ingest_selfcheck.py` PASS（If `WFCondition=100` has any value + `Type=Variable`）。
- **改动**：空集跳过改为「Find 结果 has any value」；`WFInput` 包一层 `Type=Variable`。重签 `pha-sync-health.shortcut`。
- **回滚**：还原 `_if_has_any` / `_variable_input`。
- **维护者下一步**：桌面 `PHA同步健康.shortcut` 再传到 iPhone **替换一次**。

---

## 2026-09-08 (M1-P9.1：解读专属 profile + 日期归一化审计)

- **类别**：事实卡按钮式解读叠 harness（非主动路径）。
- **证据**：`python3 scripts/pha_fact_card_selfcheck.py` PASS（365d 卡拒「近 90 天」；拒卡外日期；中文 as_of 通过；T1 参考范围通过；harness `future_date` 拒；块外 120–140 拒 / T1 ACSM 过；块外「参考范围 60–100」拒；改勾选 cache key 变）；`pha_chat_turn_fsm_selfcheck.py` / `pha_numerics_manifest_selfcheck.py` PASS。
- **改动**：`fact_card_interpret` profile；user_message 固定短句，评估要求进 `USER_ASSESSMENT_PROMPT` 槽；撤掉 9/7 晚「harness 已过则只拦 ≥100」；失败态把被拒 token 写给用户。PRD FR-6.8/6.9/6.10、§4.2、§8 P9.1 DONE。
- **回滚**：还原 `fact_card_interpret.py` 审计与 chat `profile_override` 接线；registry `--write` 去掉该 profile。

---

## 2026-09-08 (M1-P10 + M1-P11：时效语义 + 勾选即所见 + 捷径全集)

- **类别**：注册表 / 事实卡 prefs / 捷径生成器 / ingest 数量路径。
- **证据**：`python3 scripts/pha_fact_card_selfcheck.py` PASS（卡 = 勾选、只勾深睡不带出在床、sync plan 与 prefs 无关、RHR D-1 有 band、D-3 空、累计型 08:00 进行中不分档、通知含「前一日」）；`python3 scripts/pha_healthkit_ingest_selfcheck.py` PASS（`empty_sample`、数量捷径 4 个 Find、RHR last-2-days + Limit 1 + Start Date、count=0 If 跳过）。
- **改动**：删 `reveal_when_selected`；`shortcut_sync_specs` 改为注册表全集；`temporal.kind` 驱动取值；数量捷径空集不 POST；ingest 空值回执 `empty_sample`。PRD §4.1 / FR-2.10 / §8 P10 P11 DONE。
- **回滚**：还原注册表、`fact_card.py` / `fact_card_prefs.py` / `healthkit_sync_plan.py` / 捷径生成器 / ingest 数量路径；重新生成捷径。
- **维护者下一步**：在 Mac 导出并在 iPhone **替换一次**「PHA 同步健康」。之后改勾选不再重装。

---

## 2026-09-08 (PRD v1.7：捷径全集同步 + 勾选即所见 + 立 P9.1 / P10 / P11 / P9.2 / P9.3；只改文档)

- **类别**：PRD 共识变更（FR-1.5 / FR-2.7）+ 交接文档。**无代码。**
- **证据**：9/8 08:12 真机截图勾 5 项、卡列 9 项（注册表 `reveal_when_selected` 隐式展开）；页面要求改勾选后重装捷径；08:00 静息心率空值 POST 400、消耗零头判 below、解读被 harness 以 `unauthorized_wearable_count:100` 拒。可能性分析：Mac 不能触达 HealthKit、iOS「查找健康样本」类型不可变量化，故「刷新即有新数据」与「按服务端名单动态 Find」不可能；可行 A（捷径全集 + 卡按勾选过滤）/ B（全集 Find + 运行时 If 门控）。**维护者 08:27 拍板 A。**
- **改动**：PRD v1.7：FR-1.5 改「捷径按注册表 `eligible ∧ shortcut_health_type` 全集同步，与勾选无关；累计型一数、每日一次型带日期、空集跳过」；FR-2.7 补「卡 = 勾选、禁止隐式展开、分母 = 勾选数」；§8 登记 M1-P9.1 / P10 / P11 / P9.2 / P9.3；§11 三条。`handoff-2026-09-08-fact-card-interpret-v2.md` 定稿（含 §5c.5 执行清单）；`pha-fact-card.md` 同步段重写；路线图 1e。
- **回滚**：还原上述文档至 v1.6。

---

## 2026-09-07 (M1-P9 浏览器验收 + 审计收紧)

- **类别**：完整卡真机/浏览器验收。
- **证据**：浏览器打开 `/proactive/fact-card/view`：评估要求保存回显；点「生成解读」先「生成中」；失败态显示「未生成（审计未通过）」可重试；最终 `status=done`，页面渲染模型名与时间。根因：补充原子审计把 harness T0「近90日 / 区间锚点」当成外来数；且 `failed` 缓存曾挡住重试。
- **改动**：日期片段白名单；`failed` 可再 POST；harness `numerics_audit.passed` 时仅拦截 ≥100 的外来大数；解读指令强调勿编造日期。selfcheck PASS；官方重启 PASS。
- **回滚**：还原 `fact_card_interpret.py` 审计逻辑。

---

## 2026-09-07 (M1-P9 我的评估要求 + 按钮式解读)

- **类别**：完整卡用户触发解读（非主动路径；叠 harness）。
- **证据**：`python3 scripts/pha_fact_card_selfcheck.py` PASS（prefs 回显 / 超长 400；假 stream：外来数字 `audit_rejected`、T1 块 `done`、异常 `model_unavailable`；未点按钮 `interpretation is None`；同键二次 POST `started=False` 不二调）。通知与 `assessment` 不含解读。
- **改动**：`fact_card_prefs.assessment_prompt`（≤2000）；`pha/fact_card_interpret.py` 缓存 `data/fact_card_interpret/{sha256}.json`，经 `stream_pha_chat_events` 生成；`POST/GET /proactive/fact-card/interpret`；`load_fact_card` 顶层 `interpretation`；HTML「我的评估要求」+「AI 解读（实验）」轮询。禁止裸 Ollama、禁止预生成、禁止进通知。
- **回滚**：去掉 interpret 模块与路由；还原 prefs/HTML/load_fact_card/selfcheck；删缓存目录。

---

## 2026-09-07 (M1-P8 HRV 列语义纠正：RMSSD 列 → SDNN)

- **类别**：账本语义 / 穿戴读取路径（叠 harness ACK）。
- **证据**：迁移前 `wearable_data` 11652 条 `metric_type=hrv`，其中 9714 条 `sample_id` 含 `HeartRateVariabilitySDNN`，其余多为 `default|hrv|` 日镜；库中无真 RMSSD。`python3 scripts/pha_migrate_hrv_rmssd_to_sdnn.py`：日表复制 1937 行 → `hrv_sdnn_ms`（现 1938），样本改标 11651→`hrv_sdnn`。9/6 卡：`hrv_sdnn_ms=40.97`，`baseline_window=365d` n=275 band=above。自检：fact_card / healthkit_ingest / compare_table / chat_turn_fsm / numerics / aggregator PASS。
- **改动**：方案 A。迁移脚本幂等；聚合器把遗留 `hrv` 样本写入 SDNN 桶；zip 导入与 ingest 别名 `hrv`→`hrv_sdnn`；注册表主指标改 `hrv_sdnn_ms`（label HRV），`hrv_rmssd_ms` 标 deprecated/非 eligible；prefs 自动 remap；`health_data`/patient_state/compare/OCR 快照兼容旧 id。深睡/REM 占比参考仍 TODO。
- **回滚**：还原代码与注册表；日表可用备份或从 `wearable_data` 重算（迁移不删 `hrv_rmssd_ms` 历史值）。

---

## 2026-09-07 (M1-P7 递进个人基线 + 通用参考层)

- **类别**：事实卡规则评估（无 LLM）。
- **证据**：`python3 scripts/pha_fact_card_selfcheck.py` PASS（含 90d 空→365d、无历史 `/7`、T1 参考三态、HRV 无参考、卡级综合/不综合）。真机 `default`：睡眠总时长 `baseline_window=365d` n=267 band=typical，参考 within；REM/清醒 band=below；`sleep_core` 无历史 unknown；HRV/RHR 当日无数 missing（不顶）。
- **改动**：`fact_card.py` 按指标递进 90d→365d→all；JSON 写 `baseline_window` / `baseline_earliest`；文案「相对你近 12 个月 N 夜/天」；unknown 写「个人历史 n/7」；卡级综合需睡眠+HRV+RHR 均已选且已分档否则「不综合」。注册表 `reference_range` 进睡眠总时长 / RHR / 步数；T1 披露句；深睡/REM 占比参考本轮不做（TODO）。`load_fact_card` 拉全历史。占比型参考与 HRV 列合并仍属 M1-P8。
- **回滚**：还原 `pha/fact_card.py` / `fact_card_prefs.py` / `fact_card_html.py` / 注册表三处 `reference_range` / selfcheck；官方重启。

---

## 2026-09-07 (PRD v1.6：递进基线 + 通用参考层 + 我的评估要求 + 按钮式解读；HRV 列语义；只改文档)

- **类别**：产品共识 / 文档（无代码）。
- **证据**：完整卡评估层只写「基线不足」。查 `data/pha_storage.db`（`default`）：`wearable_daily` 2016-09-26～2026-09-07 共 3504 行；`sleep_hours` 642 夜（近 365 日 268，近 90 日 **1**）、`hrv_rmssd_ms` 1936 天（近 90 日 **0**）、`resting_heart_rate_bpm` 2255、`active_energy_kcal` 2286。`fact_card.py` `BASELINE_DAYS=90` 从 as_of 回看，zip 数据止于 2026-06-09，正好全落窗外。另：`wearable_data` 11650 条 `metric_type=hrv` 的 `sample_id` 全为 `HKQuantityTypeIdentifierHeartRateVariabilitySDNN|…|Wind’s Apple Watch`——RMSSD 列自始就是 Apple SDNN。维护者定：主动 agent 与 Mac PHA 不割裂，「基线不足」不成立；同意「我的评估要求（自由文本，给 LLM）」；M3 与按钮式解读不冲突。
- **改动**：PRD v1.6：§1.3 定义「主动路径」、§1.3a 不割裂；FR-2.1 / FR-2.6 基线窗口递进 90d→365d→all + 卡上披露窗口与 n，卡级综合三档/「不综合」；FR-2.8 通用参考层（`manifest-tier-v1` T1 披露句，范围放注册表 `fact_card.reference_range`，HRV 绝对值不给人群范围）；FR-2.9 `assessment_prompt` 保存回显；FR-6 用户触发 LLM 解读（复用 `chat_service` harness + Numerics 审计、异步 + 按 `(user, as_of, sha256(prompt))` 缓存、独立区块、fail-closed、禁止预生成/裸奔）；§3/§8 M3 改为 App 接线；立 **M1-P7**（基线+参考层）、**M1-P8**（HRV 列语义纠正，叠 harness ACK）、**M1-P9**（评估要求+解读）。同步 `pha-fact-card.md`、`pha-ios-proactive-roadmap.md`、`pha-healthkit-sleep-hrv.md` RMSSD 行。新增交接文档 `handoff-2026-09-07-fact-card-assessment.md`。
- **回滚**：还原上述文档至 v1.5 口径；删交接文档。无运行时影响。

---

## 2026-09-07 (T7 FR-1.7 同步回执)

- **类别**：可运维性 / ingest 契约。
- **证据**：`python3 scripts/pha_healthkit_ingest_selfcheck.py`（含 fail→success 回执 + `GET /ingest/healthkit/last`）；`python3 scripts/pha_fact_card_selfcheck.py`。
- **改动**：`pha/healthkit_ingest_receipt.py` 落 `data/healthkit_ingest_last.json`（成功/失败时间、kind、error、精简 audit，无正文/token）；POST 成功与 fail-closed 均写入；`GET /ingest/healthkit/last?user_id=`；事实卡 JSON `facts.ingest_last` + 完整卡顶部「上次同步」。
- **回滚**：去掉路由与回执写入；还原 fact_card HTML 行。

---

## 2026-09-07 (M1-P6 门禁：有则比、无则空；真源=健康 App 展现)

- **类别**：产品口径 / 文档（PRD v1.5）。
- **证据**：删近两日 Pillow 后 15:41 POST 200；9/7 入睡 7.60 / 清醒 3.45 / 分期可展示，相对健康 App ≤8 分钟；在床健康 App 与 PHA 皆无。截图证明原虚高来自 Pillow+Watch 双轨。「显示所有数据」+ Data Sources 含 Pillow / 多块 Watch / iPhone。
- **改动**：FR-1.6、任务卡门禁、review §6：只验收健康 App 有且用户已勾选的项；禁止硬编码必采睡眠项（呼应 FR-2.7）；真源=健康 App 展现，M1 单源过渡、多源优先级对齐属 M2。更新锚点 A 与偏差表。无代码。
- **回滚**：还原 PRD / 任务卡 / review / 本条目至 v1.4 口径。

---

## 2026-09-07 (T6.1 睡眠 D1 必须带日期谓词)

- **类别**：捷径采集窗口。
- **证据**：真机两遍 `pha-sync-sleep`（15:02 / 15:03，`192.168.77.9`）均为 `POST 400 sleep_stage_list_mismatch`，正文 `---VALUES---` 空；维护者确认新捷径健康权限已开。`/Users/hwh/Downloads/healthkit.json` 即该 400。结论：Health Find 只有 Type Sleep + Limit、没有日期条件时返回空集（仍会 POST）。`python3 scripts/pha_healthkit_ingest_selfcheck.py`。数量捷径未改。
- **改动**：D1 Find 增加 `Start Date is in the last 2 days`（Operator 1001 / Number 2 / Unit 16384），保留 Latest First + Limit 150。last 1 day 无 Limit 曾崩 Get Details，故仍用 Limit 封顶。Source/Device 本轮不动（一次只改一处）。
- **回滚**：去掉 last-2-days 谓词，或生成 `variant=is_today`。

---

## 2026-09-07 (T6 睡眠捷径 D1：降序 + Limit 150)

- **类别**：捷径采集窗口。
- **证据**：`python3 scripts/pha_healthkit_ingest_selfcheck.py`（含 D1 plist：Limit 150、Latest First、无 is today、无 9/6 锚点文案；`is today` 备选仍带原过滤器）。数量捷径 `_find_health` / `_get_detail` 未改。
- **改动**：主捷径「PHA 同步睡眠」Find Sleep 改为按 Start Date 最新优先、Limit 150（T0 一夜 64 段，150 留余量）；Get Details 试加 Source/Device，写入可选 `---SOURCES---` / `---DEVICES---`（长度不一致则忽略，不整晚拒）；显示结果删掉写死的 9/6 锚点。另生成 `pha-sync-sleep-is-today.shortcut` 备选。ingest 解析多出来的分段以免 ENDS 被污染。
- **回滚**：生成回 `is today` 版（`variant=is_today`）；还原 `build_sleep` 与 `parse_sleep_bundle_text`。

---

## 2026-09-07 (T3 偏离基线核对文案；T4 在床/会话跨度；T5 同日睡眠日键清理)

- **类别**：事实卡文案 + ingest 在床规则 + 数据卫生。
- **证据**：`python3 scripts/pha_fact_card_selfcheck.py`；`python3 scripts/pha_healthkit_ingest_selfcheck.py`。真机 9/7 已是入睡 7.483 / 分期空 / 清醒 2.683 / 在床空（T1+T2）。
- **改动**：睡眠指标偏离近 90 日分位时，通知与完整卡追加「请到健康 App 核对」固定句（禁用判定词）；`in_bed_hours` 只来自 In Bed 样本，派生 `sleep_period_hours` 不写进在床，效率仅在有在床时写入审计；`in_bed<1h` 且无分期时事实卡显示「无」。睡眠 bundle 成功后删除该醒来日全部 `healthkit|…|sleep_*` 日键行再重算；维护脚本 `scripts/pha_sleep_cleanup_day.py`。
- **回滚**：还原 `pha/fact_card.py`、`pha/models.py`、`pha/sqlite_storage.py`、`pha/wearable_daily_aggregator.py`、`pha/healthkit_ingest.py` 后官方重启；删清理脚本。

---

## 2026-09-07 (T1+T2 分段落库 + 入睡总并集 + 醒来日正午窗口)

- **类别**：ingest 正确性。
- **证据**：自检 `python3 scripts/pha_healthkit_ingest_selfcheck.py`（含 9/6 式 6 段 ±0.02、审计行、分段表幂等、跨分期 `stage_overlap` 分期列空、23:00–07:00 归醒来日、晚 23:30 不混进昨夜、`stale_sleep_bundle`）。
- **改动**：`PHA_SLEEP_V1` / `sleep_*` 列表写入 `wearable_sleep_segments`（先删该醒来日 `healthkit|` 分段再插入）；日表从分段重算；入睡 = Core∪Deep∪REM∪Asleep 一次总并集；Σ分期并集偏离 >5% 则 `stage_overlap=true` 且核心/深/REM 写空；醒来日 D = 最后一段睡眠结束日，窗口 `[D-1 12:00, D 12:00)`；D 早于收到日 >1 天 → 400 `stale_sleep_bundle`。zip 分段仍走原 SUM deep/rem。数量捷径路径未改。
- **回滚**：还原 `pha/healthkit_ingest.py`、`pha/sqlite_storage.py`、`pha/wearable_daily_aggregator.py`、`pha/sleep_aggregator.py` 后官方重启。

---

## 2026-09-07 (T0 回放结案：跨分期重叠导致 10.6h)

- **类别**：取证。
- **证据**：14:00:59 `192.168.77.252` POST **200**，正文落入 `data/local_shortcuts/sleep_body_2026-09-07.txt`。日表与前两次逐位相同。回放：入睡一次总并集 7.483h（健康 App 7.717h，差约 14m 窗口缺口）；入库 10.6h = 各分期并集相加。跨分期重叠 38 对 / 2.1h；同分期交错核心多计 1.633h；完全重复 0；深睡并集=求和=1.633 与健康 App 一致。
- **改动**：review §2 写入 T0 结论。无新代码。
- **回滚**：不适用。

---

## 2026-09-07 (T0 回放脚本；正文落盘待下次 POST)

- **类别**：ingest 取证（不碰日表数字）。
- **证据**：11:59 / 12:34 两次 200 的正文未完整入日志（400 预览截到 `---STARTS---` 第一行；200 未记 body）。VALUES 64 段：Core 27 / Awake 17 / REM 13 / Deep 7。无 STARTS/ENDS 无法定位 13.28h 多出的 ≥1.3h。
- **改动**：`scripts/pha_sleep_bundle_replay.py` 离线打印分段、同/跨分期重叠、完全重复、每分期求和 vs 并集、入睡总并集、会话跨度。`parse_sleep_bundle_text` 成功解析后把全文写到 gitignored `data/local_shortcuts/sleep_body_{day,latest,timestamp}.txt`（无 token）。
- **回滚**：删脚本；去掉 `_persist_sleep_bundle_for_replay`。

---

## 2026-09-07 (12:34 第二次真机 200，结果逐位相同；清醒口径定稿；只改文档)

- **类别**：真机验收 + 文档（无代码）。
- **证据**：`192.168.77.198` 12:34:35 POST **200**，日表 9/7 与 11:59:58 逐位相同（入睡 10.6 / 核心 6.033 / 深 1.633 / REM 2.933 / 清醒 2.683 / 在床空）。重复计入可复现。维护者定口径：健康 App 没有「入睡前」概念，睡眠从入睡起算，核心/REM/深睡计入入睡，清醒不计入；9/7 入睡前那块按采集特例。
- **改动**：撤回「清醒三分解」产品列提案；`awake_duration_hours` = 健康 App 原值。12:37 维护者补充：9/7 会话由 20:30 一段 4 分钟 Deep 开启后 ≈2.2h 清醒，App 与 Apple 规则均无误。12:42 定稿：**PHA 不判定某夜是否采集失误、不打 `collection_anomaly` 类标签、不修正、不排除**（两版标记提案作废）；T3 改为「睡眠各项接入事实卡既有个人 90 日基线分档，偏离时加固定模板『…明显高于/低于你近 90 日的水平，请到健康 App 核对这一夜的数据』」，文案禁用判定词。review §3/§4-E/§6/§7、任务卡、PRD FR-1.6 与 §11/§12 同步。
- **回滚**：还原文档。

---

## 2026-09-07 (健康 App 9/7 真值到位；T0–T9 任务表；只改文档)

- **类别**：文档 / 共识（无代码）。
- **证据**：维护者截图（12:23）健康 App 9/7：在床 8h57m、入睡 7h43m、清醒 3h35m（约 20:30–22:45 一块 ≈2.2h 在入睡前）、REM 1h6m、核心 4h59m、深 1h38m。库同夜：深 1.633 精确一致；REM 2.933 vs 1.10；核心 6.033 vs 4.983；清醒 2.683（午夜后真值约 1.4）。入睡+清醒 11.30 ≠ 在床 8.95。
- **改动**：review §2 写入真值对照与推断（非均匀放大 → 不是简单双来源；深睡一致 → 解析链正确，问题在重复/重叠段去重）；否决 D3「在床 = 会话跨度」；review §7 改为 T0–T9 任务表（取证回放 → 分段落库 → 总并集/窗口 → 清醒三分解 → 在床规则 → 清理 → 捷径 D1 → 回执 → 文档 → 三夜验收）。任务卡锚点 A=9/7、B=9/6，禁止推导在床。PRD §11 追加一行。
- **回滚**：还原三份文档。

---

## 2026-09-07 (12:13 重跑无 POST；M1-P6 中期复盘，只改文档)

- **类别**：文档 / 共识（无代码）。
- **证据**：12:13 维护者重跑，日志 2029128 行以后无任何 `POST /ingest/healthkit`，库仍是 11:59:58 那次。9/7 入睡 10.6 + 清醒 2.68 = 13.3h > 12h 窗口，分期重叠被重复计入。维护者确认健康 App 9/7 清醒 3.35h 含入睡前约 2h（Apple Awake 定义）。
- **改动**：新增 [`pha-sleep-ingest-review-2026-09-07.md`](pha-sleep-ingest-review-2026-09-07.md)（错误清单 A–I、方案、完成门禁、编码顺序）。任务卡 [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md)：醒来日由数据推导、正午窗口、入睡 = 一次总并集 + `stage_overlap`、清醒三分解、分段落库 + 审计行、校验粒度、当前实现偏差表、捷径候选 D1/D3、遗留清理、完成门禁。PRD v1.4：FR-1.6 验收细化、新增 FR-1.7 同步回执、M1-P6 行、§11 三条、§12。
- **回滚**：还原上述三份文档；无运行时影响。

---

## 2026-09-07 (睡眠真机 200；日表有数，尚未对上健康 App)

- **类别**：真机验收。
- **证据**：`192.168.77.198` `POST /ingest/healthkit` **200**，`received_at=2026-09-07T11:59:58`。日表 9/7：`sleep_hours=10.6`、`sleep_core=6.033`、`sleep_deep=1.633`、`sleep_rem=2.933`、`awake=2.683`、`in_bed` 空。核心+深睡+REM=入睡成立。`in_bed` 空符合 `is today` 丢掉午夜前 In Bed。10.6h 入睡偏长，可能多源分期重叠；**未**与健康 App 9/7 醒来日对账，M1-P6 不标 DONE。
- **改动**：无新代码；记录本次 200。
- **回滚**：不适用。

---

## 2026-09-07 (睡眠 POST 通；零时长分段拒批)

- **类别**：ingest 解析。
- **证据**：第二次真机 POST 日期已解析，400 `implausible_sleep_hours`（reject 发生在列表配对，不是秒→小时）。日表仍无 9/7。Shortcuts 日期精确到分钟时，短分段会变成 end==start，旧逻辑整晚 fail-closed。
- **改动**：跳过 0～2 分钟的倒序/零时长分段；同分期重叠做区间并集；超过 2 分钟的倒序仍 400。自检 `test_sleep_zero_duration_skipped_and_overlap_unioned` PASS。
- **回滚**：还原 `pha/healthkit_ingest.py` 的 `sleep_stage_hour_samples_from_lists`，再官方重启。

---

## 2026-09-07 (睡眠 POST 通；日期窄空格)

- **类别**：ingest 解析。
- **证据**：11:5x `PHA_SLEEP_V1` 已到 Mac，400 `unreadable_timestamp:7 Sep 2026 at 12:01 AM`（`\\u202f`）。分期标签是 `Core/Deep/REM/Awake`。日表未写入 9/7。
- **改动**：`safe_parse_datetime` 先把窄空格收成普通空格，再用与 locale 无关的 Shortcuts `d Mon YYYY at h:mm AM` 解析。自检 `test_shortcut_sleep_date_format` PASS；`bash scripts/pha_restart_accept.sh` PASS。
- **回滚**：还原 `pha/date_parser.py`，再官方重启。

---

## 2026-09-07 (睡眠上传再中断；改回 is today)

- **类别**：捷径。
- **证据**：探测版 `is today` 6 条样本能跑；加上 last 1 day + Get Details + POST 又 *problem running*，无新 POST。Sleep 样本一多，Get Details / Quick Look 会崩（已知 Shortcuts 问题）。
- **改动**：Find 改回已通的 `Start Date is today`。取 Value/Start/End 后只 Show 文本。Get Details 同时写 `WFInput` 与 `Input`。
- **回滚**：还原 `build_sleep` Find 行。

---

## 2026-09-07 (睡眠探测通过，接上传)

- **类别**：捷径。
- **证据**：真机 Find `Type is Sleep` + `is today` 跑通，弹出至少 6 条 Health sample。无 `"ok": true` 是因为探测版故意不 POST；Show 健康对象会变成列表选择，不是 JSON。
- **改动**：Find 改为 last 1 day（覆盖昨夜午夜前入睡）。取 Value / Start Date / End Date 写入 `PHA_SLEEP_V1` 文本再 File POST。显示结果只出文本和服务器 JSON。
- **回滚**：还原 `build_sleep` 为两步探测。

---

## 2026-09-06 (睡眠捷径缩成探测)

- **类别**：捷径。
- **证据**：File 文本体版仍无 POST，同一句 *problem running*。Comment / Get Details / JSON body 都可能是未接参数。
- **改动**：只保留与数量捷径同一套 Find XML（`Type is Sleep` + `Start Date is today`）和显示结果。先确认 Find 能跑。
- **回滚**：下一步再加 Get Details 与 POST。

---

## 2026-09-06 (睡眠改回 File 文本体)

- **类别**：ingest + 捷径。
- **证据**：列表版 JSON body 无新 POST，仍是 *problem running*。与 Count 同类：自造 JSON 字段未接上。
- **改动**：POST 改回已通的 Text → File。正文 `PHA_SLEEP_V1` + VALUES/STARTS/ENDS。编辑页顶部有注释「PHA睡眠列表版」。
- **回滚**：还原 `build_sleep` 与 `parse_sleep_bundle_text`。

---

## 2026-09-06 (睡眠改为列表入库)

- **类别**：ingest + 捷径。
- **证据**：19:41 第一条 `sleep_in_bed=0.727` 后捷径中断。编辑页 Value 仍是 `anything`，自造分期过滤会直接报 *problem running*。
- **改动**：捷径只 Find `Type is Sleep` + last 2 days，取出 Value / Start Date / End Date 各一份列表 POST。服务端配对、只留最近 24 小时重叠分段、按分期求和。禁止再生成 Value 枚举行或 Count。
- **回滚**：还原 `build_sleep` 与 `parse_ingest_payload` 的 sleep_* 列表分支。

---

## 2026-09-06 (睡眠捷径无法运行)

- **类别**：Telemetry → 捷径。
- **证据**：新捷径弹出 *There was a problem running the shortcut*；Mac 无新 POST。编辑页：`Start Date is in the last 1` 已生效，但 Count 显示 `Count Items in Input`，Value 显示 `anything`。
- **改动**：去掉自造 Count（必填 Input 没接上会直接中断）。Value 枚举补 `Unit: 4`，避免导入成 anything。
- **回滚**：还原 `_find_sleep` Value 行；不要把 Count 加回去。

---

## 2026-09-06 (睡眠三次空 value；日期 Unit)

- **类别**：Telemetry → 捷径。
- **证据**：19:29 五条 `sleep_*` 仍 `value=""` 400。日表 9/6 睡眠列全空。健康 App：在床 8.6 / 入睡 6.75 / 核心 4.6 / 深睡 0.55 / REM 1.6 / 清醒 1.85。In Bed / Awake 标签已对仍空，主因是 `Operator 2` + 自造 Date token。
- **改动**：Find 日期改为 `Operator 1001` + `Number 1` + `Unit 16384`（is in the last 1 day）。分期标签保持 ActionKit：`Asleep Core/Deep/REM`。
- **回滚**：还原 `_find_sleep` 日期行。

---

## 2026-09-06 (睡眠捷径空 value)

- **类别**：Telemetry → 捷径。
- **证据**：五条 `sleep_*` POST `value=""` 400；健康 App 9/6 在床 8h36m / 入睡 6h45m 未入库。
- **改动**：窗口改为 Start Date after now-24h；Duration 先 Sum 再 ÷3600。ingest 把 (16, 57600] 的秒收成小时。
- **回滚**：还原 `_find_sleep` / `_sync_one_sleep_stage` / `_as_sleep_hours`。

---

## 2026-09-06 (M1-P6 睡眠分期捷径)

- **类别**：ingest / 注册表 / 捷径。
- **改动**：日列 `sleep_core_hours` / `in_bed_hours`；ingest `sleep_core|deep|rem|in_bed|awake`；入睡小时 = 核心+深睡+REM。独立捷径「PHA 同步睡眠」，Find Sleep 分期 Duration÷3600，窗口昨午–今午。数量捷径不改。
- **回滚**：去掉睡眠捷径任务与新 ingest 键；日列可留空。

---

## 2026-09-06 (真机 HRV SDNN 入库)

- **类别**：Telemetry。
- **证据**：19:09–19:10 三次 `POST /ingest/healthkit` 200；`healthkit|default|hrv_sdnn|2026-09-06` = **40.968**；日表 `hrv_sdnn_ms=40.968`，`hrv_rmssd_ms` 空；活动消耗更新为 703.626，rhr=60。
- **改动**：无代码。HRV 当时日均真机刀完成；睡眠仍未做。
- **回滚**：无。

---

## 2026-09-06 (M1-P6 第一刀：HRV SDNN 当时日均)

- **类别**：ingest / 注册表 / 事实卡 / 捷径。
- **改动**：新日列 `hrv_sdnn_ms`；`POST hrv_sdnn` 与 HK SDNN 别名只写该列。勾了 `hrv_rmssd_ms` 则捷径 Find `Heart Rate Variability` Average。事实卡 RMSSD 为空时展示 HRV (SDNN)，基线不混用。睡眠捷径仍不做。
- **回滚**：去掉注册表 `hrv_sdnn_ms` 行与 ingest `hrv_sdnn`；日列可留空。

---

## 2026-09-06 (真机活动消耗入库)

- **类别**：Telemetry。
- **证据**：18:58 两次 `POST /ingest/healthkit` 200；`healthkit|default|active_energy|2026-09-06` = **701.69**；同日 rhr=60。日表 `2026-09-06`：`active_energy_kcal=701.69`，`resting_heart_rate_bpm=60`。
- **改动**：无代码。M1-P5 数量型按此标 DONE。
- **回滚**：无。

---

## 2026-09-06 (活动消耗 Find 标签错：Active Energy ≠ Active Calories)

- **类别**：Telemetry → 注册表 / 捷径。
- **证据**：健康→Shortcuts 只有 Resting Heart Rate、Steps；跑捷径报 No Samples Found / Active Energy；同一次 RHR 60 入库 200。权限列表不会出现从未被正确请求的类型。
- **改动**：`shortcut_health_type` 改为 Find 选择器标签 `Active Calories`。M1-P6 写入「当时日均」语义（起床后跑 = 当日已有 SDNN 的 Average）。
- **回滚**：把注册表该字段改回 `Active Energy`。

---

## 2026-09-06 (活动消耗空 value；睡眠/HRV 立 M1-P6)

- **类别**：Telemetry → 捷径 / 新任务卡。
- **证据**：18:29 活动消耗 POST `value=""` 三次 400；同一次跑步静息心率 59 入库。
- **改动**：Find 不再给 Active Energy 加 kcal 单位；Statistics 后再 Detect Number 再写入 JSON。睡眠/HRV 全项分析改 [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md)（M1-P6）。
- **回滚**：还原 `_find_health` / `_sync_one_metric`。

---

## 2026-09-06 (同步未进库：健康 App ≠ PHA 账本)

- **类别**：Telemetry / 捷径稳健性。
- **证据**：完整卡 5 项全无；`default` 的 healthkit 行只有 9/4、9/5 步数；打开完整卡期间日志只有 GET view/prefs，**零** `POST /ingest/healthkit`。
- **改动**：完整卡披露最近一次 HealthKit 入库。捷径改回已跑通的 Find→合计→POST（去掉坏的 Count/If）；Find 写入 `WFHealthActionUnit`（kcal / count/min）。
- **回滚**：还原捷径生成器与 `facts.healthkit` 披露。

---

## 2026-09-06 (M1-P5 多指标入库：步数 / 消耗 / 静息心率)

- **类别**：ingest 捷径 / 注册表 / PRD FR-1.5。
- **根因**：完整卡可勾选，但生产捷径只 POST 步数；评估覆盖率诚实偏低。
- **改动**：`fact_card.shortcut_health_type` + 用户已选 → 生成「PHA 同步健康」；每项 Find 当日数量 → Sum/Average → **只 POST 一个数字**。`daily_key` 的 ingest 按日历日 UPSERT。睡眠（category）与 HRV（SDNN≠RMSSD）写 `shortcut_skip_reason`，不同步、不编数。
- **回滚**：还原捷径生成器与 `healthkit_ingest.daily_key_stored_types`；去掉注册表 shortcut 字段。

---

## 2026-09-06 (M1-P3/P4 完整卡可点开 + 用户自选指标)

- **类别**：PRD v1.3 / 事实卡触达 / 反硬编码。
- **根因**：iOS「显示通知」锁屏截断长正文，且捷径通知没有自定义点击深链；五项写死在 `pha/fact_card.py`，违反宪法「禁止防御性硬编码」。
- **改动**：锁屏只留短导语 + `open_path`；`GET /proactive/fact-card/view` 渲染完整清单与评估；捷径先做「URL」再「打开 URL」（直接写 `WFURL` 会被忽略，iPhone 报「无 URL」）。指标允许集改 `wearable_metric_registry.json` 的 `fact_card`；用户勾选落 `data/fact_card_prefs.json`。多指标入库立为 **M1-P5**（见 roadmap），本刀不编未入库数字。
- **回滚**：还原 `fact_card.py` / `fact_card_api.py` / 捷径生成器；去掉 `fact_card_prefs.py` / `fact_card_html.py`。

---

## 2026-09-06 (M1-P2 通知内容契约：五项 + 卡级评估)

- **类别**：事实卡模板 / PRD v1.2。
- **根因**：首版通知只拼接「有值的前 3 项」，库里只有步数时用户只看到一个数字，评估层等于没交货。
- **改动**：正文固定枚举 FR-1.4 五项（无数写「无」）；`assessment.summary`（覆盖率 / stale / 基线分档）+ 一句建议。分析不是 LLM。
- **回滚**：还原 `pha/fact_card.py` 通知拼装。

---

## 2026-09-06 (M1-P1 真机：iPhone 收到事实卡通知)

- **类别**：主动通道验收。
- **证据**：`pha-8788.log` 出现 `192.168.77.219 GET /proactive/fact-card?user_id=default 200`（非 127.0.0.1）；维护者确认手机弹出通知。
- **当时卡**：calendar 2026-09-06，`as_of=2026-09-05`，`stale=true`，步数 14872，基线 n&lt;7 不做分档。未改代码。

---

## 2026-09-06 (M1 开工 · 事实卡两层 + iPhone 本地通知通道)

- **类别**：PRD v1.1 + 无 LLM 事实卡引擎 + GET。
- **产品**：主动通道冻结为 **iPhone 捷径本地通知**（不是 Mac 通知、不是 APNs、不是 LLM 评估）。卡分 `facts` / `assessment`。v1.2 起通知必须五项 + 卡级评估。
- **代码**：`pha/fact_card.py`（点日缺行不顶；`as_of=MAX(day)` + stale）；`GET /proactive/fact-card`（同源 ingest token）；捷径「PHA 事实卡通知」。
- **回滚**：去掉 `fact_card.py` / `fact_card_api.py` 与 `main.py` 的 include_router。

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
