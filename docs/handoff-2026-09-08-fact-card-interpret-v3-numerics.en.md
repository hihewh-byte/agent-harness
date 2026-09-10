# Handoff · Fact-card interpretation numerics audit v3: graded off-card numbers + single audit + review punch list (M1-P9.4)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-08-fact-card-interpret-v3-numerics.md)

> For the successor coding agent · drafted 2026-09-08 20:10 · based on 9/8 17:06 / 17:07 on-device screenshots (interpretation repeatedly rejected `2、95、2、3、95` / `70、80、2、2、95、2、3`) and local reproduction  
> First reply must output both lines:  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.10** (FR-6.3 / FR-6.10 / §8 M1-P9.4 / §11) · [`manifest-tier-v1.md`](manifest-tier-v1.md) §3.2 / §4 (T0 before T1, T1 disclosure protocol) · [`pha-pm-constitution.md`](pha-pm-constitution.md) (anti-hardcode, no patches for a specific case)  
> **Maintainer authorized** (2026-09-08 20:11): off-card number audit **may be relaxed**, scale set by this document §2; this document lands docs and development guidance only, **no code**.  
> Previous handoff: [`handoff-2026-09-08-fact-card-interpret-v2.md`](handoff-2026-09-08-fact-card-interpret-v2.md) (§4.4 “redo card-side audit” is replaced by this document §3)

---

## 0. Required reading and live state before starting

Read order: PRD v1.10 full → `manifest-tier-v1.md` §3–§4 → harness consensus §5 → last three entries each of `harness-change-log.md` / `pha-ios-proactive-change-log.md` → this document.

**git live**: `main` is one commit ahead of `origin/main` `8462695` (unpushed). That commit’s body and message describe “assessment prompt → metric-id alias parse → narrow manifest → reject off-focus numbers”, which the maintainer judged a corner case violating Constitution article 4 and FR-6.8; the workspace already reverted it and switched to a TASK outline (see change-log 9/8 two entries). **Workspace is still dirty** (9 files modified); do not stash / checkout-discard. History cleanup in §7.

**Reproduction (do not check into the repo)**: in `/tmp` load `load_fact_card('default')` with Python, feed each §2.4 sentence to `fact_card_interpret._audit_interpretation_text`, and you get the same tokens as the screenshots; the same sentences fed to `numerics_manifest.audit_response_numerics` all `passed=True`. That is direct evidence that “the two audits disagree”.

---

## 1. Problem evidence (why we must move)

| Screenshot token | Actual source | Nature |
|---|---|---|
| `2` (every paragraph) | Digits nested in `SpO2` / `VO2max` labels. Card-side `_NUM_RE = \d+(?:\.\d+)?` has no boundary; the card’s own labels also fire | Audit false positive |
| `96.0` (local repro) | `FACT_CARD_CONTEXT` gives the model JSON raw `"value": 96.0` / `13.0`, while the allowlist only has `96` / `13`. Model copies the card and is still rejected | Our own two formats disagree |
| `95`, `70`, `80`, `3` | Educational/advice numbers: SpO2 95% common threshold, max-HR 70–80% zone, 2–3 times per week | Per FR-6.10 v1.7 must enter a T1 block; 7b cannot write an exact template |
| `9` | Suspected “September”; failure records do not store original text, cannot confirm | Observability gap |

The two audits have different rules:

| | harness `numerics_manifest.audit_response_numerics` | card-side `fact_card_interpret._audit_interpretation_text` |
|---|---|---|
| What numbers | 1–2 decimal places (non-digit anchors) + dose-context numbers + 3–6 digit bare integers | All `\d+(\.\d+)?`, no boundary |
| T1 block | `LANG_DISCLOSURE_MAP` zh/en | Only Chinese `【参考标准】…（来源：…，请自行查证…）` |
| `.0` normalize | Allowlist by formatted string | None |
| Personal-claim context | Yes (`LANG_T0_CLAIM_MAP`, T0 before T1) | None |
| Same text | `passed=True` | Reject |

