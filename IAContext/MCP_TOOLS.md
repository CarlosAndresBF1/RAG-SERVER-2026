# Odyssey RAG — MCP Tools Specification

> **Version**: 1.1.0  
> **Date**: 2026-03-15  
> **Status**: Implemented  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §2.1, §3.2

---

## Overview

The MCP server exposes **6 tools** designed for the ISO 20022 / Barbados IPS / Odyssey domain. These tools are the primary interface for AI agents in VS Code (Copilot, Claude Code, etc.) to query the knowledge base.

### Design Principles

1. **Domain-specific inputs**: message types (pacs.008, camt.056), XPaths, ISO status codes — not generic REST
2. **Uniform output contract**: every tool returns `evidence[]`, `gaps[]`, `followups[]`
3. **Strict citations**: `strict_citations=true` by default — no evidence = explicit gap, never fabrication
4. **Extensible**: new integrations/doc types added as new `source_type` values, not new tools
5. **Composable**: agents are expected to chain tools (e.g. `find_module` → `find_message_type` → `find_error`)

### Output Contract (All Tools)

```json
{
  "evidence": [
    {
      "id": "chunk_uuid",
      "score": 0.87,
      "title": "pacs.008 — Group Header Fields",
      "snippet": "GrpHdr/MsgId is Mandatory [1..1], Max35Text. Must be unique...",
      "citations": [
        {
          "source_type": "annex_b_spec",
          "source_id": "IPS_Annex_B_Message_Specifications.md",
          "locator": "§ pacs.008 > GrpHdr > MsgId",
          "uri": "odyssey://docs/annex-b/pacs.008#GrpHdr-MsgId"
        }
      ],
      "metadata": {
        "message_type": "pacs.008",
        "iso_version": "pacs.008.001.12",
        "module_path": "Bimpay/Messages/Pacs008CreditTransfer.php",
        "php_class": "Pacs008CreditTransfer",
        "field_xpath": "GrpHdr/MsgId",
        "rule_status": "M",
        "source_type": "annex_b_spec"
      }
    }
  ],
  "gaps": [
    "No runbook found for pacs.008 timeout scenarios"
  ],
  "followups": [
    {
      "tool": "odyssey_rag.find_error",
      "args": {"iso_status": "RJCT", "reason_code": "FF01", "message_type_hint": "pacs.008"},
      "rationale": "Check XSD validation failure handling for this message type"
    }
  ]
}
```

---

## Tool 1: `odyssey_rag.find_message_type`

### Purpose
Retrieve comprehensive evidence for an ISO 20022 message type: Annex B specification fields, PHP builder/parser/validator code, XML examples, and related docs.

### Typical Usage
- "How do I build a pacs.008 for 500 BBD?"
- "What fields are mandatory in a camt.056 recall?"
- "Show me the pain.013 Request-to-Pay structure"
- "What does the Pacs008Parser extract?"

### Input Schema

```json
{
  "name": "odyssey_rag.find_message_type",
  "description": "Retrieve evidence (Annex B spec, PHP code, XML examples) for an ISO 20022 message type and its Odyssey implementation.",
  "inputSchema": {
    "type": "object",
    "required": ["message_type"],
    "properties": {
      "message_type": {
        "type": "string",
        "description": "ISO 20022 message identifier: 'pacs.008', 'camt.056', 'pain.013', etc.",
        "enum": ["pacs.008", "pacs.002", "pacs.004", "pacs.028", "camt.056", "camt.029", "pain.001", "pain.002", "pain.013", "pain.014"]
      },
      "focus": {
        "type": "string",
        "enum": ["overview", "fields", "builder", "parser", "validator", "examples", "envelope"],
        "default": "overview",
        "description": "Narrow the search: 'fields' = Annex B spec only, 'builder' = PHP Message class, 'parser' = PHP Parser class, 'validator' = validation rules, 'examples' = XML samples, 'envelope' = AppHdr + signing."
      },
      "field_xpath": {
        "type": "string",
        "description": "Optional: specific field XPath to zoom into, e.g. 'GrpHdr/MsgId', 'CdtTrfTxInf/Amt/InstdAmt'."
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["annex_b_spec", "php_code", "xml_example", "tech_doc", "claude_context", "postman_collection"]
        },
        "default": ["annex_b_spec", "php_code", "xml_example"],
        "description": "Restrict search to specific source types."
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 30,
        "default": 8
      },
      "include_code_snippets": {
        "type": "boolean",
        "default": true,
        "description": "Include PHP code snippets in evidence."
      },
      "strict_citations": {
        "type": "boolean",
        "default": true,
        "description": "If true, only return evidence with verifiable citations. Gaps reported for uncitable claims."
      }
    }
  }
}
```

