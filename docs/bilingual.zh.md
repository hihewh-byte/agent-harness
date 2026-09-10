# 维护者文档 — 双语约定

> **Language / 语言**：[English](bilingual.md) · 中文（本文）

`docs/` 下的**维护者文档**（产品规格、PRD、RFC、ingest/事实卡契约、路线图、宪法、仍约束工作的交接）必须是 **中文 + 英文**成对文件。公开 README 仍以英文为第一屏，可链到英文孪生页。

## 配对

| 原文件 | 孪生 |
|--------|------|
| `foo.md`（中文正文、历史路径） | `foo.en.md` |
| `foo.md`（英文正文） | `foo.zh.md` |
| 已有 `foo.zh.md` / `foo.en.md` | 保持；可选无正文的 `foo.md` 索引 |

**不要**为了双语去改已有 URL。缺哪边补哪边。

## 文首（两个孪生都要）

中文原件：

```markdown
> **Language / 语言**：[English](foo.en.md) · 中文（本文）
```

英文孪生：

```markdown
> **Language / 语言**：English (this document) · [中文](foo.md)
```

标识符（`metric_id`、环境变量、路径、HTTP）保持原样。翻译正文、表格和验收句。

## 不在本约定内

- `reports/**` 运行时产出
- `tests/fixtures/**`（维护者 README 除外）
- LinkedIn / 社交发帖稿（不准进 git）

## 改一边时

同一次改动更新另一边。来不及写双语就不要合入。
