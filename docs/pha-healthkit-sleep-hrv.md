# 任务卡 · 睡眠 / HRV 全量入库（M1-P6）

> 状态：`IN_PROGRESS` · HRV 真机已对上；睡眠 2026-09-07 11:59 首次真机 **200**，但入睡+清醒=13.3h 超出 12h 窗口（分期重叠重复计入），且清醒未拆入睡前在床；**未对上健康 App，不得标 DONE**  
> 复盘与方案：[`pha-sleep-ingest-review-2026-09-07.md`](pha-sleep-ingest-review-2026-09-07.md)（编码前必读）  
> 上位：PRD FR-1.6 / M1-P6；宪法：fail-closed、禁止把对不上的数写进同一列  
> 推动力：真机活动消耗已对上；睡眠/HRV 勾了仍为「无」是本卡范围

分析要用「各项」，不能只取一个睡眠小时或把 SDNN 冒充 RMSSD。

---

## iPhone「健康」App / HealthKit 实际能提供什么

以 **Apple Watch + iPhone 健康** 为准（无 Watch 则分期/夜间 HRV 通常没有）。

### 睡眠（健康 App「睡眠」页）

| 健康 App 上看见的 | HealthKit 真源 | 捷径能不能像步数那样「当日一个数量」 |
|-------------------|----------------|--------------------------------------|
| 在床时长 | `Sleep Analysis` = In Bed 各段起止 | 否，要分段求和 |
| 入睡总时长 | Asleep / Asleep Unspecified 各段 | 否 |
| 核心睡眠 | Asleep Core（watchOS 9+ 分期） | 否 |
| 深睡 | Asleep Deep | 否 |
| REM | Asleep REM | 否 |
| 清醒（睡眠窗内） | Awake 各段 | 否 |
| 睡眠效率 | 健康 App **算出来的**，不是独立样本 | 须用 入睡/在床 自己算，禁止编一个效率样本 |
| 睡眠心率 / 呼吸率 | 数量类型，常落在睡眠窗 | 可另卡；不是 Sleep Analysis |
| 腕温（部分机型） | `Apple Sleeping Wrist Temperature` | 数量，另列 |

**没有**名为「睡眠小时」的官方数量类型。健康 App 的「睡了 7 小时」是把 Asleep 分段加总后的展示。

### HRV（健康 App「心率变异」）

| 健康 App 上看见的 | HealthKit 真源 | 说明 |
|-------------------|----------------|------|
| HRV 点、日均线 | Find 标签 `Heart Rate Variability` = **SDNN（毫秒）** | Watch 在夜间/呼吸时打点，一天多条 |
| RMSSD | **Apple 不提供** | 第三方才可能写。**M1-P8 DONE**：历史误标列已迁到 `hrv_sdnn_ms`；注册表 `hrv_rmssd_ms` 标 deprecated、非 fact_card eligible；新写入一律 SDNN |

可从 SDNN 点算出、且应用来分析的：**条数、当时日均、最低、最高、夜间窗均值**。这些是聚合，不是健康里另一条原始类型。

#### 当时日均（本刀已编码）

捷径跑的那一刻，对**当日已经写入的 SDNN 点**做 Average，就是「实时均值」。它等于当日均值在那个时刻的值，不是另一种 Health 类型。

- 上午起床后跑：白天通常还没有新点，这个数基本就是昨夜睡眠窗的均值，分析价值高。
- 傍晚再跑：同一列会被白天新点（若有）更新；带 ingest 时间戳，禁止假装成「日终官方均值」。
- 入库：`POST metric_type=hrv_sdnn` → 日列 `hrv_sdnn_ms`。**禁止**写入 `hrv_rmssd_ms`。
- 事实卡：勾了「HRV」且 RMSSD 为空时，展示 **HRV (SDNN)**，基线只用 SDNN 列。
- 采集：Find `Heart Rate Variability` → Average → 一个数字。首次须在捷径里点 Allow Access。

---

## 跨夜规则（睡眠编码前冻结）

健康 App 把**一整晚**显示成一条睡眠，日期是**醒来日**，不是入睡日。真机 2026-09-06：页上写 Sep 6，入睡 9/5 23:03，在床 8h36m，入睡 6h45m。不会把两晚加在一起，除非真的连睡两晚。

**日键**：跟健康 App 一样，记在醒来日。**醒来日 D 由数据推导** = 最后一段睡眠分期结束时刻的日历日，不用 `received_at`。若推导出的 D 比收到时间早 1 天以上，返回 `stale_sleep_bundle`，让用户知道拿到的是旧夜。

