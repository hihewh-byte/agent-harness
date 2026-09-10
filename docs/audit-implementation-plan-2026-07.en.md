# Audit Implementation Plan 2026-07

> **Language / 语言**：English (this document) · [中文](audit-implementation-plan-2026-07.md)

> **This document is the single source of truth for execution.**
> Any coding agent (including human collaborators) must fully read this document and
> [`.cursor/rules/audit-plan-execution.mdc`](../.cursor/rules/audit-plan-execution.mdc) before executing the tasks below,
> and output the ack line in the first implementation reply / PR description:
> `CONSENSUS_ACK: audit-plan-2026-07 read`

- Source: 2026-07-14 whole-repo audit (main @ a5a36ab, 57/57 selfchecks PASS, composite 7.1/10)
- Finding IDs: F1 (α3 not merged) · F2 (harness_loop has no in-package tests) · F3 (Loop algorithms stuck in scripts/) · F4 (adoption funnel is zero) · F5 (giant modules / doc navigation)

---

## 0. Execution protocol (mandatory for every successor agent)

1. **Status is source of truth**: each task card has a `status` field (`TODO` / `IN_PROGRESS` / `DONE` / `BLOCKED`).
   Set it to `IN_PROGRESS` when starting; set `DONE` when finished and fill “completion record” (date + commit/PR id).
   **Status updates must land in the same PR as the code change**; verbal claims of done are forbidden.
2. **Order constraints**: do not start P1 until all P0 are `DONE`; P2 tasks may start only when their “trigger” field is met,
   otherwise do not do them (prevent premature investment). Same priority may run in parallel.
3. **Acceptance is a command**: each card’s DoD is an executable command + expected output. The PR description must paste actual run output.
   Command fail = task not done; do not merge.
4. **Do not expand scope**: do not do work the card does not list. New issues go into this document §4 “New findings register” as a new row,
   then a new task card through human review; no drive-by fixes.
5. **Existing gates are not waived**: this plan does not replace `pha-mandatory-reads.mdc` and similar rules;
   harness / startup changes still stack the corresponding `CONSENSUS_ACK` and update the corresponding changelog.
6. **No runtime self-heal red line** (inherited from protocol v0): no task may introduce online self-heal / auto-merge /
   catalog auto-write; Loop artifacts are always proposal-only + human-review PR.
7. **Push boundary**: the agent only commits locally; push and PR creation are done by the maintainer.
   After the local commit the agent must provide a complete PR write-up.

---

## 1. P0 — this week (close name vs reality)

### P0-1 · Merge the α3 branch (F1)

- Status: `DONE` (merging this PR completes it; DoD already measured on the rebased branch; output in the PR description)
- Goal: merge `feat/harness-loop-pipeline-extract` (808dfd2, harness-loop 0.1.0a3:
  portable harvest / candidates / pipeline / static promote) into main so main reality matches README / changelog.
- Steps:
  1. Maintainer pushes the branch and opens the PR (agent provides the PR write-up).
  2. Merge after CI all green; confirm with local `git pull`.
- DoD (run on main):

  ```bash
  harness-loop version                     # expected output contains 0.1.0a3
  ls packages/harness_loop/src/harness_loop/{harvest,candidates,pipeline}.py
  PYTHONPATH=. python scripts/pha_harness_loop_pipeline_selfcheck.py   # PASS
  bash scripts/run_selfchecks.sh           # ALL SELF CHECKS PASSED
  ```

- Completion record: 2026-07-14 · commit 3fe1eb0 (α3 rebased onto main 399618d; all four DoD items measured: `harness-loop version` = 0.1.0a3; three portable modules exist; pipeline selfcheck PASS; full selfcheck ALL PASS)

### P0-2 · Independent in-package tests for harness_loop (F2)

- Status: `DONE`
- Prerequisite: P0-1 DONE.
- Goal: establish pytest unit tests under `packages/harness_loop/tests/` so the package can self-prove without this repo.
  Sink selfcheck assertions for proposals / harvest / pipeline / eval_set into 6–10 cases:
  - `test_proposals.py`: legal/illegal proposal shape; `static_veto` intercepts
    `code_review_items_present`, `patch_outside_allowlist`, `tier_c_slot_promoted_to_catalog`.
  - `test_harvest.py`: `harvest_failed_turns_jsonl` only takes `passed: false`; dedupe; candidate row fields complete.
  - `test_pipeline.py`: stages run in order; `stop_on_error` aborts and notes mark no auto-merge.
  - `test_eval_set.py`: toy golden PASS path (no PHA domain).