Conclusion: on-screen “repeated fail” = card-side false positives + 7b cannot write T1 templates + dual audits. **Not the model inventing personal data**.

---

## 2. Decision: graded off-card numbers (relaxation scale)

### 2.1 Principles

- What we keep: **numbers that look like user measurements/dates may only ever come from the allowlist** (PRD §1 “numeric honesty and fail-closed first”).
- What we open: **general-population common sense and integer training advice** no longer must enter a T1 block, no longer must cite a source. T1 remains the recommended form “when you want a source”; in-block rules unchanged.
- Judge by **context**, not **magnitude** (lesson from the ≥100 threshold); context lexicons live in language tables; metric labels/units come from the card; **Python contains no metric names**.
- Unsure → reject (fail-closed).

### 2.2 Terms

| Term | Definition |
|---|---|
| Allowlist W | Manifest generated from the whole card: each row `value` / baseline mean / reference low-high / baseline n / window days (`90d`→90, `365d`→365, copy constants 7, 12 — the last two should be derived from the card’s window fields, see §3.3) / `as_of` / `calendar_day` / each row `day` / card times. Compare after **normalize**: `96.0 ≡ 96`, `6,484 ≡ 6484`, full-width digits to half-width |
| T1 block | `manifest-tier-v1` §4 disclosure block, zh and en forms (`LANG_DISCLOSURE_MAP`). In-block numbers are not authenticity-checked; personal-claim words in the block → `t0_forgery_in_t1_block` |
| Identifier digits | Digit flush against letters/underscores (`SpO2`, `VO2max`, `T1`, `HRV4`). Not a number token; do not count |
| Clause | After stripping T1 blocks and masking dates/times/identifiers, split on `。！？；，` and `. ! ? ; ,` |
| Personal-claim context P | Clause contains **owner words** (你 / 你的 / 您 / your / yours) or **time-owner words** (今天 / 今晨 / 昨天 / 昨夜 / 本周 / 上周 / 近 N / 最近 / 过去 / today / tonight / yesterday / this week / last N / recent) or **measurement verbs** (测得 / 记录 / 显示 / 读数 / 卡上 / 均值 / 中位 / 基线 / measured / recorded / shows / reading / baseline / median) |
| Educational context E | Clause contains **population words** (一般 / 通常 / 常见 / 多数人 / 健康成年人 / 人群 / typical / usually / most adults / general population) or **advice words** (建议 / 推荐 / 可以 / 尽量 / 控制在 / 保持在 / 目标 / 不超过 / recommend / aim for / keep / try to / target / up to) or **reference words** (参考 / 范围 / 区间 / 阈值 / 指南 / reference / range / threshold / guideline) |
| Card-metric context M | Clause contains any card row’s `label` (current locale and the other locale) or `unit` (bpm / ms / % / kcal / mL/kg/min / 步 / 小时 …, all from manifest rows, not hard-coded) |

### 2.3 Decision rules (for each number token outside W)

```
0. token is inside a T1 block            → allow (run t0_forgery scan separately in the block)
1. token is a date/time                  → must ∈ W, else unauthorized_date / unauthorized_time
2. token has 1–2 decimals (still non-integer after normalize) → must ∈ W, else unauthorized_value (S)
3. clause ∈ P                            → must ∈ W, else unauthorized_value (S)
4. clause ∉ P and ∈ E                    → allow, record educational_int (E; telemetry, not violations)
5. clause ∉ P and ∉ E and ∈ M            → reject unauthorized_value (ambiguous, fail-closed)
6. rest (no owner, no educational words, no card metric label/unit; bare integer) → allow, record educational_int
```

