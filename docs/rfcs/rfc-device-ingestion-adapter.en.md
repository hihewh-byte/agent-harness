# RFC · Universal Device Ingestion Adapter

> **Language / 语言**：English (this document) · [中文](rfc-device-ingestion-adapter.md)

> **Filename**: `docs/rfcs/rfc-device-ingestion-adapter.md`  
> **Version**: v0.1 (2026-07-05)  
> **Status**: 📋 **Ratified (jurisprudence design · Future Work · zero production code)**  
> **Governing docs**: [`pha-pm-constitution.md`](../pha-pm-constitution.md) Article 3 · [`wearable-metric-registry-v1.md`](../wearable-metric-registry-v1.md) · [`wave4b-chronic-health-brief-spec.md`](../wave4b-chronic-health-brief-spec.md)

---

## 0. Core ask

> Allow **any third-party** wearable / IoT device (MQTT · BLE · HTTP Webhook · private-cloud API) to wash raw telemetry into PHA standard L1 daily-aggregate rows, **without modifying** CompareTable · Harness FSM · P1 gold label chains.

**This RFC contains no vendor names, topic names, or private payload field hardcoding.**

---

## 1. Non-goals

- Do not add a fifth `prov_type` (see §4 two-layer labels)
- Do not change the `wearable_daily` table shape (new columns go through Registry + Wave 3d-δ)
- Do not ingest synchronously inside a Chat Turn (do not block the FSM)
- Do not enter PR blocking CI

---

## 2. Three-layer interconnect (reuse existing L0→L1→L2)

```text
L0  DeviceIngestAdapter (one-shot encode per transport)
      parse_envelope → NormalizedSample[]
         │
L1  sqlite_storage.upsert_* (existing API · user_id partitioned)
         │
L2  CompareTable / CHB §Facts (Registry-driven · zero algorithm change)
         │
L3  LLM narrative + Audit (unchanged)
```

Shares the **same L1 exit** as Apple Health `export.zip` import; the only difference is the L0 parser.

---

## 3. Unified interface contract

### 3.1 `DeviceIngestAdapter` (abstract)

| Member | Type | Notes |
|------|------|------|
| `adapter_id` | `str` | Globally unique, e.g. `generic_mqtt_v1` |
| `supported_transports` | `set[str]` | `mqtt` · `ble` · `http_webhook` |
| `parse_envelope(raw: bytes \| dict) → list[NormalizedSample]` | | Raw packet → normalized samples |
| `normalize_units(sample) → NormalizedSample` | | SI / registry standard units |
| `dedupe_key(sample) → str` | | → `wearable_data.sample_id` |

### 3.2 `NormalizedSample` (Schema)

```json
{
  "user_id": "default",
  "metric_type": "hrv",
  "timestamp": "2099-01-01T12:00:00+00:00",
  "value": 55.0,
  "sample_id": "ingest:{adapter_id}:{device_id}:{metric}:{ts}",
  "source_vendor": "vendor_slug",
  "device_id": "opaque_device_ref",
  "raw_payload_ref": "optional_audit_blob_id"
}
```

**Hard requirements:**

- `sample_id` globally unique and idempotent (duplicate delivery → `INSERT OR IGNORE`)
- `user_id` is resolved by the Ingest Gateway (see Enterprise RFC); the Adapter **must not** guess the user

### 3.3 Registry hookup

Declare in [`wearable_metric_registry.json`](../../storage/registry/wearable_metric_registry.json) `ingest_modules[]`:

```json
{
  "module_id": "generic_mqtt_v1",
  "adapter": "pha.device_adapters.generic_mqtt.GenericMqttAdapter",
  "transport": "mqtt",
  "source_vendor": "vendor_slug",
  "registry_metrics": ["hrv_rmssd_ms", "resting_heart_rate_bpm"]
}
```

New metrics: **prefer mapping an existing `l1.field`**; if the registry has no column, take a Wave 3d-δ encoding PR — do not privately alter the table inside the Adapter.

---

## 4. Two-layer label jurisprudence (the P1/P2 zero-change key)

| Layer | Field | Value | Consumers |
|----|------|-----|--------|
| **T0 jurisprudence** | `prov_type` | still `wearable_import` | CompareTable · CHB · numerics audit |
| **Provenance** | `source_vendor` | any slug (e.g. device-ecosystem name) | audit · ops · version traceback |
| **Row key** | `ref_id` | `{vendor}_{device_id}_{metric_id}_{day}` | CHB §Facts `[ref:…]` |

**Forbidden** to add a fifth `prov_type` for specific hardware — otherwise P1 `expectations_v1.json` · N-CHB cases must all be re-signed.

---

## 5. Async ingest topology

```text
Device Cloud / BLE Gateway
    → Ingest Worker (separate process / Cron · not HTTP Turn)
        → Adapter.parse + normalize
        → upsert_wearable_daily_batch / WearableDataBatchWriter
        → [optional] pha_chb_compile_all_users.py (already in P2)
    → Harness next round reads the latest brief (already in 4-β-2a)
```

Natural join with P2 loop B: L1 change → `ledger_hash` changes → offline stale recompile.

---

## 6. Unit normalization

The RFC implementation phase must keep a **vendor_field → metric_id → SI unit** map on the Registry side (JSON, not Python hardcoding):

| registry `metric_id` | L1 column | Standard unit |
|----------------------|-------|----------|
| `hrv_rmssd_ms` | `hrv_rmssd_ms` | ms |
| `resting_heart_rate_bpm` | `resting_heart_rate_bpm` | bpm |
| `sleep_time_asleep` | `sleep_hours` | h |

The Adapter only converts; CompareTable **does not** see the vendor.

---

## 7. §X. SOTA Benchmarking

| Benchmark | PHA adopts |
|------|----------|
| **FHIR Observation** | Normalized sample + provenance ref; no first-release FHIR Server |
| **Home Assistant entity → recorder** | Async write to the timeseries store; chat layer does not block |
| **Timescale / IoT pipelines** | `sample_id` idempotent; out-of-order tolerant |

---

## 8. Acceptance scenarios (future encoding phase)

| ID | Scenario | Expectation |
|----|------|------|
| D-ING-1 | Mock MQTT envelope → Adapter | L1 row written · correct `sample_id` |
| D-ING-2 | Duplicate envelope | Zero duplicate rows |
| D-ING-3 | L1 change | P2 stale → new `brief_{hash}.json` |
| D-ING-4 | CompareTable follow-up on HRV | Same as P1 E2 · audit no violations |

---

## 9. Revision history

| Date | Notes |
|------|------|
| 2026-07-05 | v0.1 Universal edition; two-layer labels; zero vendor hardcoding |
