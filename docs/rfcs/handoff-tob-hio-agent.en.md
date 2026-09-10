# ToB handoff · Hospital IoT Ops Agent (HIO)

> **Language / 语言**：English (this document) · [中文](handoff-tob-hio-agent.md)

> **Audience**: the new Agent dedicated to ToB / HIO (and the human owner)  
> **Author stance**: product judgment and asset handoff from the PHA / harness-core mainline Agent  
> **Date**: 2026-07-11  
> **Status**: product-discussion stage · **zero production code by default**, until there is a clear buyer signal or the owner orders a PoC start

This document is the **only recommended entry**. Read it fully before changing product docs or writing code.

---

## 0. What you are here to do (Mission)

Move “trusted in-hospital IoT ops assistant” from a **discussable product definition** to **pre-sales, acceptance, and PoC-ready** ToB deliverables.

| Stage | Goal | Output |
|-------|------|--------|
| **Now (product)** | Converge what we sell, what we don’t, how we accept | Product definition freeze, one-pager pre-sales, PoC scope sheet |
| **After a buyer signal (PoC)** | One department, one set of read-only views, adversarial fuse demoable | Private PoC repo + golden_run PASS |
| **After contract (delivery)** | Embed vendor console, tenant isolation, contract acceptance scripts | Deploy pack + acceptance report |

**You are not here to**: build a hospital-wide smart brain, file medical-device registration, rewrite PHA personal edition, stuff JWT/base-station protocols into `harness_core`, or publicly push `tax_agent`.

---

## 1. Product judgment (handoff author’s own definition and advice)

The following **complements** Gemini pre-sales copy: Gemini owns “looks hard”; this section owns “don’t sell the wrong thing, don’t blow up”.

### 1.1 One sentence (recommended external line)

> **HIO-A**: a **trusted reconciliation layer** hung on the hospital’s existing IoT platform — ask utilization / offline / alerts / location in natural language, and **every number in the answer must click through to the read-only DB**; forcing it to lie trips the fuse.

Do not lead with “smarter AI”; lead with **conversation and an audit pack on top of the dashboard that is not allowed to lie**.

### 1.2 Real sellable differentiation (by strength)

1. **Contract-acceptable honesty** (0-LLM golden + adversarial-injection fuse) — dashboard / generic Agent competitors almost never have this.  
2. **This-turn evidence card (Trust Trace)** — the “traditional-software safety feel” selling point for management.  
3. **Cascading device-tree hard routing** — kill open-domain hallucination at the door (MVP does no NER guessing of devices).  
4. **0-Token weekly-report slot fill (HIO-R)** — stickiness and renewal reason, not the sole first-deal selling point.

### 1.3 SKU advice (tighter than Gemini)

| SKU | Advice | Why |
|-----|--------|-----|
| **HIO-A** | **Only P0 lead SKU** | Buyer pain is clear (equipment-dept reconciliation); data views relatively standard |
| **HIO-D** | **P0 standard pre-sales pack** | Without a live “force 99% → fuse” demo, the premium is unexplainable |
| **HIO-R** | **Ship together or bundle on first deal** | Cheap to build (fast_lane); department-head weekly meeting is a real need |
| **HIO-G** | **P1, only after green-channel data quality** | Dirty node timestamps kill product credibility first |
| **HIO-A+** | **Promise with care** | Touches HIS/RIS; integration and political cost far above IoT views |
| **HIO-N** | **Roadmap** | Vertical scene; not first-deal |

### 1.4 GTM advice

* **Channel first**: sell to **IoT vendors / integrators** first (value-add module hung on the console), then enter hospitals with the vendor; do not start with direct sales to tertiary-hospital equipment departments (cycle and relationship network mismatch).  
* **Wedge customer profile**: vendors that already have asset location + utilization/alert stores but lack “trusted conversation” (reference profile: Zhongke Cihang-class).  
* **PoC success bar (write into internal discipline)**:  
  1 department tree + ≥2 read-only views + 3 fixed questions 100% reconciled + 1 adversarial fuse demo, told in ≤ 30 minutes.  
  **Not** “the feature list is done”.

### 1.5 Honesty limits that must go into the product boundary

