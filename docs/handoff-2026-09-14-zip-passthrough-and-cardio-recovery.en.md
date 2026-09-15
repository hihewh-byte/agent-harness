# Handoff · 2026-09-14 · zip Record passthrough + Cardio Recovery promotion

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-14-zip-passthrough-and-cardio-recovery.md)

> For the next coding agent · **P21a/P21b coded; P21c not started**  
> Maintainer 2026-09-14 agreed the order: ledger first stores all zip Records as-is → registry promotion → catalog aliases → only then Loop A.  
> Field: query “Cardio recovery in the wearable store” → no rows; model **substituted** HRV 37.6 / VO2max 51.5 (violates FR-6.13).

**Status: M1-P21a DONE (including chat read path v1.27) · M1-P21b DONE (fixture samples) · P21c TODO.** Live ledger still has no recovery rows until zip re-import. Prefs / Find device_verified / ingest POST keys untouched.

---

## 0. One line

The zip allowlist is a historical importer implementation, not a Loop contract. Unknown HK `Record`s must land in `wearable_data` **as-is**; chat and the fact card must fail-closed until the metric is **registered**. Cardio Recovery must not be invented by a Loop approval. Loop A only aliases a catalog metric that **already exists**.

---

## 1. Disk (checked 2026-09-14)

| Layer | Fact |
|-------|------|
| Health app | Browse → Heart → **Cardio Recovery** (zh often **有氧恢复**); older name Heart Rate Recovery |
| HealthKit / zip XML | `HKQuantityTypeIdentifierHeartRateRecoveryOneMinute` (bpm drop one minute after exercise; positive) |
| Zip import | `pha/data_importer.py` `_SUPPORTED_RECORD_TYPES`; other `Record@type` never reach `_consume_record` |
| Ingest / Shortcut | Not in FR-1.4 or `shortcut_health_find_catalog.json`; Find label **not** copied from device |
| Registry | No `cardio_recovery*` / `heart_rate_recovery*` |
| Intent Catalog | No metric key; Loop A human review **rejects unknown metric** |
| Live ledger | No `*recover*` / `HeartRateRecovery` rows in `wearable_data` |
| Chat | Missing row then speculated via HRV/VO2max — **not** an acceptance gold |

Types already on the allowlist keep the typed path. P21a must not double-write them.

---

## 2. Layers (do not collapse)

```text
L0  zip / ingest samples     →  P21a as-is wearable_data
L1  daily + Registry         →  P21b metric_id / temporal / baseline / fact card
L2  catalog named fetch      →  registered: daily; unregistered: unique L0 hit → this-turn Manifest
L3  Loop A aliases           →  attach to existing catalog key only; never edit registry / importer
```

Named chat is **not** a promotion PR per question. Promotion is for daily columns, the fact card, Shortcuts, and Chinese aliases.

See [`wearable-metric-registry-v1.en.md`](wearable-metric-registry-v1.en.md) §2 and Loop SOP iron rule 5: **Loop does not change routing/registry**.

---

## 3. Task cards (status changes only when coding)

| ID | Do | Do not |
|----|----|--------|
| **M1-P21a** | Quantity `Record`s **not** on the typed branch → `wearable_data` with HK `type` string (value/unit/start/source/idempotent `sample_id`) | No auto daily columns; no `fact_card.eligible`; no prefs; no guessed Find labels; no weaker Numerics; no M2 |
| **M1-P21b** | Promote from real `HeartRateRecoveryOneMinute` rows: registry + daily rollup + catalog key; named chat fetches only that column | Empty registry row with no samples; population range without a sourced guideline; HRV/VO2max padding; causal claims |
| **M1-P21c** | After copying the Shortcuts Find literal on device: Find catalog + ingest alias + incremental Shortcut | Guessing Find from Health app title / SDK name |

**Order: a → b → c.** c may lag b; b must not be DONE without a samples. M1 fact-card rollup stays **DONE**. This slice is ledger completion, not a reopen of M1, not early M2.

---

## 4. P21a (passthrough)