- Constraint: tests must not import `pha.*` or `scripts/*`; fixtures live in-package `tests/fixtures/`.
- DoD:

  ```bash
  cd packages/harness_loop && python -m pytest tests/ -q    # all pass, ≥6 cases
  cd - && bash scripts/run_selfchecks.sh                    # still all green
  ```

  Also add a step in `.github/workflows/ci.yml`: `python -m pytest packages/harness_loop/tests -q`
  (and if harness_core tests are not in CI yet, add them in the same change), and update `docs/harness-change-log.md`.
- Completion record: 2026-07-14 · branch feat/harness-loop-package-tests (20 cases covering proposals/harvest/pipeline/eval_set; in-package fixtures; zero pha/scripts deps; CI adds Harness packages unit tests step including harness_core tests; DoD measured: in-package pytest 20 passed, full selfcheck ALL PASS)

---

## 2. P1 — two to four weeks (make “portable” real + get an external signal)

### P1-1 · Second extraction of Loop core algorithms (F3)

- Status: `DONE`
- Prerequisite: all P0 DONE.
- Goal: following the α3 pattern, move **domain-agnostic** parts of 1E gates and alias distill into
  `harness_loop`; PHA scripts degrade to “domain params + delegated call”.
- Split rules (must follow; if unsure, register in §4 first):
  - Movable: candidate dedupe / frequency stats, junk-heuristic **interface** (injectable predicate list),
    1E gate frame (gate order, verdict shape), proposal assembly.
  - Not movable: health-domain lexicons, OCR chrome word lists, PHA catalog paths, Chinese-segmentation specials —
    those stay as params / plugin callbacks in `scripts/` or `harness_loop/plugins/pha.py`.
- Suggested modules: `harness_loop/gates.py` (1E frame) + `harness_loop/distill.py` (frequency/dedupe/assembly).
- DoD:

  ```bash
  cd packages/harness_loop && python -m pytest tests/ -q    # new gates/distill cases pass
  cd - && bash scripts/run_selfchecks.sh                    # all green (including loop suite)
  git diff --stat main -- scripts/ | tail -1                # scripts/ net line count down
  ```

  Version to `0.1.0a4`, changelog recorded; `harness-loop harvest --plugin pha` behavior matches pre-migration
  (compare pre/post JSON field-by-field using `scripts/fixtures/loop_e2e_sample.jsonl`).
- Completion record: 2026-07-14 · branch feat/p1-1-loop-gates-distill (`harness_loop.gates` + `distill` moved into the package; `pha_loop_alias_distiller.py` 397→204 lines; in-package pytest 38 passed; full selfcheck ALL PASS; version 0.1.0a4)

### P1-2 · Actively get the first external builder (F4; human-led, agent-assisted)

