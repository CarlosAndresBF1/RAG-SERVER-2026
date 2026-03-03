# Source Documents

Place source documents here for ingestion into the Odyssey RAG system.

## Supported file types

| Source Type | Extension | Description |
|-------------|-----------|-------------|
| `annex_b_spec` | `.md` | IPS Annex B Message Specifications |
| `tech_doc` | `.md` | Technical documentation (Notion exports, etc.) |
| `claude_context` | `.md` | CLAUDE.md context files |
| `php_code` | `.php` | Bimpay PHP source files |
| `xml_example` | `.xml` | IPS message XML examples |
| `postman_collection` | `.json` | Postman collection exports |
| `pdf_doc` | `.pdf` | PDF documentation |
| `generic_text` | `.txt` | Plain text (fallback) |

## Directory structure

Organize files by integration/type:

```
data/sources/
├── annex_b/           # Annex B spec markdown
├── tech_docs/         # Technical documentation
├── php/               # PHP source code
├── xml_examples/      # XML message examples
├── postman/           # Postman collections
└── pdf/               # PDF documents
```

Files are auto-detected by the ingestion pipeline based on extension and content.
