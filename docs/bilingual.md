# Maintainer docs — bilingual convention

> **Language / 语言**：English (this document) · [中文](bilingual.zh.md)

Every **maintainer** document under `docs/` (product specs, PRDs, RFCs, ingest/fact-card contracts, roadmaps, constitutions, handoffs that still bind work) ships as a **Chinese + English pair**. Clone-facing README stays English-first; it may link the English twin.

## Pairing

| Canonical file | Twin |
|----------------|------|
| `foo.md` (Chinese body, historical path) | `foo.en.md` |
| `foo.md` (English body) | `foo.zh.md` |
| `foo.zh.md` / `foo.en.md` already | keep both; optional `foo.md` index with no body |

Do **not** rename existing URLs. Add the missing twin beside them.

## Header (required on both twins)

Chinese original:

```markdown
> **Language / 语言**：[English](foo.en.md) · 中文（本文）
```

English twin:

```markdown
> **Language / 语言**：English (this document) · [中文](foo.md)
```

Keep identifiers (`metric_id`, env vars, paths, HTTP routes) identical. Translate prose, tables, and acceptance text.

## Out of this rule

- `reports/**` runtime dumps
- `tests/fixtures/**` except a short README twin if the README is maintainer-facing
- LinkedIn / social post copy (does not belong in git)

## When you edit one twin

Update the other in the same change. If you only have time for one language, do not land the edit.