### Example Invocations

**Basic — overview of pacs.008:**
```json
{
  "message_type": "pacs.008",
  "focus": "overview",
  "top_k": 10
}
```

**Specific field:**
```json
{
  "message_type": "pacs.008",
  "focus": "fields",
  "field_xpath": "CdtTrfTxInf/Amt/InstdAmt",
  "top_k": 5
}
```

**Parser code only:**
```json
{
  "message_type": "camt.056",
  "focus": "parser",
  "sources": ["php_code"],
  "top_k": 5
}
```

### Expected Output Composition

| Focus | Evidence sources |
|-------|-----------------|
| `overview` | 2-3 Annex B spec chunks + 1-2 builder code + 1-2 XML examples |
| `fields` | 3-5 Annex B field definitions (with M/O/C/R status, data types) |
| `builder` | 2-3 PHP `Messages/Pacs008CreditTransfer.php` chunks (constructor, `toXml`, `buildDocument`) |
| `parser` | 2-3 PHP `Parsers/Pacs008Parser.php` chunks (parse method, field extraction) |
| `validator` | 2-3 PHP `Validators/Pacs008Validator.php` chunks (rules, `getRules`) |
| `examples` | 2-3 XML example files from `IPS Messages Examples/pacs.008/` |
| `envelope` | AppHdr construction + XMLDSig signing + MessageEnvelope wrapping |

---

## Tool 2: `odyssey_rag.find_business_rule`

### Purpose
Search for specific validation rules, field constraints, or ISO code definitions from the Annex B specification and their implementation in Odyssey validators.

### Typical Usage
- "What are the mandatory fields for a pain.013?"
- "What validation applies to BIC fields in the AppHdr?"
- "Which fields in pacs.004 are Conditional and what are the conditions?"
- "What does rule status 'R' mean for InstrForDbtrAgt?"

### Input Schema

```json
{
  "name": "odyssey_rag.find_business_rule",
  "description": "Search for Annex B validation rules (M/O/C/R), field constraints, ISO code definitions, and their Odyssey validator implementation.",
  "inputSchema": {
    "type": "object",
    "required": [],
    "properties": {
      "message_type": {
        "type": "string",
        "description": "Filter by message type: 'pacs.008', 'camt.056', etc. Omit for cross-message search.",
        "enum": ["pacs.008", "pacs.002", "pacs.004", "pacs.028", "camt.056", "camt.029", "pain.001", "pain.002", "pain.013", "pain.014"]
      },
      "rule_status": {
        "type": "string",
        "enum": ["M", "O", "C", "R"],
        "description": "Filter by Annex B status: M=Mandatory, O=Optional, C=Conditional, R=Required (receiver may reject if missing)."
      },
      "field_xpath": {
        "type": "string",
        "description": "Search by XPath pattern, e.g. 'GrpHdr/MsgId', 'Amt/InstdAmt', 'SvcLvl/Prtry'."
      },
      "data_type": {
        "type": "string",
        "description": "Search by ISO data type: 'Max35Text', 'ISODateTime', 'BIC', 'Amount', 'ActiveCurrencyAndAmount'."
      },
      "iso_code_type": {
        "type": "string",
        "description": "Search for specific code lists: 'LocalInstrumentCode', 'PurposeCode', 'ReturnReasonCode', 'CancellationReasonCode', 'TransactionStatusCode'."
      },
      "keyword": {
        "type": "string",
        "description": "Free-text keyword search, e.g. 'CLRG', 'SENT', 'BBD', 'NbOfTxs always 1'."
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["annex_b_spec", "php_code", "tech_doc", "claude_context"]
        },
        "default": ["annex_b_spec", "php_code"],
        "description": "Restrict to spec, code, or both."
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 30,
        "default": 10
      },
      "strict_citations": {
        "type": "boolean",
        "default": true
      }
    }
  }
}
```

