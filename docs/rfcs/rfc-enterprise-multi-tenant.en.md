# RFC · Enterprise Multi-Tenant Gateway

> **Language / 语言**：English (this document) · [中文](rfc-enterprise-multi-tenant.md)

> **Filename**: `docs/rfcs/rfc-enterprise-multi-tenant.md`  
> **Version**: v0.1 (2026-07-05)  
> **Status**: 📋 **Ratified (jurisprudence design · Future Work · zero production code)**  
> **Governing docs**: [`pha-pm-constitution.md`](../pha-pm-constitution.md) · [`wave4a-open-source-readiness-spec.md`](../wave4a-open-source-readiness-spec.md) · [`rfc-stage4b-personalization-flywheel.md`](rfc-stage4b-personalization-flywheel.md)

---

## 0. Core ask

> Support B-end concurrent access and auth isolation for “hospital/department → doctor → many patients” **without modifying** the PHA Core FSM · Harness Profile topology · CompareTable algorithm.

**The personal open-source edition (Wave 4a) deliberately does not include this RFC’s implementation.**

---

## 1. Non-goals

- Do not change the `orchestrate_chat_turn_events` signature or the Profile registry
- Do not change SQLite primary keys or add a `tenant_id` column in Phase 1
- Do not embed RBAC logic in Harness / LLM prompts
- Do not require P1 gold / PR CI re-sign

---

## 2. Why the FSM can stay 100% unchanged

PHA Core today only recognizes **`effective_user_id`**:

```text
orchestrate_chat_turn_events(user_id=…)
sqlite: WHERE user_id = ?
reports/chb/{user_id}/
chat_sessions: user_id column
```

The Enterprise Gateway finishes at the HTTP boundary:

```text
(JWT tenant_id, actor_id, patient_id) → effective_user_id
```

Core still receives a single string `user_id` — FSM · Tier0 · CompareTable · CHB read path are **physically unchanged**.

---

## 3. Phase 1: composite user_id namespace (recommended first cut)

### 3.1 Format

```text
effective_user_id = "{tenant_id}:{patient_id}"
```

| Component | Rule |
|------|------|
| `tenant_id` | Department/hospital slug; `[a-z0-9_-]{1,64}` |
| `patient_id` | In-hospital patient ID; same |
| Separator | Single character `:`; **forbidden** for `patient_id` to contain an unescaped `:` |

### 3.2 Compatibility with existing storage

| Subsystem | Phase 1 behavior |
|--------|--------------|
| SQLite `wearable_daily` PK `(user_id, day)` | ✅ composite string as user_id |
| `reports/chb/{user_id}/` | ✅ directory name may contain `:` (filesystem allows it) |
| P2 `pha_chb_compile_all_users.py` | ✅ walk directory names |
| Personal edition `default` | ✅ no colon · backward compatible |

**No** Phase 1 migration script needed.

### 3.3 Phase 2+ (scale, Future)

| Stage | Storage evolution |
|------|----------|
| Phase 2 | Path convention `tenants/{tid}/patients/{pid}/` (CHB · attachments · export) |
| Phase 3 | SQLite adds `tenant_id` column + composite index; query-layer filter |
| Phase 4 | Optional per-tenant DB shard |

This RFC approves Phase 1 as the Enterprise **minimum encodable** incision; Phase 2+ is a separate project.

---

## 4. Enterprise Gateway duties

```text
Client (Clinician App / EHR iframe)
    │
    ▼
Enterprise Gateway (:8443 or reverse proxy)
    ├── JWT verify (iss / exp / aud)
    ├── Parse claims: tenant_id, sub=actor_id, roles[]
    ├── RBAC: care_relationships table → may this actor access patient_id
    ├── Build effective_user_id = f"{tenant_id}:{patient_id}"
    ├── Cross-tenant / over-privilege → 403 + structured audit NDJSON
    └── Forward → PHA Core (:8788) existing REST/SSE API
    │
    ▼
PHA Core (no tenant concept · trusts the user_id the Gateway injects)
```

### 4.1 The Gateway **does not**

- Call the LLM · assemble Harness slots
- Read/write SQLite directly (Phase 1 all forwarded to Core)
- Change chat-turn routing

### 4.2 The Gateway **must**

- Production **must not** silently fall back to `user_id=default`
- Every forward carries `X-PHA-Actor-Id` · `X-PHA-Tenant-Id` (audit; Core may optionally record)
- Structured over-privilege logs (no PHI body)

---

## 5. Minimum RBAC model

### 5.1 Roles

| Role | Permission |
|------|------|
| `tenant_admin` | Manage tenant members · audit read-only |
| `doctor` | Bound patient’s chat / data read / report export |
| `patient` | Only their own `effective_user_id` (C-end) |
| `device_ingest` | Ingest API wearable writes only; no chat |

### 5.2 Relationship tables (Gateway DB · not PHA Core SQLite)

```text
tenant_members(tenant_id, actor_id, role, created_at)
care_relationships(tenant_id, doctor_id, patient_id, status, granted_at)
device_bindings(tenant_id, device_id, patient_id, bound_at)
```

Device Ingest must look up `device_bindings` to resolve `patient_id` → `effective_user_id` (see Device RFC §3.2).

---

## 6. Security red lines

| ID | Red line |
|----|------|
| MT-1 | Gateway is the only tenant-resolution point; Core API must not accept a bare `tenant_id` Query that bypasses RBAC |
| MT-2 | Personal OSS edition defaults to `127.0.0.1` + no auth — **must not share the same public port with an Enterprise deploy** |
| MT-3 | Cross-tenant access attempt → 403 · logs must not contain lab values / chat body |
| MT-4 | JWT short TTL + refresh; no long-lived token embedded in the frontend |

---

## 7. High concurrency and memory sandbox

- Gateway: **stateless**; session stickiness not required
- PHA Core: existing `user_id` partitioning is enough; SSE session dual-key check on `session_id` + `user_id`
- **Forbidden** thread-global current tenant; request-scoped context only
- Horizontal scale: Gateway replicas + Core workers; shared SQLite is **not** an Enterprise Phase 1 goal (Phase 3+ external PG)

---

## 8. §X. SOTA Benchmarking

| Benchmark | PHA adopts |
|------|----------|
| **SMART on FHIR** | Gateway auth + resource scoped to patient |
| **Keycloak Organizations** | tenant hierarchy · role mapping |
| **Supabase RLS** | Phase 3 optional DB-layer filter; Phase 1 uses the namespace |

---

## 9. Acceptance scenarios (future encoding phase)

| ID | Scenario | Expectation |
|----|------|------|
| MT-E1 | Doctor A accesses Patient X (has care_relationship) | 200 · correct effective_user_id |
| MT-E2 | Doctor A accesses Patient Y (no relationship) | 403 · audit log |
| MT-E3 | Tenant T1 doctor accesses Tenant T2 patient | 403 |
| MT-E4 | Same effective_user_id conversation | FSM profile identical to personal edition |
| MT-E5 | Device ingest writes wearable | Row lands in `{tid}:{pid}` partition |

---

## 10. Revision history

| Date | Notes |
|------|------|
| 2026-07-05 | v0.1 Universal edition; Phase 1 composite user_id; FSM zero-change argument |
