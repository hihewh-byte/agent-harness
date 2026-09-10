# Stage 3A.2 — Session episodic focus + grounded rationale (RFC)

> **Language / 语言**：English (this document) · [中文](stage3a2-episodic-focus-and-grounded-rationale.md)

> **Baseline**: `pha-v2.3.3-stage3a1-attachment-qa-governance`  
> **Target build**: `pha-v2.3.3-stage3a2-episodic-focus-grounded`  
> **Status**: ✅ coded

## 0. Problem

| Symptom | Root cause |
|------|------|
| Turn 1 attachment Q&A is good | 3A.1 `attachment_asset_qa` + focused background |
| Turn 2 “why these benefits” becomes a plan log | No attachment → governance drops; falls to `supplement_manifest` + full `SUPPLEMENT_BG` |
| User wants “answers with evidence” | Missing a “≤3 checkable grounds” contract; turn 1 should emit this too |

**Memory-layer gap**: add **Layer 2.5 session episodic turn focus** between Layer 2 (background) and Layer 3 (chat history).

## 1. Memory and conflict constitution (summary)

### 1.1 Who guarantees long-term memory?

**PHA** assembles every turn; the **LLM** has no physical cross-turn memory. Dialog persists in `chat_sessions` / `chat_messages`; fragments in `user_health_background_notes`; labs live in the SQLite medical ledger.

### 1.2 Conflict priority (should · phased)

| Priority | Type | This-turn behavior |
|--------|------|----------|
| P0 | User explicit statement this turn | Answer follows it; may capture to background; **do not** silently rewrite lab tables |
| P1 | Structured labs / Manifest | Numeric iron evidence |
| P2 | Session focus asset | Beats full regimen background |
| P3 | background notes | Focused slice only + ≤3 preselected grounds |
| P4 | Chat history / RECALL | Keep anaphora; attachment turns **close cross-session RECALL** |

## 2. Mechanism

### 2.1 `chat_session_turn_focus` (SQLite)

| Field | Notes |
|------|------|
| `session_id` | Primary key |
| `focus_summary` | Attachment parse summary (≤2k) |
| `document_type` | e.g. `supplement_label` |
| `focus_tokens_json` | OCR structure tokens |
| `turns_remaining` | Default 3; decrement each consumed turn |

Write: after successful attachment parse or first-turn `attachment_asset_qa`.  
Read: follow-up turns (no new attachment) with TTL>0.

### 2.2 Routing

| Mode | Condition |
|------|------|
| `initial` | This turn has a parsed attachment + short-question intent (3A.1) |
| `followup` | Session focus valid + follow-up intent (why / how / caution…) + no explicit labs/HRV question |
| `none` | Other → ordinary pricing |

Profile is always `attachment_asset_qa`; `followup` uses dedicated TASK copy.

### 2.3 Output constitution (first turn + follow-up share)

1. **This-turn asset ledger**  
2. **In your situation (≤3 items)**: `【依据】… → 【推论】…` (may cite only the “citable grounds” block)  
3. **Cautions**  

Forbidden: whole-plan review, lipid / HRV textbook, reciting the full attachment summary.

### 2.4 Input trim

- `build_preselected_grounded_hits`: medication first + token match, **at most 3**
- `build_focused_background_for_attachment_qa`: focused fragment (same as 3A.1)
- Follow-up turns: `SUPPLEMENT_BG` injects **session focus summary** + the two blocks above
- **RECALL** is emptied on `attachment_asset_qa` turns (prevent cross-session plan pollution)

## 3. Environment variables

| Variable | Default |
|------|------|
| `PHA_SESSION_FOCUS_TTL_TURNS` | `3` |
| `PHA_GROUNDED_HITS_MAX` | `3` |
| `PHA_ATTACHMENT_QA_BG_MAX_CHARS` | `1400` |

## 4. Acceptance

- [ ] Attachment + “how does it help me” → `attachment_asset_qa` + answer contains “in your situation” ≤3 structure (needs live E2E)
- [ ] Same-session follow-up “why these benefits” → still `attachment_asset_qa` + **no** protein-powder / fixture-med log (needs live E2E)
- [x] `chat_session_turn_focus` has a row and `turns_remaining` decrements (`pha_stage3a2_selfcheck.py`)
- [x] `pha_stage3a2_selfcheck.py` passes

## 5. Follow-on

- **3A.2.1 (next coding pack)**: [response-layer UX + topic lock + temporal causality](stage3a2.1-response-ux-and-causal-anchor.en.md) — followup lexicon, lipid hard-cut, Soul jargon, ingest UI from three live turns
- **3A.3**: `user_declared_change` capture, background global rank, `regimen_dump_detected` telemetry
