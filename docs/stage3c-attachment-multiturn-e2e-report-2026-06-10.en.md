# Stage 3C attachment multi-turn follow-up E2E special report

> **Language / 语言**：English (this document) · [中文](stage3c-attachment-multiturn-e2e-report-2026-06-10.md)

> Time: 2026-06-10 18:34:15 (UTC+8)
> Service: `http://127.0.0.1:8788` · build `pha-v2.3.32-full-import-only`
> Flag: `PHA_EPISODIC_ALL_PROFILES=1` · `PHA_HEALTH_TURN_RESOLVER=1`
> Model: `qwen2.5:7b-instruct`
> session_id: `94356a79-736b-42c1-a637-8e413418b9a8`
> Harness: `/tmp/pha-e2e-harness.jsonl` (fixed server-side path)

## Summary

| Scene | Turns | Functional result | Constitution red line | Routing quality |
|------|------|----------|----------|----------|
| A1-supplement label two images + 11 follow-ups | **12** | **PASS** (every turn answered) | **PASS** (`RECALL` slot not injected) | **WARN** (5 turns landed `wearable_screenshot_review`) |

Wall clock about **16.7 min** (R1 includes Vision parse 265s).

Attachments: `IMG_6800` (front) + `6801` (Facts) supplement-label images.

---

## Harness per-turn profile / turnScope (source of truth)

| Turn | User input (summary) | profile | attachmentQaMode | metricSource | bridge | RECALL∈forbidden | RECALL∈tier1 |
|------|------------------|---------|------------------|--------------|--------|------------------|--------------|
| R1 | supplement dual-Q + 2 images | `wearable_screenshot_review` ⚠ | — | default | — | ✗ | ✗ |
| R2 | which metrics can it raise? | `attachment_episodic_bridge` | — | default | — | ✓ | ✗ |
| R3 | any LDL improvement? | `attachment_asset_qa` | episodic_bridge | default | — | ✓ | ✗ |
| R4 | how is my recent HRV? | `wearable_screenshot_review` ⚠ | episodic_bridge | **focus** | ✓ | ✗ | ✗ |
| R5 | sleep, last month | `wearable_screenshot_review` ⚠ | episodic_bridge | **focus** | ✓ | ✗ | ✗ |
| R6 | compare with steps | `wearable_screenshot_review` | — | explicit | ✓ | ✗ | ✗ |
| R7 | continue | `attachment_episodic_bridge` | followup | **focus** | — | ✓ | ✗ |
| R8 | last year’s labs? | `attachment_episodic_bridge` | episodic_bridge | **focus** | — | ✓ | ✗ |
| R9 | what ingredients did that picture list? | `wearable_screenshot_review` ⚠ | followup | **focus** | ✓ | ✗ | ✗ |
| R10 | what did the uploaded attachment say? | `wearable_screenshot_review` ⚠ | — | default | ✓ | ✗ | ✗ |
| R11 | got it | `attachment_episodic_bridge` | — | default | — | ✓ | ✗ |
| R12 | thanks | `attachment_episodic_bridge` | followup | default | — | ✓ | ✗ |

Note: `recallFocusInjected=true` on every turn is the ledger anchor `RECALL_FOCUS` (RFC H-A3), distinct from the forbidden slot `RECALL`.

---

## Dialog-quality summary

**R1 (265s)** correctly identified Perin / NOW Foods two supplements; interpreted lecithin, choline, vitamin D, etc.

**R2–R3** kept the supplement focus; R3 stated “no direct LDL-improvement evidence” — matches evidence-bridge intent.

**R4–R5** switched to HRV/sleep; answers cited last-90-day wearable summary (HRV≈1.03, sleep trend).

**R6 (0.1s)** ⚠ fast fail: OCR/confidence insufficient, refused to invent steps — “please re-upload a complete screenshot”. This turn did not take long LLM reasoning.

**R7–R8** “continue” and “last year’s labs” expanded steps/HRV linkage and 2023 vs 2025 lab compare.

**R9–R10 (attachment recall probes)** could answer ingredients (lecithin, sophora, vitamin D), but R10 mixed in Apple Watch sleep advice (context drift).

**R11–R12** short closers still returned a supplement+lab combined summary, not pure small talk.

---

## Constitution red-line check (attachment lane)

| Check | Result | Notes |
|--------|------|------|
| Attachment profile `plan.forbidden` contains `RECALL` | **PASS** | R2/R3/R7/R8/R11/R12 six `attachment_*` profiles all contain it |
| tier1 does **not** inject `RECALL` / `RECALL_FOCUS` slots | **PASS** | 12 turns `recall_t1=false` |
| Attachment-recall questions do not inject `RECALL` slot | **PASS** | R9/R10 probes did not inject RECALL tier1 |
| `RECALL_FOCUS` ledger anchor | **INFO** | every turn `recallFocusInjected=true` (H-A3 expected) |
| Follow-up `metricSource=focus` | **PASS** | R4–R9 many turns hit focus |
| episodic `bridgeInjected` | **PASS** | R4–R6, R9–R10 true |
| R1 should be `attachment_asset_qa` | **WARN** | actual `wearable_screenshot_review` (two images may have been seized by wearable routing) |
| No cross-session RECALL relaxation | **PASS** | independently created session |

---

## Issues found

1. **R1 profile miss**: first dual-image supplement question landed `wearable_screenshot_review` instead of `attachment_asset_qa`; later episodic focus summary may mix wearable context.
2. **Wearable lane too sticky**: R4–R6, R9–R10 five turns landed `wearable_screenshot_review`; HRV/sleep/attachment-recall probes did not stably keep `attachment_episodic_bridge`.
3. **R6 fast fail**: steps compare triggered the low-confidence guard (0.1s), UX cliff; suggest reusing R1 supplement parse in-session instead of mistakenly reusing wearable OCR.
4. **R10 off-topic**: “what did the uploaded attachment say” should focus the supplement label, but emitted Apple Watch sleep advice.

---

## Conclusion

- **Function**: 12/12 turns returned a valid SSE answer (R6 is a guard short answer); special **function PASS**.
- **Constitution**: `RECALL` forbidden slot was not injected; attachment-recall probes did not break the red line; **constitution PASS**.
- **Routing quality**: attachment ↔ wearable profile switching is unstable; **quality WARN**. Suggest 3C-γ tighten catalog inheritance and R1 two-image supplement routing priority.

Repro:

```bash
cd agent-harness
PYTHONUNBUFFERED=1 .venv/bin/python scripts/pha_e2e_attachment_multiturn_report.py
```