### Example Invocations

**All mandatory fields for pacs.008:**
```json
{
  "message_type": "pacs.008",
  "rule_status": "M",
  "top_k": 20
}
```

**Find BIC validation rules:**
```json
{
  "data_type": "BIC",
  "keyword": "4!a2!a2!c",
  "top_k": 10
}
```

**Conditional rules for camt.029:**
```json
{
  "message_type": "camt.029",
  "rule_status": "C",
  "sources": ["annex_b_spec", "php_code"],
  "top_k": 15
}
```

**Search for a specific code list:**
```json
{
  "iso_code_type": "ReturnReasonCode",
  "sources": ["php_code", "annex_b_spec"],
  "top_k": 10
}
```

### Expected Output Composition

Evidence should include:
- Annex B field definitions with M/O/C/R status, multiplicity, data type, conditions
- PHP validator `getRules()` implementations showing the actual rule enforcement
- Code enum classes (e.g. `Codes/ReturnReasonCode.php`) with `getAllCodes()`, `isValid()`
- Conditions text for "C" fields ("Conditional: required when X is present")

---

## Tool 3: `odyssey_rag.find_module`

### Purpose
Map the Odyssey/Bimpay implementation: file paths, PHP classes, key methods, tests, configs, and architectural decisions for a given module or integration area.

### Typical Usage
- "Where is the Bimpay integration implemented?"
- "What files do I touch to add a new message type?"
- "Show me the signing/envelope module"
- "Where are the Bimpay tests?"

### Input Schema

```json
{
  "name": "odyssey_rag.find_module",
  "description": "Map Odyssey implementation: file paths, PHP classes, key methods, tests, and architecture for a given module or integration area.",
  "inputSchema": {
    "type": "object",
    "required": ["module"],
    "properties": {
      "module": {
        "type": "string",
        "description": "Module path or logical area: 'Bimpay', 'Bimpay/Messages', 'Bimpay/Validators', 'AppHdr', 'XmlDSigSigner', 'ValidationEngine', 'MessageEnvelope'."
      },
      "focus": {
        "type": "string",
        "enum": ["overview", "messages", "parsers", "validators", "codes", "infrastructure", "signing", "tests", "config"],
        "default": "overview",
        "description": "Narrow focus: 'messages' = builders only, 'parsers' = parsers only, 'signing' = XMLDSig + AppHdr, 'infrastructure' = base classes + value objects."
      },
      "php_class": {
        "type": "string",
        "description": "Optional: specific class name, e.g. 'Pacs008CreditTransfer', 'ValidationEngine', 'XmlBuilder'."
      },
      "php_symbol": {
        "type": "string",
        "description": "Optional: method/function name, e.g. 'toXml', 'validate', 'buildDocument', 'wrapAndSign'."
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["php_code", "tech_doc", "claude_context", "annex_b_spec"]
        },
        "default": ["php_code", "tech_doc", "claude_context"],
        "description": "Source types to search."
      },
      "include_tests": {
        "type": "boolean",
        "default": true,
        "description": "Include test file references and patterns."
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 40,
        "default": 15
      },
      "strict_citations": {
        "type": "boolean",
        "default": true
      }
    }
  }
}
```

### Extended Output: `module_map`

In addition to the standard `evidence[]`, this tool returns a structured map:

