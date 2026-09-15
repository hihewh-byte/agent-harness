# Handoff · Cardio Recovery fact-card checkbox + zh aliases (v1.28)

> 2026-09-15 · Maintainer: finish this-slice M1 checkbox and Chinese aliases; do not guess P21c Find.

## Landed

- `data/fact_card_prefs.json` `users.default.enabled_metric_ids` includes `cardio_recovery_1min_bpm`. Registry `enabled_default` stays false.
- Catalog / `intent_hints` include 有氧恢复, 有氧恢复能力, 心肺恢复, 心率恢复, 一分钟心率恢复, 运动后心率恢复.
- Build: `pha-v2.3.52-cardio-card`. PRD v1.28.
- Regression: `python scripts/pha_p21b_cardio_recovery_selfcheck.py`

## Not opened

- **P21c**: Shortcut Find requires on-device copy; `shortcut_skip_reason=shortcuts_find_unverified`.
- **Walking steadiness**: English L0 ledger chat works; Chinese 步行稳定性 has no catalog key, so Loop A cannot attach it. Needs a separate promotion.

## Loop A boundary (this slice does not change Loop code)

Loop only aliases an **existing catalog key**. Unknown metric (no key) = human reject. On-Mac “Approve” writes `data/loop_local_aliases.json` and does not edit the repo catalog.