- Status: `TODO` (transaction prep materials ready; invitation body and external feedback still missing)
- Prep: [`docs/p1-2-outreach-prep.md`](p1-2-outreach-prep.md) (Issue #1 status, invitee table, feedback register template; no High-tier invitation copy)
- Goal: at least 1 external developer fully runs the README “Builder? 10 seconds” block and leaves written feedback
  (Issue comment / DM OK, must be citable).
- Steps: maintainer invites 2–3 developers who build numerics-sensitive agents; agent drafts invitation copy,
  collates feedback, and turns feedback into §4 register rows.
- DoD: Issue #1 or a new Issue has **one substantial comment from a non-maintainer account**; feedback registered in §4.
- Completion record: (pending)

### P1-3 · Three-entry documentation navigation (F5)

- Status: `DONE`
- Goal: README top pins three paths, each pointing at a unique landing doc:
  1. **Use PHA** (personal health app) → existing quick start;
  2. **Attach Harness** (builder) → `docs/harness-builder-overview.md`;
  3. **Contribute Loop** → `examples/loop_reference_pha.md` + `CONTRIBUTING.md`.
- Constraint: add navigation only; do not rewrite bodies; do not add new docs (landings use existing docs; gaps go to §4).
- DoD: README top (first screen) has the three-entry block; all three links resolve in-repo
  (`python -c` or lychee checks relative paths exist).
- Completion record: 2026-07-14 · branch docs/p1-3-three-path-nav (README top adds Choose your path three entries; landing links all resolve; no new docs)

### P1-4 · Short threat-model note (audit security-dimension gap)

- Status: `DONE`
- Goal: add `docs/threat-model-v0.md` (1–2 pages), covering:
  trust-boundary diagram (online Core / offline Loop / human-review PR), Loop proposal attack surface
  (malicious JSONL poisoning → 1E gates + static veto + human review as three defenses),
  Loop B `--confirm YES` and T0 adopt defenses, explicit non-goals (no runtime input filtering).
- DoD: document exists and is cited in the `AGENTS.md` doc index table; `docs/harness-change-log.md` records it.
- Completion record: 2026-07-15 · branch docs/p1-4-threat-model (`docs/threat-model-v0.md`: three-level trust boundary + online O1–O3 / offline L1–L4 threats and three defenses + explicit non-goals + ops checklist; AGENTS.md index and harness changelog updated in the same PR)

---

## 2.5 P1.5 — Minimal Attach (commercial decoupling; may run parallel to P1-2/P1-4)

> Source: 2026-07-14 “how Core+Loop enter a user Agent directly” plan + external review (Gemini), adopted.
> **Band: High** (Adapter contract and isolation-boundary design). Grok Fast / Mid **must not** start this card’s implementation.
> **Prerequisite:** only all P0 DONE (already met). Not blocked on P1-2/P1-4.

### P1.5-1 · Minimal Attach example and Adapter contract freeze

- Status: `DONE`
- Prerequisite: all P0 DONE.
- Goal: peel business semantics from the underlying fuse. Freeze the Domain Adapter contract so an external developer can attach harness-core in 15 minutes without reading the PHA health domain; provide a **zero health-domain vocabulary** minimal IT-ticket fuse example; emit failure JSONL that Loop can consume.
- Deliverables:
  1. `packages/harness_core/src/harness_core/interfaces.py` — freeze a contract of ≤15 public symbols (`Protocol` / type aliases preferred over thick ABCs), at least covering: `build_plan`, `extract_atoms` (or equivalent allowlist extract), `post_audit`, `emit_failure_event` (fields a superset of existing failure JSONL).
  2. `examples/attach_minimal/` — ≤3 Python files: `ticket_adapter.py`, `fake_agent.py`, `run_demo.py` (in-memory ticket/permission-change scene; **forbid** wearable / biomarker / health / HRV and similar domain words).
  3. `docs/attach-in-15-minutes.md` — one-page attach guide; README “Attach Harness” path adds a pointer (link only, no body rewrite).
- Architecture constraints:
  - **Zero extra runtime deps**: `harness_core` and `interfaces.py` must not add third-party runtime deps; must not `import pha.*`.
  - **PHA degrades to a reference implementation**: this card requires `pha/harness_core_adapter.py` (or a thin wrapper) to **statically/runtime-reconcile with the contract** (`isinstance` / Protocol check or equivalent selfcheck). **Forbid** using this to rewrite the PHA chat/routing main path; a large migration is a separate card.
  - **Red lines unchanged**: no runtime self-heal; demo round 2 must fail-closed; do not write a real catalog.
- Visual/behavior (`run_demo.py` must physically print):
  - Round 1 compliant → explicit `PASS` (or equivalent success mark)
  - Round 2 over-privilege / number smuggling → explicit `FAIL-CLOSED` / `verdict.ok=False`
  - Auto-write at least one failure snapshot to `examples/attach_minimal/failures.jsonl` (or a configurable path under `/tmp`; default relative to that directory)
- DoD:

  ```bash
  # 1. Non-health-domain minimal sandbox: compliant pass + violation fuse
  PYTHONPATH=packages/harness_core/src python examples/attach_minimal/run_demo.py
  # expected: PASS and FAIL-CLOSED (or equivalent); exit 0 (demo successfully ran both paths)

  # 2. Failure emit
  test -f examples/attach_minimal/failures.jsonl
  grep -q '"passed": false\|"passed":false' examples/attach_minimal/failures.jsonl

  # 3. Docs and contract exist
  test -f docs/attach-in-15-minutes.md
  test -f packages/harness_core/src/harness_core/interfaces.py

  # 4. Package tests + full selfcheck still green; CI adds an independent step to run run_demo.py
  python -m pytest packages/harness_core/tests -q
  bash scripts/run_selfchecks.sh
  ```

  Also: `docs/harness-change-log.md` records it; this card’s status marked `DONE` in the same PR.
- Completion record: 2026-07-15 · branch feat/p1.5-1-minimal-attach — `harness_core.interfaces` v1 (10 public symbols: `DomainAdapter` three-method Protocol / `run_post_audit` / `emit_failure_event` / `AuditVerdict` / `is_domain_adapter` etc.); `examples/attach_minimal/` three-file IT-ticket demo (Turn 1 PASS / Turn 2 FAIL-CLOSED writes failures.jsonl, verified consumable by `harness-loop harvest`); PHA reference `PHANumericsAdapter` + selfcheck contract reconcile; `packages/harness_core/tests/test_interfaces.py` 8 cases; independent CI step; `docs/attach-in-15-minutes.md`; harness-core `0.0.0a2`

---

## 3. P2 — after an external signal (do nothing if the trigger is unmet)

| ID | Task | Trigger | Status |
|----|------|----------|--------|
| P2-1 | Publish harness-core / harness-loop to PyPI (alpha channel) | ≥1 external builder explicitly says vendored install is inconvenient (written record) | `TODO` |
| P2-2 | Split pha/ giant modules (`wearable_compare_table_v1.py` and other 1000+ line files) | A second active contributor appears, or that module needs a large functional change | `TODO` |
| P2-3 | Land multi-tenant / device-ingest RFC | Real ToB integration intent (not a thought experiment), and the other party confirms the scene | `TODO` |
| P2-4 | CI coverage gate | P0-2 and P1-1 in-package tests both DONE | `DONE` |

### P2-4 · CI coverage gate (completion summary)

- Status: `DONE`
- Goal: add `--cov-fail-under` on the **library surface** of portable packages `harness_core` + `harness_loop`, so later extract/refactor cannot silently drop coverage.
- Scope: `.coveragerc` omits `cli.py` / `paths.py` / `plugins/*` (CLI and PHA plugins are covered by selfcheck / e2e, not this gate).
- Threshold: `fail-under=80` (library surface measured ≈86% at land; leave regression slack).
- DoD:

  ```bash
  pip install pytest pytest-cov
  python -m pytest packages/harness_core/tests packages/harness_loop/tests -q \
    --cov=harness_core --cov=harness_loop \
    --cov-config=.coveragerc \
    --cov-report=term-missing:skip-covered \
    --cov-fail-under=80
  # expected: all passed and Required test coverage of 80% reached
  ```

  CI: `.github/workflows/ci.yml` step “Harness packages unit tests + coverage gate (P2-4)” runs the same command.
- Completion record: 2026-07-18 · `.coveragerc` + CI fail-under=80; local DoD 53 passed / 86.3%

---

## 4. New findings register (append during execution; do not edit historical rows)

| Date | Finding | Source task | Disposition |
|------|---------|-------------|-------------|
| 2026-07-14 | Maintainer asked to automate “task → model-band routing” so humans do not pick models (external suggestion reviewed: drop hard-coded model names, use band semantics; make soft-gate boundaries explicit) | Execution protocol §0 | Landed: `.cursor/rules/audit-plan-execution.mdc` adds Model Routing Protocol section |
| 2026-07-14 | README Builder section still says harness-loop `0.1.0a3`; main is already `0.1.0a4` (P1-1) | P1-3 | **Fixed**: README + `packages/harness_loop/README.md` → `0.1.0a4` (branch chore/a-readme-a4-and-p12-prep) |
| 2026-07-14 | High quota insufficient; P1-2 invitation body / P1-4 threat model deferred; do Mid transactional assist first | P1-2 | Wrote [`docs/p1-2-outreach-prep.md`](p1-2-outreach-prep.md) (Issue #1 status, invitee table, §4 feedback template; **no** invitation body) |
| 2026-07-14 | Core+Loop “enter a user Agent directly” needs Adapter contract + dehydrated minimal example; external review agrees and suggests P1.5 | Planning | **Card opened** P1.5-1 (see §2.5); implementation requires High; this commit only checks in the task card, no architecture code |
| 2026-07-31 | GitHub glance misread as a “Health app”: repo name `personal_health_agent` vs About/README writing a general harness (distribution diagnosis) | Distribution audit | **Narrative fix**: README first screen becomes Harness Core+Loop; PHA degrades to reference; **repo renamed `hihewh-byte/agent-harness`** (in-repo clone/Homepage/Issue links synced) |
| 2026-08-31 | Maintainer will gradually make PHA an iOS App + proactive health-management Agent (HealthKit collection; not changing the harness OSS narrative) | Product planning | **Consensus PRD opened** [`docs/prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md); ack line `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`. Orthogonal to this audit’s P2 trigger cards: this track follows PRD milestones and does not auto-start PyPI / giant-module splits |

---

## 5. Revision record

| Date | Change | Author |
|------|--------|--------|
| 2026-07-14 | First version: 2026-07-14 audit report turned into an executable plan | audit agent |
| 2026-07-14 | Execution protocol adds model compute reconciliation (Model Routing Protocol; see the rule file) | audit agent |
| 2026-07-14 | Add §2.5 P1.5-1 Minimal Attach / Adapter contract task card (review adopted; implementation waits for High) | audit agent |
| 2026-07-18 | P2-4 DONE: CI harness-package library-surface coverage gate (`.coveragerc` omits CLI/plugin, fail-under=80) | coding agent |
