---
doc_type: dev-guide
slug: translation-terms-v1
component: document-ir-translation
status: current
summary: Minimal read-only CSV terminology format for P1 DocumentIR translation.
tags: [backend, translation, terminology, document-ir]
last_reviewed: 2026-05-30
---

# Translation Terms v1

P1 DocumentIR translation uses a read-only CSV glossary. It is intentionally small: online editing, conflict handling, priorities, and rollback are out of scope for this phase.

Default path:

```text
template_configs/translation_terms.csv
```

Required columns:

| Column | Meaning |
|---|---|
| `language_pair` | Translation direction, for example `en2zh` |
| `source_term` | Source-language term sent to the provider as glossary context |
| `target_term` | Target-language preferred translation |
| `version` | Immutable glossary version within the language pair |

Runtime binding uses `language_pair@version`, for example `en2zh@v1`. `document_jobs.term_version_id` stores that canonical value for translation tasks.

The loader validates the required columns, rejects blank required values, and computes a `sha256:<hex>` snapshot hash from the matched rows. It does not mutate the CSV or write a runtime store.
