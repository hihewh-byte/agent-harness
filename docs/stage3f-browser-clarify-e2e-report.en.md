# Stage 3F Browser Clarify E2E Report

> **Language / 语言**：English (this document) · [中文](stage3f-browser-clarify-e2e-report.md)

> Time: 2026-06-24  
> Service: `http://127.0.0.1:8788`  
> Path: in-page `fetch('/api/chat')` (same stack as `app.js` `sendAsk` / `sendClarifyChoice`)  
> Model: `qwen2.5:7b-instruct`  
> Flags: `PHA_CLARIFY_TURNS=1` · `PHA_HEALTH_TURN_RESOLVER=1` · `PHA_GOAL_CLASSIFIER=1` · `PHA_CLARIFY_INTENT_SCOPE=1`

## Result: **PASS**

| Turn | Action | SSE events | Assertion |
|------|------|----------|------|
| R1 | “How are my lipids?” | `status` → `clarify` → `done` | `kind=lab_year`; choices include 2023/2025 |
| R2 | chip `2023` (`clarify_choice_id=2023`) | `delta`… → `done` | no `error`; answer includes 2023/2025 LDL compare |

- session: `f2dde1fc-2daa-4ce3-9632-4a35a6cb0f9a`
- R1 clarify prompt: “You have multi-year lipid / lab records (2023, 2025). Please specify the year to view.”

## Notes

- When automated click approval on the UI Send button is restricted, verification uses **same-origin fetch SSE** (same network path as `app.js`).
- API special `pha_e2e_clarify_multiturn_report.py` also **PASS** (after restart).
