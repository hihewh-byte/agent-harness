# Daily fact card · Mac + iPhone on the same Wi-Fi

> **Language / 语言**：English (this document) · [中文](pha-fact-card-lan.zh.md)

PHA is **not** a medical device and does **not** provide medical advice, diagnosis, or treatment. The card is a local daily snapshot of *your* wearable ledger.

This is the clone path for people who want the **iPhone card**, not the Mac chat box. Daily numbers use **no LLM**. Ollama is optional (the “Generate interpretation” button).

## Why this is easier than PHA chat

| | Fact card | PHA chat at `:8788` |
|---|---|---|
| Daily habit | Shortcut / lock-screen teaser → Safari card | Open a desktop page and type |
| First value | HealthKit samples + rule bands vs *your* baseline | Empty warehouse + a 4–5 GB model pull |
| Numbers | Written by Python; the model cannot invent them | Chat is evidence-gated, but you still wait on a reply |
| LLM | Only if you tap the button | Required for a useful reply |

You still need a Mac. The iPhone never talks to a project server — only to **your** machine on the LAN (or Tailscale).

## What you need

- A **Mac** running PHA (`PHA_HOST=0.0.0.0`)
- An **iPhone** with Health and Shortcuts
- **Same Wi-Fi** (iPhone on cellular cannot reach `*.local` / your LAN IP)
- Apple Watch optional, but that is where HRV / overnight sleep usually live
- Python 3.10+ (same as [README Quick Start](../README.md#5-minute-quick-start-pha-app))

Honest time: Mac ~5 minutes if you already cloned; first iPhone Health permissions 5–10 minutes; after that, automation.

## 1. Mac

```bash
git clone https://github.com/hihewh-byte/agent-harness.git
cd agent-harness
bash scripts/bootstrap.sh
source .venv/bin/activate
bash scripts/macos/setup_fact_card_lan.sh
python -m pha.main
```

Leave that last command running. The setup script:

- sets `PHA_HOST=0.0.0.0` so the phone can connect (default `127.0.0.1` is Mac-only)
- creates `PHA_INGEST_TOKEN` in gitignored `.env` if missing
- optionally signs a **personal** `pha-daily.shortcut` into `data/local_shortcuts/` (gitignored — it contains your token; do not copy it to git)

If PHA was already listening on `127.0.0.1`, restart so the new bind takes effect:

```bash
bash scripts/pha_restart_accept.sh
```

Do **not** forward port `8788` to the public internet.

## 2. iPhone (same Wi-Fi)

One Shortcut: **PHA Daily** (sleep + HealthKit pack + open the card). One automation.

**Clone path (no secrets in the file):**

1. iPhone **Settings → Shortcuts → Advanced → Allow Untrusted Shortcuts**
2. **Settings → Privacy & Security → Local Network → Shortcuts = ON**
3. Download [`shortcuts/pha-daily.shortcut`](../shortcuts/pha-daily.shortcut). Import asks for:
   - Mac URL: `http://YourComputer.local:8788` or `http://<LAN-IP>:8788` — **not** `127.0.0.1`
   - Token: `PHA_INGEST_TOKEN` from the Mac `.env` (print length only; do not paste it into git or a post)
4. Run **PHA Daily** once. Tap **Allow Access** for every Health Find.
5. **Shortcuts → Automation → Time of Day → PHA Daily → Run Immediately**. Background runs can miss; the ledger `as_of` date is the source of truth.

Safari should open the full card. Until HealthKit lands, the top of the page is a setup checklist; then you get numbers and a three-band glance (easier / similar / favorable vs *you*, not a 0–10 score).

**Already ran the Mac setup script?** AirDrop gitignored `data/local_shortcuts/pha-daily.shortcut` instead — URL and token are already filled. Do not upload that file.

Lock-screen banners are teasers. iOS will not open a custom URL from a stock notification. Re-run **PHA Daily** (or wait for the M2 app) to open the page.

## 3. If Safari cannot connect

- iPhone is on **Wi-Fi**, not cellular; Mac is awake and `python -m pha.main` is running
- macOS Firewall allowed Python / the PHA process
- `.local` often dies on guest / client-isolation Wi-Fi or after DHCP. Put the LAN IP in the Shortcut’s **PHA Base** text (or re-import and answer the URL question again):

```bash
PHA_INGEST_URL_HOST=192.168.x.x bash scripts/macos/setup_fact_card_lan.sh
```

- Optional later: Tailscale on both devices, then `PHA_INGEST_URL_HOST=<tailscale-name-or-ip>`

Maintainer contract (JSON, units, fail-closed ingest): [healthkit-ingest.md](healthkit-ingest.en.md) ([中文](healthkit-ingest.md)). Card JSON / prefs: [pha-fact-card.md](pha-fact-card.en.md) ([中文](pha-fact-card.md)).

## What you will not get from clone alone

- A public URL or App Store binary
- Your Mac address or ingest token inside the GitHub Shortcut (the template asks for those on import)
- Garmin / CGM vendor connectors in this version
- A substitute for Apple Health or a physician