```json
{
  "module_map": {
    "entrypoints": [
      {"path": "Bimpay/Bimpay.php", "why": "Main API: createMessage, parseMessage, validateMessage"}
    ],
    "key_files": [
      {"path": "Bimpay/Messages/Pacs008CreditTransfer.php", "class": "Pacs008CreditTransfer", "why": "pacs.008 builder"},
      {"path": "Bimpay/Parsers/Pacs008Parser.php", "class": "Pacs008Parser", "why": "pacs.008 XML parser"},
      {"path": "Bimpay/Validators/Pacs008Validator.php", "class": "Pacs008Validator", "why": "pacs.008 validation rules"}
    ],
    "infrastructure": [
      {"path": "Bimpay/BaseMessage.php", "class": "BaseMessage", "why": "Abstract base: getRules, toXml, buildDocument"},
      {"path": "Bimpay/ValidationEngine.php", "class": "ValidationEngine", "why": "M/O/C/R rule enforcement"},
      {"path": "Bimpay/XmlBuilder.php", "class": "XmlBuilder", "why": "Safe XML construction"},
      {"path": "Bimpay/MessageEnvelope.php", "class": "MessageEnvelope", "why": "Montran envelope wrapping"},
      {"path": "Bimpay/XmlDSigSigner.php", "class": "XmlDSigSigner", "why": "XMLDSig RSA-SHA256 signing"}
    ],
    "value_objects": [
      {"path": "Bimpay/Amount.php", "class": "Amount", "why": "Monetary amount (string-based, 2 decimal, ISO 4217)"},
      {"path": "Bimpay/BicIdentifier.php", "class": "BicIdentifier", "why": "BIC validation (8/11 chars)"},
      {"path": "Bimpay/IsoDateTime.php", "class": "IsoDateTime", "why": "ISO 8601 datetime"},
      {"path": "Bimpay/MaxText.php", "class": "MaxText", "why": "Max-length text (max35, max140, max105, max2048)"}
    ],
    "code_enums": [
      {"path": "Bimpay/Codes/TransactionStatusCode.php", "why": "RJCT, ACSP, PDNG, ACCC, ACSC"},
      {"path": "Bimpay/Codes/ReturnReasonCode.php", "why": "AC03, AM04, MD07, etc."},
      {"path": "Bimpay/Codes/CancellationReasonCode.php", "why": "DUPL, FRAD, TECH, etc."}
    ],
    "tests": [
      {"path": "app/test/unit/banking/Bimpay/", "why": "271 tests, 16 files"}
    ],
    "related_docs": [
      {"source": "BIMPAY_TECHNICAL_DOC.md", "what": "Layer architecture, outbound/inbound flow"},
      {"source": "BIMPAY_INFRASTRUCTURE_DOC.md", "what": "Value objects, validation engine design"}
    ]
  }
}
```

### Example Invocations

**Full Bimpay overview:**
```json
{
  "module": "Bimpay",
  "focus": "overview",
  "top_k": 20
}
```

**Signing module deep dive:**
```json
{
  "module": "Bimpay",
  "focus": "signing",
  "php_class": "XmlDSigSigner",
  "top_k": 10
}
```

**Specific method:**
```json
{
  "module": "Bimpay/Messages",
  "php_symbol": "buildDocument",
  "top_k": 10
}
```

---

## Tool 4: `odyssey_rag.find_error`

### Purpose
Troubleshoot errors using ISO 20022 status codes (`TxSts`: RJCT, ACSP, PDNG), reason codes (AC03, AM04, FF01, MD07), and Odyssey error handling patterns.

### Typical Usage
- "What does TxSts RJCT with reason AC03 mean?"
- "Where do we handle FF01 XSD validation failures?"
- "What are all the possible ReturnReasonCodes?"
- "How does Odyssey handle a pacs.002 with RJCT status?"

### Input Schema