* “100% reconciles” **applies only to the closed question set written in the contract** (utilization, offline count, alert Top-N, last location, etc.), not arbitrary chat.  
* Compliance copy: **ops / quality-control management aid, not clinical care**; **do not claim** “definitely exempt from medical-device registration / all approvals” — use cautious wording until legal signs off (see the product definition).  
* Numeric audit grades (already in the technical RFC): hard numbers L-strict must fuse; soft narrative L-soft may pass — pre-sales must not sell “absolute” as mysticism.

### 1.6 Repo and code ownership advice

| Content | Suggested location | Why |
|---------|-------------------|-----|
| Product/RFC docs (current) | `<repo>/docs/rfcs/*` | Already hooked to the Core blueprint; docs can keep iterating |
| **HIO production/PoC code** | **New private repo** or `myAgents/hospital_iot_ops_agent/` (local) | **Do not** push hospital vendor adapters, sample DBs, or pre-sales demo data into the PHA public repo |
| Control plane | **Consume** `packages/harness_core` (copy or path dep) | Core is already vendored in public PHA; HIO is a Domain Plugin |
| `tax_agent` | **Read-only reference twin**; **no push / no copy of private data** | Local financial privacy |

### 1.7 Suggested next priorities for you (ToB Agent)

1. **Product freeze**: on the existing definition, add “closed question list v0” + “non-goals one-pager” + “PoC scope sheet” (still zero code).  
2. **One-pager pre-sales**: PDF/Markdown for vendor BD (problem → solution → acceptance → integration, four steps).  
3. **Freeze the data contract**: write the field-level minimum set of `asset_daily` / `asset_alert_event` / `location_fix` as tables a vendor DBA can use.  
4. **Wait for a buyer signal before code**: open PoC only after DB engine, department, iframe vs standalone are decided.  
5. **Do not** parallel-implement HIO-G/A+/N; do not “casually add hospital fields” to the harness-core protocol.

---

## 2. Existing document assets (required reading order)

| Order | Path | Use |
|-------|------|-----|
| 1 | **This doc** `docs/rfcs/handoff-tob-hio-agent.md` | Task boundary and advice |
| 2 | [`product-definition-hio-ops-agent.md`](product-definition-hio-ops-agent.md) | **External product definition** (positioning/users/features/delivery/acceptance) v0.2 |
| 3 | [`rfc-hospital-iot-ops-agent.md`](rfc-hospital-iot-ops-agent.md) | **Technical + product RFC** v0.2 (SKU, Trust Trace, data preference, comps) |
| 4 | [`../harness-core-protocol-v0.md`](../harness-core-protocol-v0.md) | Core protocol: Plan → freeze → compose/fast_lane → post_audit |
| 5 | [`../harness-core-evolution-blueprint.md`](../harness-core-evolution-blueprint.md) §5 | ToB vs Core boundary (Gateway/Ingest outside) |
| 6 | [`rfc-enterprise-multi-tenant.md`](rfc-enterprise-multi-tenant.md) | Tenant/Gateway design (when HIO auth is externalized) |
| 7 | [`rfc-device-ingestion-adapter.md`](rfc-device-ingestion-adapter.md) | Device ingest L0 (HIO prefers DB View; may not use this RFC) |

**Public repo**: https://github.com/hihewh-byte/agent-harness (default `main`; Harness + PHA reference; HIO is DOC only).

---

## 3. Reusable technical assets (code layer)

### 3.1 harness-core (control plane · reuse directly)

| Location | Notes |
|----------|-------|
| `<repo>/packages/harness_core/` | **Already vendored publicly**; authoritative delivery shape |
| `myAgents/harness_core/` | Isomorphic skeleton under the workspace root (interface-level) |

**Modules**: `turn_plan` · `turn_fsm` · `integrity` · `plan_vs_actual`  
**Spine**: `INIT → SESSION → PLAN → COMPOSE → POST_AUDIT → DONE`  
**Iron rules**: numeric whitelist / allowlist; plan vs actual; 0-LLM dry-run possible.

### 3.2 Adapter examples (write the HIO adapter from these; do not copy business)

