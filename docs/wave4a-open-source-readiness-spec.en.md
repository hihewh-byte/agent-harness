# Wave 4a — Open Source Readiness Spec v1.0

> **Language / 语言**：English (this document) · [中文](wave4a-open-source-readiness-spec.md)

> **Filename**: `docs/wave4a-open-source-readiness-spec.md`  
> **Version**: v1.0 (2026-07-05)  
> **Status**: ✅ **Ratified (B-tier spec open-source release · Path-B)**  
> **Governing docs**: [`pha-pm-constitution.md`](pha-pm-constitution.md) · [`CONTRIBUTING.md`](../CONTRIBUTING.md) · [`SECURITY.md`](../SECURITY.md)

---

## 1. Non-goals

- **Not** medical-device registration or a clinical decision support system (CDSS)
- **Not** a multi-tenant SaaS first release (see [`rfcs/rfc-enterprise-multi-tenant.md`](rfcs/rfc-enterprise-multi-tenant.md) Future Work)
- **Not** a third-party hardware vendor integration implementation (see [`rfcs/rfc-device-ingestion-adapter.md`](rfcs/rfc-device-ingestion-adapter.md) Future Work)

---

## 2. Open-source product boundary (personal C-end)

| Dimension | Ruling |
|------|------|
| **Deploy model** | Single-machine local-first (macOS / Docker); data does not leave the machine by default |
| **Network bind** | Default `PHA_HOST=127.0.0.1`; **forbidden** to expose 8788 to the public internet without a Gateway |
| **Auth** | Personal edition has **no** HTTP auth; `user_id` comes from Query/Form and trusts the local operator |
| **LLM** | Default local Ollama; optional BYOK cloud (user configures their own Key) |
| **Medical positioning** | Personal health tracking and evidence-citing assistant; **not** diagnosis / treatment / prescription |

### 2.1 Medical disclaimer (required in the release)

Repo-root [`README.md`](../README.md) and all user-facing install docs **must** include:

> PHA is **not** a medical device and does **not** provide medical advice, diagnosis, or treatment. Outputs are for personal wellness tracking only.

---

## 3. PII defense audit standard (Release hard red line)

### 3.1 Always allowed in Git

- Synthetic fixtures (`tests/fixtures/**`) — dates must be obvious demo values (e.g. 2099-01-01) or anonymized
- Offline selfcheck expectation matrices (`expectations_v1.json`, etc.)
- Architecture / RFC / Harness docs

### 3.2 Never allowed in Git

| Path / type | Reason |
|-------------|------|
| `data/` · `*.db` | User SQLite ledger |
| `storage/users/` · `storage/attachments/` | User-uploaded originals |
| `reports/chb/**/brief_*.json` | CHB compile artifacts, containing T0 lab/wearable values |
| `reports/p1_golden/` | On-device E2E run reports |
| `.env` | Secrets and environment |
| Apple Health `export.zip` · on-device screenshots · lab PDFs | Raw PHI/PII |

### 3.3 Release Audit Checklist (maintainer must run before first public)

- [ ] `git grep -i` has no real names, ID numbers, phone numbers, or real lab-date clusters (e.g. personal historic report days)
- [ ] `.gitignore` covers all §3.2 paths
- [ ] `reports/chb/**/brief_*.json` removed from the index; keep only [`tests/fixtures/chb/`](../tests/fixtures/chb/)
- [ ] **If the repo ever privately pushed PII**: run `git filter-repo` / BFG to purge history before first public (see §3.4)
- [ ] `bash scripts/run_selfchecks.sh` Exit 0
- [ ] `python scripts/doctor.py --quick` has no blockers (Ollama offline may WARN)
- [ ] README Quick Start can complete cold clone → 8788 reachable

### 3.4 Git history PII purge (one-shot)

Deleting a file from the index **is not** purging history. If `brief_*.json` or `export.zip` ever entered any commit, the maintainer **must** rewrite history **before the first public push**, for example:

