# Stage 3A.2.3 — Chat-window inline attachment preview (RFC)

> **Language / 语言**：English (this document) · [中文](stage3a2.3-chat-attachment-inline-preview.md)

> **Baseline**: `pha-v2.3.3-stage3a2.1-response-ux-causal-anchor`  
> **Target build**: `pha-v2.3.3-stage3a2.3-chat-attachment-inline-preview`  
> **Status**: 📋 pending Review  
> **Depends on**: [3A.2.1](stage3a2.1-response-ux-and-causal-anchor.en.md) · prefer Vision guard first, then preview ([3A.2.2](stage3a2.2-answer-quality-and-vision-guard.en.md))

---

## 0. Problem

Current chat-attachment flow:

1. Pick image → background upload + parse → “ready: filename” beside the input
2. After send, the user bubble is mostly **plain text** (or `[attachment] filename`)
3. **Chat history cannot show the image**, so users cannot form “this is the picture I asked about”

There is a clear UX gap vs ChatGPT / Claude / WeChat-style in-message images.

---

## 1. Goals and non-goals

### 1.1 Goals

| # | Goal |
|---|------|
| G1 | **At send** show a thumbnail (≤320px wide) in the user bubble + optional filename |
| G2 | **Refresh / history replay** still shows that turn’s attachment thumbnail |
| G3 | Click thumbnail → **original preview** (lightbox or new tab) |
| G4 | PDF shows icon + filename (no forced embedded render) |
| G5 | Auth: only the same `user_id` can access the matching `storage/attachments/{uid}/` |

### 1.2 Non-goals

- Repeat the image in the assistant bubble (optional P2)
- Image editing / 9-grid album
- Replacing the Vision parse path

---

## 2. Data model

### 2.1 Existing fields (reuse)

`chat_messages` already can store:

- `attachment_path` — server-relative or absolute safe path
- `attachment_name` — original filename
- `parsed_json` — parse summary (already exists)

### 2.2 Suggested additions (optional)

| Field | Notes |
|------|------|
| `attachment_mime` | `image/png` etc. |
| `attachment_thumb_path` | Server-generated 320w thumbnail path (less bandwidth) |

Thumbnails can be generated at `POST /api/chat/attachments` (Pillow).

---

## 3. API

### 3.1 Controlled download (must-do)

```
GET /api/chat/attachments/file?user_id={uid}&path={encoded_relative_path}&variant=thumb|original
```

- After resolve, `path` must sit under `storage/attachments/{uid}/`
- `Cache-Control: private, max-age=3600`
- Forbid directory traversal

### 3.2 History-message DTO extension

`GET /api/chat/sessions/{id}/messages` each user message adds:

```json
{
  "attachment_preview_url": "/api/chat/attachments/file?...&variant=thumb",
  "attachment_name": "IMG_6800.png"
}
```

Only when `attachment_path` is non-empty and mime is image/*.

---

## 4. Frontend UX

### 4.1 Before send (local preview · P0)

| State | UI |
|------|-----|
| `ready` | **Local ObjectURL thumbnail** above the input + “ready” |
| `parsing` | Thumbnail translucent + spinner |

Does not depend on the server for “picked the right image”.

### 4.2 After send (persistent preview · P0)

`appendChat` user branch:

```text
┌─────────────────────────┐
│ [thumb]  IMG_6800.png   │
│ What is this? How does it help me? │
└─────────────────────────┘
```

- Thumbnail `max-width: 240px; border-radius: 8px`
- Click → `window.open(preview_url)` or a light modal

### 4.3 Streaming assistant bubble

Unchanged; optional P2 small “attachment under discussion” image above the first assistant reply.

### 4.4 Relation to ingest button

Preview is **orthogonal** to “Save to health record”; lab-image preview + bottom confirm button can coexist.

---

## 5. Security and privacy

- All attachment URLs must carry **session or token** (once login exists); short-term `user_id` + path check (same as current prod) is OK.
- Response header `Content-Disposition: inline` for images only; PDF `attachment`.
- Logs must not print sensitive information in the full path other than UUID.

---

## 6. Implementation order

```text
P0  GET controlled-file API + user-bubble thumbnail (ObjectURL at send; preview_url for history)
P1  Server thumb generation + history-message DTO
P2  Lightbox + PDF icon
```

**Estimate**: P0 about 1–2 days frontend+backend; P1 thumbnail cache optional.

---

## 7. Acceptance

| id | Step | Pass |
|----|------|----------|
| E1 | Pick PNG → see local thumbnail before send | Matches the chosen file |
| E2 | After send, user bubble contains the image | Still there after refresh |
| E3 | Click to enlarge | Original is readable (PS 100mg distinguishable) |
| E4 | Guess path with another user_id | 403/404 |
| E5 | Supplement dialog | No “Save to health record” button (keep 3A.2.1) |

---

## 8. Relation to 3A.2.2

- **3A.2.2 first**: avoid “wrong image displayed convincingly”
- **Then 3A.2.3**: image is correct and visible — trust loop complete

---

*Drafted: Cursor · 2026-05*
