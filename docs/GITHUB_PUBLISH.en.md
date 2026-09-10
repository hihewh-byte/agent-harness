# Publish with GitHub Desktop (single repo · personal OSS)

> **Language / 语言**：English (this document) · [中文](GITHUB_PUBLISH.md)

> **Public repo**: `hihewh-byte/agent-harness` (Harness Core+Loop; PHA = reference app).  
> **Git root** = this checkout (`pha/`, `packages/`, `README.md`, `docker-compose.yml`). The local folder name may differ from the remote.  
> **Do not** add the parent `myAgents/` as the repository.

Upstream: [`wave4a-open-source-readiness-spec.md`](wave4a-open-source-readiness-spec.md) · [`CONTRIBUTING.md`](../CONTRIBUTING.md)

---

## 0. Pre-publish audit (maintainer)

```bash
cd agent-harness

# 1. PII history — empty output means no filter-repo
git log --all --full-history --oneline -- "**/brief_*.json"

# 2. Offline regression
bash scripts/run_selfchecks.sh

# 3. No local absolute paths staged (do not commit reports/loop/)
git status
```

| Check | Expect |
|-------|--------|
| `brief_*.json` history | **empty** (never committed) → skip `git filter-repo` |
| `reports/chb/**/brief_*.json` | gitignored · not in the tree |
| `data/` · `*.db` · `.env` | not in the tree |
| Default bind | `PHA_HOST=127.0.0.1` (see `.env.example`) |

### If history ever contained PII (rare)

```bash
brew install git-filter-repo
git filter-repo --path-match 'reports/chb/' --invert-paths --force
```

---

## 1. GitHub Desktop

1. **File → Add Local Repository…** → this checkout root (`pha/` and `packages/`).
2. Current branch; prefer **`main`** before a release (see §2).
3. **Changes**: stage release files; **do not** stage:
   - `.env` · `data/` · `*.db` · `reports/chb/**/brief_*.json` · `reports/loop/`
4. Example commit message:
   ```text
   chore(release): open source readiness v0.4.0-beta
   ```
5. **Repository → Create Tag…** → `v0.4.0-beta`
6. **Publish repository** (or Push origin) → suggested names **`personal-health-agent`** or **`pha`**

---

## 2. Branch

Dev may still be on `stage3c-alpha-health-turn-resolver`. First public:

```bash
git branch -M main
```

Or Desktop: **Branch → Rename…** → `main`, then Publish.

---

## 3. Fresh clone (optional CHB demo)

After clone there is **no** CHB artifact by default (harness slots stay empty, non-blocking):

```bash
mkdir -p reports/chb/default
cp tests/fixtures/chb/synthetic_brief_demo.json \
   reports/chb/default/brief_c209d632963d6a6f.json
```

After Apple Health data exists:

```bash
PYTHONPATH=. python3 scripts/pha_chb_compile_all_users.py
```

---

## 4. CI

- PR gate: `.github/workflows/ci.yml` → `bash scripts/run_selfchecks.sh`
- Nightly (non-blocking): `.github/workflows/nightly-harness.yml`

---

## 5. How to ship “PHA” vs “PHA framework”

| Asset | Suggestion | Note |
|-------|------------|------|
| **Harness + PHA reference** | ✅ **this repo** `agent-harness` | harness-core/loop + PHA reference · v0.4.0-beta |
| **Standalone PyPI** | ⏳ **not first ship** | still vendored; PyPI split is demand-driven |

**Conclusion**: ship **this single repo** first; do not wait for a framework split.

---

## 6. Can Cursor / an agent push for you?

**Not end-to-end**:

- Publish needs **your GitHub account** (Desktop login / PAT); the agent environment has no `gh` and no configured `origin`.
- An agent **can**: PII audit · docs · local `commit` + `tag` · this checklist.
- **You must**: GitHub Desktop **Publish repository** or `git push -u origin main --tags`.

---

## 7. After publish, check the website

- [ ] Root has `README.md` · `LICENSE` · `CONTRIBUTING.md` · `SECURITY.md`
- [ ] Releases has tag **`v0.4.0-beta`**
- [ ] No `brief_*.json` · no `.env` · no `export.zip`
- [ ] README has the medical disclaimer

---

## Revision

| Date | Note |
|------|------|
| 2026-07-05 | v0.4.0-beta Path-B first-ship guide |