- Goal: quantity `Record`s that appear in export.zip can be retrieved by type on the Mac ledger instead of being dropped.
- As-is = keep Apple `type`, `value`, `unit`, dates, `sourceName`; do **not** map unknown types onto HRV/RHR/VO2max at L0.
- Sleep analysis, already-typed quantities, and the existing Workout path keep current semantics.
- Unknown **Category** types (other than sleep) stay skipped until a separate card; this cut = `Record`s whose `value` parses as a finite float. Unparseable values skip that row (fail-closed).
- Importer: typed set → existing `_consume_record`; else parseable quantity → `add_sample(metric_type=HK_type_string, …)`.
- Store the **full** HK identifier as `metric_type`. No Python name tables.
- Do **not** mean/sum unregistered types into existing `wearable_daily` columns. P21a acceptance is `wearable_data` only.
- FR-1.8 overlay applies to passthrough rows on the same `xml_max` day. No second overlay.
- Volume: passthrough is **only** types outside the current typed set (heart rate is already typed). Log row counts / RSS; if a red line is hit, open a separate card — no business exception table.
- Chat while P21a-only: catalog first; unique unpromoted L0 hit → this-turn Manifest; miss → fail-closed; **no** HRV/VO2max stand-in. Chinese Health-app names that do not match HK-derived tokens fail-close.
- Fixtures: recovery Record lands; VO2max still typed; walking steadiness cited on named English ask; Chinese 步行稳定性 fail-closes; bad value writes nothing; re-import does not duplicate `sample_id`.
- FR-1.4 v1.27 documents the chat read path.

---

## 5. P21b (promotion)

Trigger: real `HKQuantityTypeIdentifierHeartRateRecoveryOneMinute` rows exist after P21a.

Suggested `metric_id`: `cardio_recovery_1min_bpm` (`label_en=Cardio Recovery`, `label_zh=有氧恢复`). Same-day rollup default **max**; `temporal` aligned to Health app presentation (do not guess). `fact_card.eligible` only after promotion; **do not** enable the checkbox in live prefs. No `reference_range` without a sourced guideline. New catalog key; **do not** cluster under `hrv` / `vo2max`. Correlational wording only.

Chat: hints/aliases for Cardio Recovery / 有氧恢复 / Heart Rate Recovery; `infer_wearable_metric_ids` returns only that id; card ⊆ scope; missing rows stated, not padded. Gold: before promotion, fail-closed with no stand-in digits; after, exclusive named recovery must not emit unnamed HRV/VO2max precise values.

---

## 6. P21c (Shortcut, deferrable)

Copy the Find picker literal on device → `device_verified`. Unverified = not in the Shortcut. Ingest aliases onto the same `metric_id`. Must not fight zip-as-final-truth (FR-1.8).

---

## 7. Loop A

Allowed: after the P21b catalog key exists, weekly harvest may propose spoken aliases onto that key; Path B local aliases after human approve. Forbidden: a live chat utterance creating `loopapr`; unknown-metric proposals; Loop PRs editing importer / registry / daily schema; runtime LLM self-heal; catalog auto-merge. While P21a is done and P21b is not, there must be **no** approval that “adds Cardio recovery to the allowlist”.

---

## 8. Coding start ack

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

Stack `CONSENSUS_ACK: stability-plan-v2026-06-10 read` if touching startup. Source of truth: this file + PRD v1.24 §8 / §11. On conflict: **numeric honesty and fail-closed win**.

---

## 9. Red lines

TurnEvidencePlan before LLM; user-visible digits ⊆ Manifest. No new Python phrase/metric/label/drug tables; no golden-sentence `if`. No must-cover / missing-row retry / prefs∩ / exclusive-scan / Data>Context flip. No weaker audit; no naked Ollama. No M2 / Watch App / APNs / cloud. This chat does not git unless the maintainer asks.

---

## 10. Rollback

Docs-only: drop this handoff, the three §8 rows, the §11 row, the change-log row; PRD back to v1.23. After code: P21a feature flag or restore the typed-set gate; P21b drop the registry row and daily-column migration (dry-run first).
