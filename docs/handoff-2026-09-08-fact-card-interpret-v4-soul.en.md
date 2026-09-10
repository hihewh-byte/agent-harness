# Handoff · Fact-card interpretation focus drift: profile-dedicated soul (M1-P9.5)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-08-fact-card-interpret-v4-soul.md)

> For the successor coding agent · drafted 2026-09-08 22:45 · based on 9/8 22:26–22:29 three English API retests (`enR1–enR3`) vs zh-2/zh-3  
> First reply must output both lines:  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) v1.10 (FR-6.8 whole card is the evidence source / §8) · [`pha-pm-constitution.md`](pha-pm-constitution.md) (anti-hardcode, no patches for a specific case) · previous handoff [`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) (§4.3 “outline lives in TASK, do not parse metric ids” still holds; this document does not overturn it)  
> This document **is design only, no code**. The change surface is small (one constant, one branch, one hash input, three selfchecks); do not expand it.

---

## 0. Live state and start order

**git**: `main` is two commits ahead of `origin/main` (`95f8e5b`, `eafe393`), unpushed. Workspace is **dirty**: `pha/numerics_manifest.py`, `scripts/pha_numerics_manifest_selfcheck.py`, `docs/pha-ios-proactive-change-log.md`, `docs/harness-change-log.md` — this is M1-P9.4.1 (English yearless date mask, policy `v1.1`), retested passing but **not committed**.

Start order:

1. Commit P9.4.1 first, alone (message in §9); only after `git status` is clean touch anything in this document. Do not mix the two into one commit.
2. Read §1 evidence; reproduce once locally with the §1.3 method (see whether the first system-prompt message contains “三步看诊法”).
3. Do §3 → §4 → §5 in order; selfcheck green before the next step.

**Runtime**: PHA on `:8788`, build `pha-v2.3.32-full-import-only-p94`; ingest token in `~/Library/Application Support/pha/env-8788.sh`; restart with `bash scripts/pha_restart_accept.sh`. Current `data/fact_card_prefs.json` is zh-CN; assessment prompt original: `只看静息心率与HRV，VO2Max。用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度的建议`. After tests **must restore as-is**.

---

## 1. Problem and root cause

### 1.1 Observed

Assessment names “only look at RHR / HRV / VO2max”; the card also has active_energy / respiratory_rate / spo2 checked. Same model `qwen2.5:7b-instruct`:

| Round | Locale | Audit | Mentions SpO2 / respiratory rate | Section headings |
|---|---|---|---|---|
| zh-2 | zh-CN | pass | no (drifted to “sleep”) | none |
| zh-3 | zh-CN | pass | no | none |
| enR1 | en-US | pass | **yes** | `Trend review / Related markers / Recommendations` |
| enR2 | en-US | pass | **yes** | same |
| enR3 | en-US | pass | **yes** | same |

Numerics audit all passed (those numbers are on the card), so this is not an audit problem; the **outline was overwritten**.

### 1.2 Root cause (code evidence)

The three headings match `pha/chat_message_stack.py` `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` “三步看诊法” (lines 43–52) character-for-character. Step two original:

> 【相关指标对照（Related Markers）】：可横向对照当轮证据中的相关穿戴/化验指标……

And `pha/chat_turn_slots.py` lines 557–570 pick soul by profile:

- `is_attachment_qa_profile` → `PHA_ATTACHMENT_SOUL_MINIMAL` (plain “no three-step clinical review structure”)
- `is_wearable_screenshot_profile` → `PHA_WEARABLE_SOUL_MINIMAL` (plain “do not use the three-step clinical review headings”)
- **everything else (including `fact_card_interpret`) → `else` → full medical soul**

`fact_card_interpret` TASK says "If it names metrics, discuss only those rows", but TASK is a Tier0 supplement layer; soul sits above it. The model is **obeying** the higher-layer instruction “must cross-compare other metrics”. zh and en eat the same soul; the mechanism exists on both sides; Chinese samples are fewer and zh-2 also drifted, so “Chinese does not drift” is false, only lower probability.

### 1.3 Reproduction (do not check into the repo)

In `/tmp` with Python, go through the `chat_turn_slots` entry that builds slots for `fact_card_interpret` (`plan.profile == "fact_card_interpret"`, `authoritative_profile` same name), take `chat_messages[0]["content"]`, `grep` `三步看诊法` / `Related Markers`. Should hit; after §3 should be empty.

---

## 2. Design principles (judge first, then change)

1. **Reuse the existing pattern**: picking soul by profile is already a `chat_turn_slots` mechanism (two profiles use it). This document only lets a third profile join; it is not a new mechanism.
2. **TASK is the only outline**: soul only sets role and red lines, not structure. No “write this first then that” language enters soul.
3. **Zero metric parse, zero audit change**: do not parse the assessment prompt, do not reject by label, do not change `numerics_manifest`, do not change FR-6.10. Focus is a style/outline problem; fail-closed is only for invention.
4. **Change one variable at a time**: this round **does not change TASK text**. Measure soul’s effect alone first (§5); if not enough, go to §6.
5. **Anti-hardcode**: soul text must not contain any metric name, unit, card field name, T1 template literal, or Chinese or English reply template. Language is left to the `RESPONSE LANGUAGE` instruction (`response_language.py`), same as the other two minimal souls.

### 2.1 Rejected options (do not raise again)

| Option | Why rejected |
|---|---|
| Posterior reject/retry by card labels | Would parse free-text assessment into metric ids, exactly the alias match P9.3 withdrew; and it would reject real numbers on the card — fail-closed used in the wrong place |
| Only strengthen TASK wording | Fighting soul’s forced structure from a lower slot; ineffective on 7b; treats the symptom |
| Pin named metrics at the top of context | Also requires parsing named metrics |
| Change `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` itself | Affects all chat profiles, out of scope |

---

## 3. Change detail

### 3.1 New constant `PHA_FACT_CARD_SOUL_MINIMAL` — `pha/harness_plan.py`

Place next to `FACT_CARD_INTERPRET_USER_MESSAGE` / `_FACT_CARD_INTERPRET_TASK` (that file already owns fact_card_interpret constants; `chat_turn_slots` and `fact_card_interpret` already import it). Add to `__all__` if present.

**Content requirements** (write in English, style aligned with `PHA_WEARABLE_SOUL_MINIMAL`, ≤ 600 characters):

- `Role:` one sentence: PHA personal health assistant; this turn **only** interprets today’s fact card per TASK.
- `Rules:` itemized:
  1. Language follows the `RESPONSE LANGUAGE` instruction; natural tone.
  2. **Must not** use the three-step clinical review structure or its headings in any language (do not list metric names besides the heading names being forbidden; like wearable soul, heading names may be cited as forbidden); **must not** invent a “related markers / related markers” cross-compare section — outline comes only from TASK and USER_ASSESSMENT_PROMPT.
  3. Numbers and dates only from this turn’s injected FACT_CARD_CONTEXT / Numerics Manifest; do not take numbers from Patient State, snapshots, or memory (those slots are already forbidden this turn; the sentence is for the model).
  4. Educational, non-diagnostic; no prescription, no dose.
  5. Plain text, no Markdown.
  6. Do not expose internal terms (Tier0, Manifest, metric_id, ledger, verdict, etc.).
  7. Do not repeat the disclaimer (the page already has it).

**Must not appear**: any metric name/abbrev (`HRV`, `SpO2`, `静息心率`…), units, card field names, `【参考标准` / `[Reference Standard`, Chinese sentences. Selfcheck will lock these (§4).

### 3.2 Soul-select branch — `pha/chat_turn_slots.py` lines 557–570

Extract the existing `if / elif / else` chain into a pure function (suggested name `select_soul_base(profile: str, qtype) -> Optional[str]`, same file); behavior for other profiles **character-for-character unchanged**; add one:

```
attachment → PHA_ATTACHMENT_SOUL_MINIMAL
wearable_screenshot → PHA_WEARABLE_SOUL_MINIMAL
profile == "fact_card_interpret" → PHA_FACT_CARD_SOUL_MINIMAL      ← new
qtype == CASUAL → PHA_MEDICAL_SOUL_LITE_SYSTEM_PROMPT
else → None (keep full medical soul)
```

Judge with `plan.profile == "fact_card_interpret"`, same as existing writes at lines 274/279/321/394 of that file; do not invent fuzzy prefix match like `is_fact_card_profile`.

Downstream of `ctx.soul_base` (lines 570, 573, 606, and `chat_turn_orchestrator.py:689`) needs no change: they already consume `soul_base`.

### 3.3 Cache key — `pha/fact_card_interpret.py::_interpret_prompt_rev`

Currently hashes `TASK(en) | FACT_CARD_AUDIT_POLICY_REV`. Add soul text: `TASK(en) | POLICY_REV | PHA_FACT_CARD_SOUL_MINIMAL`. Soul change then auto-misses old interpretations; no hand-clear of cache; also a §4 assertion.

### 3.4 `pha/harness_report.py:740` (optional, consistency)

That site unconditionally uses `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` to assemble the system prompt. First confirm whether `fact_card_interpret` goes through this path (it is report/replay assembly). If it does, call `select_soul_base` the same way; if not, do not change, only note in the change-log “report path still uses full soul, inconsistent with the online path, to be unified”. Do not expand the change for this.

### 3.5 What not to change

- `_FACT_CARD_INTERPRET_TASK` text (this round frozen, see §2 item 4).
- `harness_tier0_assembly` slot order, `harness_profile_registry` slot invariants (soul is not a slot; `--write` artifact should have no diff).
- `numerics_manifest.py`, `fact_card_copy.py`, HTML/API.
- `strip_markdown_markers` (headings disappearing should come from soul itself, not post-processing).

---

## 4. Selfcheck (write cases first, then implement)

### 4.1 `scripts/pha_fact_card_selfcheck.py`

Near existing TASK assertions (about lines 1104–1112) add:

1. **Soul routing**: `select_soul_base("fact_card_interpret", <non-CASUAL qtype>)` returns an object `is PHA_FACT_CARD_SOUL_MINIMAL`; `select_soul_base("wearable_screenshot_review", …)` and `select_soul_base("attachment_asset_qa", …)` return values identical to before (regression gate); any other profile returns `None`.
2. **System prompt has no three-step**: use the §1.3 entry to take `chat_messages[0]["content"]`, assert it does not contain `三步看诊法`, `纵向趋势对账`, `Related Markers`, `Trend review`, and does contain soul’s first `Role:` sentence. If the slot-build entry depends on external services and is inconvenient in selfcheck, fall back to only tests 1 and 3, and note in the change-log.
3. **Soul source anti-hardcode**: `PHA_FACT_CARD_SOUL_MINIMAL` contains no `resting_heart_rate` / `静息心率` / `HRV` / `SpO2` / `VO2` / `【参考标准` / `[Reference Standard`, and no CJK (`re.search(r"[\u4e00-\u9fff]")` is None).
4. **Cache key invalidates with soul**: record `_interpret_prompt_rev()`; `monkeypatch` that constant to another string and take again, they differ; after restore they match.

### 4.2 `scripts/pha_chat_turn_fsm_selfcheck.py` and registry

`fact_card_interpret` slot order unchanged; `harness_profile_registry --write` no diff. Proof that “soul is not a slot”.

### 4.3 `scripts/pha_numerics_manifest_selfcheck.py`

Do not change; run once all green (confirm §0 step 1 P9.4.1 is in the tree).

---

## 5. Runtime acceptance (required after the change; paste results into the change-log)

1. Clear `data/fact_card_interpret/`; `bash scripts/pha_restart_accept.sh`; `/health` should show the new build number (build_marker increments by convention).
2. **English 3 rounds**: `save_fact_card_locale('default','en-US')`, assessment prompt the exact same sentence as enR1–R3: `Only resting heart rate, HRV, and VO2max. In one or two paragraphs, explain what these numbers mean for today's training — e.g. workout type and intensity.`; each round delete cache first then `POST /proactive/fact-card/interpret`, poll `GET` until `done|failed`.
3. **Chinese 3 rounds**: restore zh-CN and the §0 Chinese original, same method.
4. Per-round record (script in `/tmp`, not in the repo): `status`, `policy_rev`, whether body contains `Trend review|Related markers|Recommendations|纵向趋势对账|多指标横向联动|其他相关指标`, whether SpO2/respiratory rate (`SpO2|blood oxygen|96\.0|respiratory rate|血氧|呼吸率`), whether “睡眠/sleep”, whether RHR/HRV/VO2max mentioned, whether English has CJK leak.
5. **Pass line**: 6/6 audit pass; three headings **0/6**; SpO2/respiratory drift **English ≤ 1/3, Chinese 0/3**; RHR and HRV **6/6** mentioned. VO2max miss is another known issue (model sporadic); record only, not this round’s bar.
6. If pass: write change-log, go §7. If not (headings gone but still recites other metrics ≥ 2/3): go §6; **do not** change audit, **do not** add label filtering.
7. Finally restore prefs to zh-CN + Chinese original; `cat data/fact_card_prefs.json` to verify.

---

## 6. Step two (only if §5 did not pass)

At the end of `_FACT_CARD_INTERPRET_TASK` item 1 add **one sentence**: do not start a paragraph or sentence for rows the user did not name. Requirement: no metric names; same English sentence for zh and en (TASK is already English). Cache key auto-invalidates with the TASK hash. After the change, repeat §5 items 2–5. If still not pass, stop and write the change-log, wait for maintainer lock (candidates: larger model, or UI checkbox “focus metrics” as structured input — the latter needs a PRD change, out of this document’s scope).

---

## 7. Doc change list

| File | What |
|---|---|
| `prd-pha-ios-proactive-agent-v1.md` | §8 add **M1-P9.5** “interpretation-dedicated soul (focus drift)”, status DONE after acceptance; §11/§12 version +0.1 by convention; FR-6 text unchanged, only note on FR-6.8 “interpretation turn does not use three-step clinical review” |
| `pha-ios-proactive-change-log.md` | New entry: class P1 (interpretation outline); root cause (soul three-step item 2); change (constant + branch + cache key); evidence (§5 six-round table); rollback (delete the fact_card branch in `select_soul_base`; cache key auto-invalidates) |
| `harness-change-log.md` | Soul select extracted to a function; fact_card_interpret uses minimal soul; whether `harness_report.py:740` was unified |
| `handoff-…-v3-numerics.md` | Append a row at the end of §11 table pointing here (“focus drift → v4”) |

---

## 8. Do not

- Do not parse metric names in the assessment prompt; do not reject or retry by label.
- Do not change `numerics_manifest.py`, FR-6.10, or any audit logic.
- Do not change `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` or the other two minimal souls.
- Do not write metric names, units, T1 templates, Chinese sentences, or output structure into soul.
- Do not change soul and TASK in the same commit (§2 item 4).
- Do not put `/tmp` scoring scripts or regex into the repo.
- Do not permanently change `data/fact_card_prefs.json`.

---

## 9. Commit plan

- **commit A (do first, P9.4.1, current dirty workspace)**:  
  `Fact-card audit: yearless EN/CN month-day dates resolve to card dates (policy v1.1)`  
  Body two lines: `_extract_fact_card_dates` + surface-form masks; selfcheck `FC-en-yearless-ok/bad`.
- **commit B (this document, P9.5)**:  
  `Fact-card interpretation: dedicated minimal soul; no three-step review structure`  
  Body: `select_soul_base` extracted; `PHA_FACT_CARD_SOUL_MINIMAL`; cache key includes soul; selfchecks; docs.
- If §6 was taken: **commit C** alone: `Fact-card TASK: no sections for unnamed rows`.

None of the three commits is pushed; the maintainer pushes.

---

## 10. Needs maintainer lock (defaults; execute defaults if no reply)

| # | Question | Default |
|---|---|---|
| 1 | Soul constant in `harness_plan.py` vs new `fact_card_harness.py` | `harness_plan.py` (constants already gather there; one fewer file) |
| 2 | Unify `harness_report.py:740` this round | Only if the fact_card path goes through it; else note as change-log TODO |
| 3 | Is §5 pass line “English ≤ 1/3” too loose | keep; tighten from telemetry after two weeks on-device |
| 4 | If §6 triggers, may it be done immediately | yes, but a separate commit and a separate change-log entry |
| 5 | After §6 still occasional sleep/VO2 miss (≤1/3) | stop; candidates: larger model, or UI “focus metrics” structured checkboxes (must change PRD) |