**一晚窗口**：醒来日 D 的睡眠 = 与 `[D-1 12:00, D 12:00)` 相交的分段（覆盖「昨晚 23 点到今早」这一整晚，不含再往前那一晚，也不含今晚刚开始的那截）。

**产品真源**：用户判断以 **健康 App 展现** 为准，不是 HealthKit 多源原始并集。健康 App 按数据源优先级只展示一套；PHA 应对齐该展现。M1 过渡：维护者侧简化为单写入源（删第三方如 Pillow 历史后仅 Watch）；Shortcuts 取不到可靠 Source，多源系统优先级对齐留给 **M2**（HealthKit API / `sourceRevision`）。禁止为了对上数字手改样本。

**验收锚点 A（2026-09-07 · 同一夜）**：

| 时刻 | 健康 App / 说明 | PHA 库 |
|---|---|---|
| 12:23（含 Pillow） | 在床 8.95、入睡 7.717、清醒 3.583、核心 4.983、深 1.633、REM 1.100 | 早期虚高（双轨并集） |
| 15:41（删近两日 Pillow 后） | 在床 **无**；入睡/清醒/分期 ≈ Watch 行 | 入睡 7.60、清醒 3.45、核心 4.90、深 1.65、REM 1.05、在床 **空**；相对健康 App 差 ≤8 分钟；`stage_overlap=false` |

原锚点 A 的在床 8.95 来自 Pillow；删除后健康 App 与 PHA 皆无在床，按门禁「双方皆空算过」。

**验收锚点 B（2026-09-06 · 健康 App Stages）**：在床 8.6、入睡 6.75、清醒 1.85、REM 1.6、核心 4.6、深睡 0.55。这晚入睡+清醒 = 在床，是入睡潜伏期短的巧合，**不是规则**。

**在床只能来自 In Bed 样本**，健康 App 无或取不到 → PHA 写空、事实卡写「无」；不得用会话跨度推导。派生列 `sleep_period_h`（首段睡眠开始 → 末段睡眠结束）另存，不写进在床。在床不是必采项：`sleep_in_bed` 注册表 `enabled_default: false`，是否展示/关心由用户勾选（FR-2.7）。

禁止：

- 只用 `Start Date is today`（丢掉午夜前的入睡）
- 把最近两个日历日全部分段加总且不切会话（晚上跑会把两晚加在一起）
- 把 In Bed + Awake 算进「睡了多久」
- **把各分期分别求并集再相加当入睡总时长**（跨分期重叠会重复计入）
- POST 一条「睡眠效率」样本
- 为了让清醒「好看」删掉入睡前在床的那段（那是编数据）
- 用「入睡 + 清醒」或会话跨度推导在床
- 健康 App 无在床时仍要求 PHA 有在床，或硬编码「睡眠六项必须齐」

**分期合计**：In Bed / Core / Deep / REM / Awake / Asleep Unspecified 各只计本类。**入睡总时长 = 所有睡眠分期段的一次总并集**（Core ∪ Deep ∪ REM ∪ Asleep），不含 In Bed、不含 Awake。各分期小时数只在「单来源、互斥」时采信；`Σ分期` 与总并集相差 > 5% 即标 `stage_overlap`，分期列写空、只写总并集。效率 = 入睡/在床，只在服务端算。

**清醒口径（维护者 2026-09-07 定）**：健康 App 没有「入睡前」概念；睡眠从入睡开始算，核心/REM/深睡计入入睡，清醒不计入。`awake_duration_hours` = 健康 App 清醒原值，不拆、不删、不加派生产品列。9/7 的会话从 20:30 一段 **4 分钟 Deep** 开始，随后 ≈2.2h 清醒，22:45 才真正入睡：App 按「入睡后未睡着 = 清醒」算得没错，规则没错。**PHA 不判断这是不是采集错误，不打标签、不修正、不排除**——人的睡眠本就千差万别，PHA 无法判定。PHA 只做：睡眠各项与个人近 90 日基线比，偏离时在通知/完整卡加一句固定模板「{指标} {值}，明显{高于/低于}你近 90 日的水平，请到健康 App 核对这一夜的数据」。用户核对后若在健康 App 修改，下次同步覆盖。文案禁用「错误 / 异常 / 采集失误」等判定词。

**分段落库**：捷径送来的每一段写入已有的 `wearable_sleep_segments`（`sample_id = healthkit|{user}|{stage}|{start}|{end}|{source}`，幂等），日表全部从分段重算；不再直接落「分期小时数」日键行。成功响应与日志打一行审计：`kept / skipped_zero / dropped_unknown_label / per_stage_h / union_asleep_h / session_span / window / stage_overlap`，手机「显示结果」原样显示。