Rule 2 is the **only remaining “by shape” rule** in this relaxation: wearable-domain decimals are almost always measurements (HRV 32.9, sleep 7.6h); educational numbers are almost always integers or “about”. A model that wants “aim for 7.5 hours” must write “7 to 8 hours” or enter a T1 block. Intentional; write it into TASK.

### 2.4 Samples (become selfcheck cases directly; “current” = today’s card-side audit, reproduced locally)

| # | Text | Current | v3 expected | Rule hit |
|---|---|---|---|---|
| 1 | 今天血氧 96.0%，SpO2 处于正常范围。 | reject `96.0`,`2` | pass | `.0` normalize; `SpO2` is identifier |
| 2 | 你的 VO2max 51.5 mL/kg/min 与近 12 个月 129 天持平。 | reject `2` | pass | identifier |
| 3 | 一般成年人血氧饱和度高于 95% 视为正常。 | reject `95` | pass (E) | rule 4: population word |
| 4 | 建议每周进行 2–3 次中低强度有氧运动。 | reject `2`,`3` | pass (E) | rule 4: advice word |
| 5 | 训练心率控制在最大心率的 70–80%。 | reject `70`,`80` | pass (E) | rule 4: advice “控制在” |
| 6 | 你的血氧 96%，高于常见的 95% 阈值。 | reject `95` | pass | clause split: second clause ∉ P, ∈ E |
| 7 | 今天 HRV 32.9 ms，昨天 40 ms。 | reject `40` | reject `40` | second clause has “昨天” ∈ P |
| 8 | 静息心率 65 bpm 偏高。 | reject `65` | reject `65` | rule 5: card label+unit, no educational word |
| 9 | 静息心率一般在 60–100 bpm。 | reject `60`,`100` | pass (E) | rule 4 before rule 5 |
| 10 | 你的 HRV 接近 35 ms。 | reject `35` | reject `35` | rule 3 (card has 32.9) |
| 11 | 建议睡 7.5 小时。 | reject `7.5` | reject `7.5` | rule 2: decimal |
| 12 | 【参考标准】血氧常见正常范围 95% 以上（来源：WHO，请自行查证，非医疗建议） | pass | pass | T1 block |
| 13 | 【参考标准】血氧常见正常范围 95% 以上（来源：WHO） | reject `95` | pass (E) | incomplete block → degrades to ordinary text, but clause ∈ E |
| 14 | [Reference Standard] SpO2 above 95% is typical (source: WHO, verify by yourself, not medical advice) | reject `2`,`95` | pass | English T1 block + identifier |
| 15 | Your resting heart rate today is 63 bpm; adults usually sit between 60 and 100. | reject `60`,`100` | pass | clause split + E |
| 16 | 【参考标准】你的血氧 94% 偏低（来源：WHO，请自行查证，非医疗建议） | pass | reject `t0_forgery_in_t1_block` | owner word inside the block |
| 17 | 近 90 天睡眠均值 7.6 小时。（card is 365d） | reject | reject `unauthorized_window:90` + `7.6` | FR-6.8 window consistency kept |
| 18 | 2026-09-05 的静息心率是 60。（card has no that day） | reject | reject `unauthorized_date` | rule 1 |

### 2.5 Explicit tradeoffs

- **Accepted leak**: a bare integer with no owner, label, or unit (“偏高的 65”) will pass as E. Such a sentence is not a readable personal-data claim for the reader; telemetry records `educational_int`; tighten if on-device shows obvious invention.
- **Do not** use the whole sentence as the unit of judgment: a whole sentence would mark “你的血氧 96%，高于常见的 95%” all P, i.e. no relaxation. Clause split is how the relaxation lands.
- **Do not** use magnitude thresholds or shape rules like “only allow ≤ 2-digit integers” (historically withdrawn).
- **Do not** auto-retry on every failure: FR-6.6 requires the failed state to be visible. An auto-repair round (feeding violations back) is P9.4b optional, see §10.

---

## 3. Architecture decision: one audit, rules live in one place