```bash
# Example — adjust to the actual leaked paths
git filter-repo --path reports/chb/ --invert-paths --force
```

Afterward force-push **only** to a remote that is not yet public; a already-public repo needs a key-rotation and disclosure assessment.

---

## 4. Release subtree and engineering gates

### 4.1 Open-source engineering assets already delivered

| Asset | Path | Status |
|------|------|------|
| LICENSE | `LICENSE` (Apache-2.0) | ✅ |
| README | `README.md` (English) | ✅ |
| CONTRIBUTING | `CONTRIBUTING.md` | ✅ |
| SECURITY | `SECURITY.md` | ✅ |
| INSTALL | `docs/INSTALL.md` | ✅ |
| Doctor | `scripts/doctor.py` | ✅ |
| Offline selfcheck | `scripts/run_selfchecks.sh` + manifest | ✅ |
| PR CI | `.github/workflows/ci.yml` | ✅ |
| Nightly (non-blocking) | `.github/workflows/nightly-harness.yml` | ✅ |
| Docker | `docker compose` | ✅ |

### 4.2 CI layers (Stage 4-0 · non-regressible)

| Layer | Entry | PR blocking |
|------|------|-------------|
| L0 | `run_selfchecks.sh` offline manifest | ✅ |
| L1 | universal attachment lane probe | ✅ |
| L2 | 148/164 LLM batteries · P1 tier H · on-device pixels | ❌ Nightly / Maintainer |

**Forbidden** to hang P1 HTTP / on-device E2E on the PR manifest “to look good for open source”.

---

## 5. Version and tag policy

| Concept | Convention |
|------|------|
| **build_marker** | `pha/build_marker.py` — runtime behavior version (e.g. `pha-v2.3.32-full-import-only`) |
| **Git tag (open source)** | SemVer release: `v0.4.0-beta` (2026-07-05 open-source readiness) |
| **Public Gate** | Wave 4a checklist all green + C-1/C-2 gold (maintainer local / Nightly, not PR CI) |

---

## 6. §X. SOTA benchmarking

| Benchmark | PHA personal OSS edition adopts | Deliberately not |
|------|-------------------|----------|
| **Local-first** (Immich, Home Assistant) | Data in local SQLite; default localhost | Cloud sync account system |
| **FHIR SMART** | Evidence chain `[ref:…]` · T0 columns | First-release FHIR Server |
| **Ollama / llama.cpp** | Local LLM default path | Bundled cloud API Key |
| **GitHub OSS hygiene** | LICENSE · CI · SECURITY · CONTRIBUTING | Committing user health exports as demos |

---

## 7. Future Work (Enterprise · not in personal first release)

| RFC | Use |
|-----|------|
| [`rfcs/rfc-device-ingestion-adapter.md`](rfcs/rfc-device-ingestion-adapter.md) | Universal heterogeneous-device Ingest Adapter · two-layer label jurisprudence |
| [`rfcs/rfc-enterprise-multi-tenant.md`](rfcs/rfc-enterprise-multi-tenant.md) | B-end Gateway · composite user_id · RBAC |

---

## 8. Acceptance (Wave 4a · Path-B)

- [x] PII paths in `.gitignore` + real `brief_*.json` removed from the index
- [x] Synthetic CHB fixture: `tests/fixtures/chb/synthetic_brief_demo.json`
- [x] This document v1.0 on disk
- [x] Universal Enterprise RFC dual docs on disk (W-13/W-14)
- [x] PR CI offline selfcheck green
- [x] README includes disclaimer + Future Work anchors
- [x] Dashboard UI default English + `PHA_UI_LANG` + top-bar en/zh toggle
- [x] First-release ops guide: [`GITHUB_PUBLISH.md`](GITHUB_PUBLISH.md)

---

## 9. Revision history

| Date | Notes |
|------|------|
| 2026-07-05 | v1.0 Path-B spec open-source release readiness; PII sterilization; Enterprise RFC parked |