**校验粒度**：结构性错误（三列表长度不一、标记缺失、时间戳不可读、倒序 > 2 分钟）整批拒；装饰性瑕疵（零时长、未知标签）按段跳过并计数。

**当前实现偏差（2026-09-07 15:41 后）**：

| 项 | 规范 | 现状 |
|---|---|---|
| 醒来日 / 正午窗口 / 总并集 / 分段+审计 | 见上文 | **已落地**（T1–T2） |
| 清醒 + 偏离基线提醒 | 见上文 | **已落地**（T3） |
| 在床只取 In Bed；无则空 | 见上文 | **已落地**（T4）；9/7 双方皆空 |
| 同日 sleep_* 日键清理 | 见上文 | **已落地**（T5） |
| 捷径窗口 | 覆盖昨夜；有则取 In Bed | D1：last 2 days + Limit 150；Source/Device 空（Shortcuts 对 Sleep 不吐来源） |
| 真源 = 健康 App 展现 | 按系统优先级只留展示源 | **M1 过渡**：维护者删 Pillow 后单源≈展现；多源自动对齐属 M2 |
| FR-1.7 回执 | 上次同步可见 | **已落地**（T7）：`GET /ingest/healthkit/last` + 完整卡顶部 |

**捷径（过渡态）**：「PHA 同步睡眠」= Find `Type is Sleep` + `Start Date is in the last 2 days` + Start Date 最新优先 + Limit 150；取 Value / Start / End（及空的 Source/Device）写 `PHA_SLEEP_V1` 一次 POST。无日期谓词时 Health Find 返回空集（已踩坑）。`is today` 备选捷径仍生成。数量捷径 `_find_health` 未改。

**遗留**：连续多夜验收（T9）。T7 回执已落地。9/6 半截残留与 orphan 日键已清。事实卡：`in_bed_hours < 1h` 且无分期 → 显示「无」。

---

## 本卡目标

1. **睡眠分段**：用户已勾选且健康 App 有样本的项入库；`in_bed_hours`（只取 In Bed）、`sleep_hours`（核心∪深∪REM 总并集）、`sleep_core_hours`、`sleep_deep_hours`、`sleep_rem_hours`、`awake_duration_hours`。无数段则该字段空，不顶昨日；**不因缺在床而判失败**。  
2. **HRV**（已对上）：`hrv_sdnn_ms` = 当时日均。禁止写入 `hrv_rmssd_ms`。  
3. 捷径可以 POST 一晚的分段文本（一次请求、几十段），但**禁止**把几百条 Health 对象直接甩给 URL 或触发「共享大量健康数据」。  
4. 验收 HRV（已过）：健康 App 当日有 HRV 点 → 库中 `hrv_sdnn_ms` 量级合理；`hrv_rmssd_ms` 不被改写。

## M1-P6 完成门禁（全部满足才可标 DONE）

1. 同一夜：健康 App 醒来日 D 截图 vs 日表。**只验收健康 App 当天有、且用户已勾选的项**，各 ≤ ±10 分钟；健康 App 没有的项（如删 Pillow 后的在床）PHA 必须空，双方皆空算过。分期互斥时写分期列；`stage_overlap` 时分期列空、只保留入睡总并集。第一夜证据 = 锚点 A 的 15:41 行。  
2. 任意一次入库满足 `入睡 + 清醒 ≤ 会话跨度 ≤ 窗口长度`（有清醒/入睡时）。  
3. 有清醒时：`awake_duration_hours` 对健康 App ±10 分钟；偏离个人基线时事实卡出「请核对」提醒句，不出判定词。  
4. 连续 3 天捷径跑完 200，无 *problem running*；每次响应含审计行。  
5. 无 `healthkit|…|sleep_*` 孤儿日键行（9/6 残留已清）。  
6. 自检覆盖：正午窗口、醒来日推导、跨分期重叠、偏离基线提醒句、零时长跳过、无 In Bed → in_bed null。

## 编码顺序

按 review §7 任务表 **T0 → T9**。T0–T8 主体已落地；余 **T9 三夜验收**。M1-P6 未全部满足前不标 DONE。

---

## 明确不做（本卡）

- 用 SDNN 填 RMSSD  
- 把 In Bed + Awake 加总当成「睡了多久」  
- 诊断标题、LLM 填数  
- Watch 独立 App  