```json
{
  "name": "odyssey_rag.find_error",
  "description": "Troubleshoot ISO 20022 errors: transaction status codes (RJCT/ACSP/PDNG), reason codes (AC03/FF01/AM04), and Odyssey error handling implementation.",
  "inputSchema": {
    "type": "object",
    "required": [],
    "properties": {
      "iso_status": {
        "type": "string",
        "description": "ISO 20022 transaction status: 'RJCT' (rejected), 'ACSP' (accepted settlement in process), 'PDNG' (pending), 'ACCC' (accepted credit), 'ACSC' (accepted settlement completed).",
        "enum": ["RJCT", "ACSP", "PDNG", "ACCC", "ACSC", "ACTC", "RCVD"]
      },
      "reason_code": {
        "type": "string",
        "description": "ISO reason code: 'AC03' (invalid account), 'AM04' (insufficient funds), 'FF01' (invalid format/XSD), 'MD07' (deceased), 'DUPL' (duplicate), 'FRAD' (fraud), 'TECH' (technical), etc."
      },
      "code_type": {
        "type": "string",
        "enum": ["TransactionStatusCode", "ReturnReasonCode", "CancellationReasonCode", "DenialOfCancellationCode", "RejectReasonCode"],
        "description": "Which code list to search in."
      },
      "message_type_hint": {
        "type": "string",
        "description": "Optional: which message type context, e.g. 'pacs.002' (status report), 'camt.029' (denial), 'pacs.004' (return).",
        "enum": ["pacs.008", "pacs.002", "pacs.004", "pacs.028", "camt.056", "camt.029", "pain.001", "pain.002", "pain.013", "pain.014"]
      },
      "error_fragment": {
        "type": "string",
        "description": "Free text: error message, log fragment, or description to search literally."
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["annex_b_spec", "php_code", "tech_doc", "claude_context", "xml_example"]
        },
        "default": ["annex_b_spec", "php_code", "tech_doc"],
        "description": "Source types to search."
      },
      "include_resolution": {
        "type": "boolean",
        "default": true,
        "description": "Include probable causes, checks, and fix steps."
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 30,
        "default": 10
      },
      "strict_citations": {
        "type": "boolean",
        "default": true
      }
    }
  }
}
```

### Extended Output: `resolution`

When `include_resolution=true`:

```json
{
  "resolution": {
    "status_meaning": "RJCT = Transaction rejected by the IPS or receiving participant",
    "reason_meaning": "FF01 = Invalid file format: message failed XSD schema validation",
    "probable_causes": [
      "XML does not conform to pacs.008.001.12 schema",
      "Missing mandatory field (GrpHdr/MsgId, NbOfTxs, etc.)",
      "Invalid namespace URI",
      "Character encoding issue (non-UTF-8)"
    ],
    "checks": [
      "Run XmlSchemaValidator::validateOrFail() locally with the exact XML",
      "Check AppHdr MsgDefIdr matches the document body namespace",
      "Verify all M-status fields are present per Annex B"
    ],
    "fix_steps": [
      "Compare XML against golden file in goldenFiles/banking/Bimpay/",
      "Validate with XSD from iso20022.org",
      "Check BaseMessage::toXml() output for the specific message type"
    ],
    "odyssey_touchpoints": [
      {"path": "Bimpay/XmlSchemaValidator.php", "what": "XSD validation, throws on FF01"},
      {"path": "Bimpay/Validators/Pacs008Validator.php", "what": "Business rule validation before XSD"},
      {"path": "Bimpay/Bimpay.php", "what": "executeHttpPostWithRetry — handles response status"}
    ]
  }
}
```

### Example Invocations

**RJCT with reason code:**
```json
{
  "iso_status": "RJCT",
  "reason_code": "FF01",
  "message_type_hint": "pacs.002",
  "top_k": 10
}
```

**Search all return reason codes:**
```json
{
  "code_type": "ReturnReasonCode",
  "top_k": 15
}
```

**Free-text error search:**
```json
{
  "error_fragment": "signature mismatch",
  "sources": ["php_code", "tech_doc"],
  "top_k": 8
}
```

---

## Tool 5: `odyssey_rag.search`

### Purpose
Free-text semantic search across all indexed sources. Fallback when domain-specific tools don't cover the query.

### Input Schema

```json
{
  "name": "odyssey_rag.search",
  "description": "Free-text semantic search across all indexed Odyssey/Bimpay/IPS documentation and code. Use when domain-specific tools don't cover the query.",
  "inputSchema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language query, e.g. 'How does the polling service work?', 'What is the Montran envelope format?'."
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["annex_b_spec", "php_code", "xml_example", "tech_doc", "claude_context", "postman_collection", "pdf_doc", "generic_text"]
        },
        "description": "Optional: restrict to specific source types."
      },
      "message_type": {
        "type": "string",
        "description": "Optional: filter by message type."
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 30,
        "default": 8
      },
      "strict_citations": {
        "type": "boolean",
        "default": true
      }
    }
  }
}
```

### Example

