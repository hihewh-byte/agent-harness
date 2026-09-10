# Stage 3C-UX — Async attachment orchestrator spec

> **Language / 语言**：English (this document) · [中文](stage3c-async-attachment-orchestrator.md)

> **Version**: v0.1 (2026-05-26)  
> **Status**: 📋 Spec (pending code)  
> **Depends on**: 3B `LabelLedgerV1`, existing `/api/chat/attachments` · `/parse`  
> **Related**: [`stage3c-attachment-evidence-bridge-analysis.md`](stage3c-attachment-evidence-bridge-analysis.en.md)

---

## 1. Problem

Current UX makes the user wait for “attachment ready” before send. That does not match real chat habits. Root cause is a **sync contract**: send time must already have `attachment_parsed_parts`, otherwise a race yields single-image / empty ledger.

**Goal**: the user can **type the question and hit send first**; the system finishes perception in the background and **then automatically runs** that turn’s Harness.

---

## 2. User-visible behavior

| Moment | UI |
|------|-----|
| Pick images + type question + send | User bubble appears immediately; assistant area shows “received, parsing attachments (1/2)…” |
| Parsing | Input may disable or allow more typing (new messages queue, see §6) |
| Parse done + high confidence | Stream the answer |
| Parse done + low confidence | Fixed refusal / retake guidance (do not call L3 to guess ingredients) |
| Failure | Clear error + keep the user question for retry |

**Forbidden** copy: “please wait until the attachment is ready before sending”.

---

## 3. API contract (draft)

### 3.1 Create a “pending turn”

```http
POST /api/chat
{
  "user_id": "default",
  "message": "What is this? How does it help me?",
  "model": "qwen2.5:7b-instruct",
  "session_id": "...",
  "attachment_paths": ["...", "..."],
  "attachment_names": ["6800.png", "6801.png"],
  "wait_for_perception": true
}
```

| Field | Notes |
|------|------|
| `wait_for_perception` | `true` (default): server finishes perception inside SSE then builds Harness; client **need not** pre-call `/parse` |
| `attachment_parsed_parts` | Optional; if provided and complete, server may skip re-perception (**ignored by default for multi-image**, see 3B Week1) |

### 3.2 SSE event extensions

| event | Meaning |
|-------|------|
| `status` | `perception_stage`: `uploading` \| `ocr` \| `merging` \| `gate` |
| `status` | `perception_ready`: `{ parse_confidence, attachment_count, ingredient_row_count }` |
| `attach_error` | Perception failed; do not enter L3 |
| `delta` / `done` | Same as prod |

### 3.3 Optional: pure queue endpoint (P2)

```http
POST /api/chat/pending-turns
→ { pending_turn_id }
GET  /api/chat/pending-turns/{id}/stream
```

v1 can **keep one endpoint** and only lengthen the status stage inside `POST /api/chat`.

---

## 4. Server state machine

```text
RECEIVED
  → PERCEIVING (per path: ocr | vision_structured)
  → MERGING (layout-weighted)
  → GATING (G1–G6)
  → [low] DETERMINISTIC_REPLY
  → [high] HARNESS_ASSEMBLE → L3_STREAM
```

**Single worker serial** per `pending_turn_id`, to avoid dual-POST races.

---

## 5. Frontend contract

| Rule | Notes |
|------|------|
| Send | `attachment_paths` is enough to send; **do not** wait for `pendingAttachBundle.parsed` |
| Forbidden | `attachParseInFlight` blocking send (delete) |
| Allowed | Clear the picker UI after send to avoid double submit |
| Display | After `perception_ready`, show “merged N images · ledger M rows” |

---

## 6. Concurrency and queue

| Scene | Behavior |
|------|------|
| User sends another while parsing | **Option A (recommended)**: reject and prompt “previous attachment still parsing” |
| | **Option B (P2)**: enqueue the new message, run in order |
| Same session two images + text | Merge into one `pending_turn` |

---

## 7. Telemetry

| Field | Notes |
|------|------|
| `pending_turn_ms` | Send → perception_ready latency |
| `client_parse_skipped` | Whether client parse was skipped |
| `perception_stages[]` | ms per stage |

---

## 8. Acceptance

- [ ] User can type a question and send immediately after picking images
- [ ] Logs have no “POST /chat before parse complete” race
- [ ] Live two-image: Harness contains 2 `layout_hints_per_image`
- [ ] F2 E2E script does not depend on frontend pre-parse

---

## 9. Non-goals

- This spec does not fix OCR/Vision quality (see 3B-β · [`stage3c-vision-capability-matrix.md`](stage3c-vision-capability-matrix.en.md))
- Does not change `attachment_asset_qa` evidence scope (see [`stage3c-episodic-evidence-bridge.md`](stage3c-episodic-evidence-bridge.en.md))
