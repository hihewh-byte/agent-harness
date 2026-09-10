# PHA Daily (public Shortcut template)

One iPhone Shortcut: sync last-night sleep + today’s HealthKit quantities, then open the fact card.

This folder is safe to clone. It does **not** contain a Mac hostname, LAN IP, or `PHA_INGEST_TOKEN`.

## Download

1. On the iPhone: **Settings → Shortcuts → Advanced → Allow Untrusted Shortcuts**.
2. Get [pha-daily.shortcut](pha-daily.shortcut) from this folder (GitHub → Raw, or clone and AirDrop).
3. Open it. Import asks for:
   - **Mac URL** — `http://YourComputer.local:8788` or `http://<LAN-IP>:8788` (not `127.0.0.1`)
   - **Token** — `PHA_INGEST_TOKEN` from the Mac `.env` (create it with `bash scripts/macos/setup_fact_card_lan.sh`)
4. Run **PHA Daily** once. Allow every Health Find.
5. **Shortcuts → Automation → Time of Day → PHA Daily → Run Immediately**.

The file is **unsigned on purpose**. Signing with `shortcuts sign` embeds an Apple ID in the binary; that must not land in git. After import, the token lives only on your phone.

Same-Wi-Fi handbook: [English](../docs/pha-fact-card-lan.md) · [中文](../docs/pha-fact-card-lan.zh.md)

## Regenerating

```bash
python scripts/macos/build_pha_ingest_shortcuts.py --public
```

The builder refuses to write if it finds this machine’s token, hostname, or LAN IP in the template. Do not copy anything from `data/local_shortcuts/` (gitignored, baked secrets) into this folder.

`pha-daily.plist` is the XML twin of the `.shortcut` for review.