```json
{
  "query": "How does the Bimpay poller service poll IPS for incoming messages via mTLS?",
  "sources": ["tech_doc", "claude_context"],
  "top_k": 8
}
```

---

## Tool 6: `odyssey_rag.ingest`

### Purpose
Feed new documents into the RAG knowledge base. Used to add new documentation, code snapshots, or PDFs as they become available.

### Input Schema

```json
{
  "name": "odyssey_rag.ingest",
  "description": "Ingest new documents into the Odyssey RAG knowledge base. Supports Markdown, PHP code, XML examples, PDFs, and Postman collections.",
  "inputSchema": {
    "type": "object",
    "required": ["source"],
    "properties": {
      "source": {
        "type": "string",
        "description": "Path to file or directory to ingest (relative to data/sources/ mount point), e.g. 'new-feature-spec.md', 'bimpay-v2/' directory."
      },
      "source_type": {
        "type": "string",
        "enum": ["annex_b_spec", "tech_doc", "claude_context", "php_code", "xml_example", "postman_collection", "pdf_doc", "generic_text"],
        "description": "Override auto-detection of source type."
      },
      "metadata_overrides": {
        "type": "object",
        "description": "Additional metadata to attach to all chunks from this source.",
        "properties": {
          "message_type": {"type": "string"},
          "doc_version": {"type": "string"},
          "integration": {"type": "string", "description": "Integration name, e.g. 'bimpay', 'future_integration'"},
          "is_current": {"type": "boolean", "default": true}
        }
      },
      "replace_existing": {
        "type": "boolean",
        "default": false,
        "description": "If true, delete existing chunks for this source before re-ingesting."
      }
    }
  }
}
```

### Output

```json
{
  "status": "completed",
  "source": "new-feature-spec.md",
  "chunks_created": 42,
  "source_type_detected": "tech_doc",
  "metadata_applied": {
    "integration": "bimpay",
    "doc_version": "2.0",
    "is_current": true
  },
  "errors": []
}
```

### Example Invocations

**Ingest a new PDF:**
```json
{
  "source": "IPS_Specification_v2.pdf",
  "source_type": "pdf_doc",
  "metadata_overrides": {
    "doc_version": "2.0",
    "integration": "bimpay"
  }
}
```

**Re-ingest updated code:**
```json
{
  "source": "bimpay-code-snapshot/",
  "source_type": "php_code",
  "replace_existing": true,
  "metadata_overrides": {
    "integration": "bimpay"
  }
}
```

**Ingest a new integration's docs:**
```json
{
  "source": "new-payment-gateway/",
  "metadata_overrides": {
    "integration": "payment_gateway_v1",
    "doc_version": "1.0"
  }
}
```

---

## Agent Workflow Pattern

When an AI agent needs to implement a feature or debug an issue, the recommended tool chain is:

```
1. odyssey_rag.find_module
   └─ Understand the codebase: entry points, patterns, related tests

2. odyssey_rag.find_message_type
   └─ Get the spec: fields, builder pattern, XML structure, examples

3. odyssey_rag.find_business_rule
   └─ Get validation details: M/O/C/R rules, code lists, constraints

4. odyssey_rag.find_error (if debugging)
   └─ Understand the error: status code meaning, handler location, fix steps

5. odyssey_rag.search (if needed)
   └─ Catch-all for queries not covered by domain tools

6. Implement the change, citing evidence from steps 1-5
```

---

## VS Code Integration

### `.vscode/mcp.json` (shared in repo)

Uses **streamable HTTP transport** (MCP 2025-03-26 spec):

```json
{
  "servers": {
    "odyssey-rag": {
      "type": "http",
      "url": "http://localhost:3010/mcp/",
      "headers": {
        "Authorization": "Bearer ${input:mcp_token}"
      }
    }
  },
  "inputs": [
    {
      "id": "mcp_token",
      "type": "promptString",
      "description": "MCP auth token (from Admin UI → Tokens page)",
      "password": true
    }
  ]
}
```

**Notes**:
- Transport is `type: "http"` (streamable HTTP, NOT legacy SSE)
- Endpoint requires trailing slash: `/mcp/`
- Token is created in the Admin UI at `/tokens`
- VS Code prompts for the token on first connection