| Path | Notes |
|------|-------|
| `<repo>/pha/harness_core_adapter.py` | PHA thin adapter; public-repo reference |
| `tax_agent/harness_core_adapter.py` | Local twin; **read-only reference, do not leak** |
| `<repo>/scripts/pha_harness_golden_run.py` | Green-wall example: must print `PASS harness_core adapter` |

### 3.3 Architecture slogan (paste into PR descriptions when implementing)

```text
Core Spine ← Adapter ← Domain Plugins (PHA / Tax / future HIO)
Plan → freeze evidence → compose | fast_lane → post_audit

Gateway / RBAC / device protocol / base station  —— all outside Core
```

### 3.4 Explicitly “not directly usable as HIO”

* PHA personal health chat, wearable sync, clinical-adjacent copy  
* ASI (`agentic_sales_intelligence`) — already judged **not** a harness completeness prerequisite; do not whole-repo-reshape it into HIO  
* `tax_agent` business data and any real financial/identity information  

---

## 4. Iron rules (violate = stop)

1. **Zero HIO production code by default**, until the owner confirms a buyer signal or explicitly “start PoC”.  
2. **Forbidden** to push to the public net: real hospital assets, incompletely de-identified samples, vendor keys, `tax_agent`.  
3. **Forbidden** to put JWT/RBAC/RF protocols into `harness_core`; HIO only does Domain Plugin + read-only tools.  
4. **Forbidden** to externally promise medical-device registration outcomes or “exempt from all compliance”.  
5. **MVP forbids** open-domain NER guessing of devices; if no tree selection, guide to the tree — do not empty-run.  
6. Core protocol changes must return to PHA mainline review; HIO side prefers **adapt**, not **fork Core**.

---

## 5. Suggested work split (backlog for the ToB Agent)

### Track P · Product (current default)

- [ ] Closed question list v0 (≤10 each EN/ZH) + each maps to SQL/view fields  
- [ ] One-pager pre-sales (vendor BD)  
- [ ] PoC scope sheet: department, views, deploy shape (iframe/standalone), success bar  
- [ ] Contract acceptance clause draft (align product definition §5)  
- [ ] Competitor copy card: PerformanceBridge-class “dashboard” vs our “honesty gate”

### Track T · Technical design (still DOC)

- [ ] Three-view field-level contract (DBA-executable)  
- [ ] Trust Trace JSON schema draft (evidence-card UI binding)  
- [ ] HIO Adapter interface sketch (against `pha/harness_core_adapter.py`)  
- [ ] `run_hio_a_golden_run.py` case table (including adversarial injection)

### Track C · Code (only after authorization)

- [ ] Private-repo scaffold + path-dep harness_core  
- [ ] Fake/de-identified SQLite sample + cascade tree + chat + evidence-card min UI  
- [ ] fast_lane weekly report (HIO-R)  
- [ ] golden_run green wall + pre-sales adversarial script (HIO-D)

---

## 6. Division of labor with PHA mainline

| Role | Owns |
|------|------|
| **PHA / Core mainline Agent** | harness-core protocol stability, PHA public quality, personal health product |
| **ToB / HIO Agent (you)** | HIO product-definition depth, pre-sales materials, PoC/delivery, vendor-integration narrative |
| **Collaboration** | If HIO finds a Core gap → raise a protocol-change request to mainline, **do not silently fork** |

Historical context (human-readable): Cursor agent transcript discussions of PHA Phase A closeout, Core vendoring, HIO RFC; Issue #1 stays OPEN as a builder call, not strongly bound to HIO.

---

## 7. Handoff checklist (self-check when a new Agent starts)

- [ ] Has read the product definition + this handoff + RFC §0–2  
- [ ] Can restate in own words: we sell a “trusted reconciliation layer”, not “smarter AI”  
- [ ] Knows code defaults to DOC; knows public PHA vs private HIO repo boundary  
- [ ] Knows reusable `packages/harness_core` + adapter/golden examples  
- [ ] Knows iron rules: no NER, no Gateway stuffed into Core, no tax leak, no unreviewed device-registration claims  

---

## Revision history

| Version | Date | Notes |
|---------|------|-------|
| v0.1 | 2026-07-11 | First version: product judgment + asset map + ToB Agent backlog |