### 3.1 Ownership

- **Sole owner of rules and lexicons**: `pha/numerics_manifest.py`. Add a **fact-card policy** that applies by profile (suggested name `fact_card` policy / `audit_scope`) implementing §2.3’s six rules. Existing `_audit_response_numerics_strict` / `_t0_plus_disclosure` semantics unchanged; only dispatch at the `audit_response_numerics` entry when `manifest.profile == "fact_card_interpret"`.
- **Lexicons**: `LANG_T0_CLAIM_MAP` expands two keys `temporal_cues`, `educational_cues` (zh and en each, same style as existing `owner_cues`). `metric_cues` no longer used on the fact-card path — card-metric context M is generated dynamically from manifest row `label` / `unit`. **`fact_card_interpret.py` must not contain any Chinese or English literal regex** (`_T1_BLOCK_RE`, `_NUM_RE`, etc. all deleted).
- **T1 block**: reuse `LANG_DISCLOSURE_MAP`, zh and en equal.
- **Identifier mask**: one generic regex (digit flush before or after `[A-Za-z_]` → mask the whole span), not an `SpO2|VO2max` list.
- **Normalize**: at manifest-build time register both “formatted string” and “normalized string” for each value (`96.0`→`96`); audit side applies the same normalize to tokens before compare; thousands separators and full-width digits in the same function.

### 3.2 What remains on the card side

`fact_card_interpret._audit_interpretation_text` shrinks to:

1. Call `audit_response_numerics(text, manifest)` (the same manifest this harness turn used, returned by `chat_service`; do not rebuild).
2. **Keep only card-specific dimensions**: window-wording consistency (FR-6.8: “近 90 天” on a 365d card → `unauthorized_window:90`). This should also sink if possible: manifest rows already have `baseline_window`; the policy can use the window-number set in W to judge “numbers in window context” — if it can sink, delete the card-side function.
3. No own T1 strip, date extract, or number extract. `_blank_card_times` duty becomes registering card times into W at manifest-build time.

Result: **harness `numerics_audit` and the card-side conclusion necessarily agree** (same function, same manifest). Cache records store one audit object; UI copy reads from it.

### 3.3 Magic numbers in `_body_numeric_atoms`

Delete `atoms.update({"7", "12"})`. Replacement: when `build_fact_card_numerics_manifest` registers `baseline_window`, also register that window’s spoken numbers at copy layer (`365d` → 12 months; `7d`/`n/7` from the card’s `coverage` denominator). Derivation lives in the manifest builder; source is card fields, not a constant set.

### 3.4 Align context-block format with the manifest

`build_fact_card_context_block` `value` / `baseline_mean` output the same formatted strings as the manifest (or the manifest also registers both raw forms). Either works; the latter is more stable: whatever shape the model sees can match.

### 3.5 Tier0 `min` band

Today: `_compress_fact_card_context` at `min` compresses 6074 characters to 190 and writes `metrics omitted`, contradicting TASK “non-empty must cite”. Handle:

- Prefer: in `harness_profile_registry` declare **FACT_CARD_CONTEXT floor band `summary`** for `fact_card_interpret` (a config item, not `if profile == ...`); when budget is short, compress generic slots other than `USER_ASSESSMENT_PROMPT` first.
- If the registry has no “slot floor” concept, `min` keeps a compact array of `[label, value, unit, day]` per row; never empty metrics.
- Selfcheck: `min` output must still contain every row’s `value`.

---

## 4. TASK text (profile layer)

Change `harness_plan._FACT_CARD_INTERPRET_TASK`, principles:

1. **Numbered items**, no longer one 1k-character English paragraph. 7b follows numbered rules clearly better than long prose.
2. Number rules rewritten as three levels, matching §2.3:
   - Your own data: only numbers and dates that appear in the manifest / context; copy decimals as-is;
   - General-population common sense and training advice: integers OK (e.g. 95%, 70–80%, 2–3 times), **no decimals**; cite a source with a T1 block;
   - Absolute dates may only be as_of / calendar_day / each row day.
3. **T1 template by response_locale**: TASK has a placeholder (e.g. `{T1_TEMPLATE}`); Tier0 assembly takes the locale example from `LANG_DISCLOSURE_MAP`. TASK source no longer has a Chinese template literal.
4. Generic constraints (plain text, no diagnosis, language follows locale, do not repeat the disclaimer) move to the generic layer if the profile already has a corresponding slot or tail; TASK keeps only: outline = USER_ASSESSMENT_PROMPT, named only talks named, non-empty must cite, three-level numbers, window wording consistent.
5. Cache key: replace hand-string `_INTERPRET_PROMPT_REV` with `sha256(TASK text + policy version)[:12]`; TASK change auto-invalidates. Policy version lives next to the `numerics_manifest` policy constant.

---

## 5. Failed state and observability

1. `failed` cache records add `rejected_text` (local data; FR-6.6 already allows showing rejected tokens; original text is the same nature). Log line `turn_complete … numerics=FAIL` also prints violations and the first 200 characters of text.
2. UI copy (`fact_card_copy`): dedupe violations, merge by class — “measurement not on the card: 65 bpm”, “date not on the card: 2026-09-05”, “the reference-standard block wrote your data”. Stop dumping `2、95、2、3、95` as-is to the user.
3. After two consecutive same-key failures, one extra hint under the button (one sentence each zh/en, into `fact_card_copy`): “Interpretation can only cite numbers on the card; general common sense may use integers, not decimals.” Expectation management, not retry logic.
4. Telemetry: audit object adds `educational_ints` (list of allowed E-level integers) to watch for leaks after the relaxation.

---

## 6. Selfcheck (behavior tests, replace text assertions)

`scripts/pha_fact_card_selfcheck.py`:

- Delete literal assertions on TASK text (contains "outline", does not contain `FACT_CARD_CONTEXT.focus`). TASK is a profile product; test its behavior, not its wording. Keep one: TASK source contains no `【参考标准` / `[Reference Standard` literal (prevent template hardcode flowing back).
- Add all 18 §2.4 cases as parameterized cases, run once each zh/en (English card labels swapped to `label_en`).
- New invariant: for the same `(text, card)`, `numerics_audit.passed` returned by `chat_service` must equal the card-side final `status` (kill “harness ok, card-side reject”).
- `min` context still contains every row’s `value`.
- Every numeric string from `build_fact_card_context_block` ∈ W (self-consistent).

`scripts/pha_numerics_manifest_selfcheck.py`:

- At least one case per of the six fact-card policy rules; `t0_forgery_in_t1_block` one each zh/en; identifier mask one; `.0` / thousands-separator normalize one.
- All existing strict / t0_plus_disclosure cases unchanged (regression gate).

`scripts/pha_chat_turn_fsm_selfcheck.py`: `fact_card_interpret` slot order and registry `--write` unchanged is enough.

---

## 7. History cleanup (commit 8462695)

Unpushed, safe to rewrite. **Decision: `git commit --amend`**, fold the workspace revert in, message changed to describe reality:

```
Fact-card interpretation: dedicated profile, card manifest, locale rendering

- fact_card_interpret profile; Numerics Manifest built from the day's card
- USER_ASSESSMENT_PROMPT is the outline (TASK-level); no metric-id parsing
- locale-aware dates/labels, plain-text output, cache key with locale
- healthkit priority pack 1 (SpO2 / RR / VO2max / wrist temp), zip as truth
```

Do not keep “fails closed on off-focus numbers” in the message. After amend, `git log -1 --stat` should still be 46±9 files. If the maintainer does not want to rewrite history, make a new commit whose first line must be “Revert focus filtering from 8462695; outline lives in TASK”.

This document’s (P9.4) code changes are a **separate commit**, not merged with the above.

---

## 8. Doc change list (same PR as P9.4 code)

| File | What |
|---|---|
| `prd-pha-ios-proactive-agent-v1.md` | Already changed at this writing: FR-6.3 / FR-6.10 grading, §8 M1-P9.4, §11, §12 v1.10. After code lands, mark P9.4 DONE |
| `manifest-tier-v1.md` | After §3.2 add a subsection “fact_card policy” pointing at this document §2.3, declare clause-level P/E/M judgment and `educational_int` telemetry; add a row to the policy table |
| `pha-fact-card.md` | “Interpretation” row: audit = harness single audit (fact_card policy); no longer write “atom-number audit” |
| `harness-change-log.md` | Class P1 (audit): fact_card policy, lexicon extra keys, identifier mask, normalize; rollback |
| `pha-ios-proactive-change-log.md` | P9.4 land entry; failed-state copy change |
| `handoff-…-v2.md` §4.4 | Already added “replaced by v3” pointer |

---

## 9. Execution order (check in order; selfcheck green before the next step)

1. `git commit --amend` (§7); confirm `git status` clean.
2. `numerics_manifest.py`: normalize + identifier mask + `LANG_T0_CLAIM_MAP` extra keys + fact_card policy + `educational_ints`. Write `pha_numerics_manifest_selfcheck.py` cases first, then implement.
3. `build_fact_card_numerics_manifest`: register `.0` dual form, card times, window spoken numbers (delete `{"7","12"}`).
4. `fact_card_interpret.py`: audit function shrinks to delegate (§3.2), delete all literal regex; `rejected_text` into cache; `_INTERPRET_PROMPT_REV` becomes hash.
5. `harness_plan.py` TASK numbered + `{T1_TEMPLATE}` placeholder; `harness_tier0_assembly.py` fill by locale; `min` floor (§3.5); registry `--write`.
6. `fact_card_copy.py` fail copy merge/dedupe + two-failure hint, zh/en.
7. `pha_fact_card_selfcheck.py` switch to behavior cases (§6); three selfcheck suites all green.
8. Clear `data/fact_card_interpret/`; `bash scripts/pha_restart_accept.sh`; Mac browser + iPhone Safari each tap “Generate interpretation” once, once each zh/en; paste the four results (including `educational_ints`) into the change-log.
9. Docs (§8); commit.

---

## 10. Do not

- Do not have any metric name (`SpO2`, `VO2max`, `静息心率`) appear in any Python file as part of audit logic.
- Do not restore ≥100, ≤2 digits, 0.5–15 or similar magnitude/shape thresholds as allow conditions (decimal=S is the only shape rule, and it is a **tighten**, not an allow).
- Do not keep two number extractors; wipe the card side clean.
- Do not use the whole sentence as context judgment.
- Do not write the Chinese T1 template back into TASK source.
- Do not list this card’s metric names in TASK to make 7b pass.
- Do not auto-retry (P9.4b not decided).

---

## 11. Needs maintainer lock (defaults; execute defaults if no reply)

| # | Question | Default |
|---|---|---|
| 1 | 8462695 amend vs new commit | amend (unpushed) |
| 2 | Decimals always S (including “aim for 7.5 hours”) | yes |
| 3 | Is rule 5 “card label/unit + no educational word → reject” too strict | keep; watch `educational_ints` and on-device fail rate two weeks then revisit |
| 4 | P9.4b auto-repair round (on fail, feed violations back, call the model once more, show failed only if still fail) | do not; register §11, revisit before M3 |
| 5 | Failure records store original `rejected_text` | store (local data) |
| 6 | Focus drift (assessment names still recite SpO2/respiratory rate) | → [`handoff-2026-09-08-fact-card-interpret-v4-soul.md`](handoff-2026-09-08-fact-card-interpret-v4-soul.md) (M1-P9.5 dedicated soul) |
