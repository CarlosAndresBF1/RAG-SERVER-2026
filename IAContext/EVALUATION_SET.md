# Odyssey RAG — Evaluation Set

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §8, [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3

---

## 1. Purpose

This evaluation set contains 60+ domain questions used to measure RAG retrieval quality. Each question has expected answers and scoring criteria. The set is used in automated evaluation tests and manual quality reviews.

---

## 2. Evaluation Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| **Precision@5** | Relevant results in top 5 / 5 | ≥ 0.70 |
| **Recall@10** | Expected sources found in top 10 / total expected | ≥ 0.80 |
| **MRR** (Mean Reciprocal Rank) | 1/rank of first relevant result, averaged | ≥ 0.75 |
| **Gap Accuracy** | Correct gap detection / total gap cases | ≥ 0.60 |
| **Source Coverage** | % of source types that return results | 100% |

---

## 3. Question Categories

### 3.1 Message Type Questions (find_message_type)

```json
[
  {
    "id": "MT-01",
    "tool": "find_message_type",
    "query": "What are the mandatory fields in pacs.008 Group Header?",
    "params": {"message_type": "pacs.008", "focus": "fields"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["MsgId", "CreDtTm", "NbOfTxs", "SttlmInf"],
    "expected_message_type": "pacs.008"
  },
  {
    "id": "MT-02",
    "tool": "find_message_type",
    "query": "Give me an overview of camt.056 recall message",
    "params": {"message_type": "camt.056", "focus": "overview"},
    "expected_sources": ["annex_b_spec", "tech_doc"],
    "expected_content": ["FIToFIPmtCxlReq", "recall", "cancellation"],
    "expected_message_type": "camt.056"
  },
  {
    "id": "MT-03",
    "tool": "find_message_type",
    "query": "How is the pacs.004 return message structured?",
    "params": {"message_type": "pacs.004", "focus": "overview"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["PmtRtr", "return", "original transaction"],
    "expected_message_type": "pacs.004"
  },
  {
    "id": "MT-04",
    "tool": "find_message_type",
    "query": "What XML envelope is used for pain.001?",
    "params": {"message_type": "pain.001", "focus": "envelope"},
    "expected_sources": ["annex_b_spec", "xml_example"],
    "expected_content": ["AppHdr", "CstmrCdtTrfInitn", "BizMsgIdr"],
    "expected_message_type": "pain.001"
  },
  {
    "id": "MT-05",
    "tool": "find_message_type",
    "query": "Show me an example XML for pacs.008",
    "params": {"message_type": "pacs.008", "focus": "examples"},
    "expected_sources": ["xml_example"],
    "expected_content": ["<FIToFICstmrCdtTrf>", "<GrpHdr>"],
    "expected_message_type": "pacs.008"
  },
  {
    "id": "MT-06",
    "tool": "find_message_type",
    "query": "What is the pacs.028 investigation request?",
    "params": {"message_type": "pacs.028", "focus": "overview"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["FIToFIPmtStsReq", "status", "investigation"],
    "expected_message_type": "pacs.028"
  },
  {
    "id": "MT-07",
    "tool": "find_message_type",
    "query": "What fields are in pain.013 Request to Pay?",
    "params": {"message_type": "pain.013", "focus": "fields"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["CdtrPmtActvtnReq", "creditor", "amount"],
    "expected_message_type": "pain.013"
  },
  {
    "id": "MT-08",
    "tool": "find_message_type",
    "query": "Describe the pain.014 response message",
    "params": {"message_type": "pain.014", "focus": "overview"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["CdtrPmtActvtnReqStsRpt", "acceptance", "rejection"],
    "expected_message_type": "pain.014"
  },
  {
    "id": "MT-09",
    "tool": "find_message_type",
    "query": "What is the camt.029 resolution of investigation?",
    "params": {"message_type": "camt.029", "focus": "overview"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["RsltnOfInvstgtn", "negative answer", "investigation"],
    "expected_message_type": "camt.029"
  },
  {
    "id": "MT-10",
    "tool": "find_message_type",
    "query": "How is pacs.002 status report structured?",
    "params": {"message_type": "pacs.002", "focus": "fields"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["FIToFIPmtStsRpt", "TxInfAndSts", "StsId"],
    "expected_message_type": "pacs.002"
  }
]
```

### 3.2 Business Rule Questions (find_business_rule)

```json
[
  {
    "id": "BR-01",
    "tool": "find_business_rule",
    "query": "Which fields are mandatory in pacs.008?",
    "params": {"message_type": "pacs.008", "rule_status": "M"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["MsgId", "[1..1]", "M"],
    "notes": "Should return field table rows with M status"
  },
  {
    "id": "BR-02",
    "tool": "find_business_rule",
    "query": "What are the conditional fields in camt.056?",
    "params": {"message_type": "camt.056", "rule_status": "C"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["C", "conditional"]
  },
  {
    "id": "BR-03",
    "tool": "find_business_rule",
    "query": "What data type is the Amount field in pacs.008?",
    "params": {"message_type": "pacs.008"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["ActiveCurrencyAndAmount", "IntrBkSttlmAmt"]
  },
  {
    "id": "BR-04",
    "tool": "find_business_rule",
    "query": "What is the multiplicity of CdtTrfTxInf in pacs.008?",
    "params": {"message_type": "pacs.008"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["[1..n]", "CdtTrfTxInf"]
  },
  {
    "id": "BR-05",
    "tool": "find_business_rule",
    "query": "What ISO code list is used for rejection reasons?",
    "params": {},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["ExternalPaymentTransactionStatus", "RJCT", "reason code"]
  },
  {
    "id": "BR-06",
    "tool": "find_business_rule",
    "query": "What XPath is the debtor BIC in pacs.008?",
    "params": {"message_type": "pacs.008"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["DbtrAgt", "BIC", "BICFI"]
  },
  {
    "id": "BR-07",
    "tool": "find_business_rule",
    "query": "What fields are optional in pain.001?",
    "params": {"message_type": "pain.001", "rule_status": "O"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["O", "optional"]
  },
  {
    "id": "BR-08",
    "tool": "find_business_rule",
    "query": "What are the settlement method options in pacs.008?",
    "params": {"message_type": "pacs.008"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["SttlmMtd", "CLRG", "settlement"]
  },
  {
    "id": "BR-09",
    "tool": "find_business_rule",
    "query": "What is the maximum length of MsgId?",
    "params": {},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["Max35Text", "35", "MsgId"]
  },
  {
    "id": "BR-10",
    "tool": "find_business_rule",
    "query": "What are the required fields in AppHdr?",
    "params": {},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["Fr", "To", "BizMsgIdr", "MsgDefIdr", "CreDt"]
  }
]
```

### 3.3 Module Questions (find_module)

```json
[
  {
    "id": "MOD-01",
    "tool": "find_module",
    "query": "Which PHP class builds pacs.008 messages?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["Pacs008CreditTransfer", "buildDocument"],
    "expected_file": "Bimpay/Messages/Pacs008CreditTransfer.php"
  },
  {
    "id": "MOD-02",
    "tool": "find_module",
    "query": "How does the camt.056 recall parser work?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["Camt056", "parse"],
    "expected_file": "Bimpay/Parsers/"
  },
  {
    "id": "MOD-03",
    "tool": "find_module",
    "query": "Where is the XML digital signature implemented?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["XmlDSigSigner", "sign"],
    "expected_file": "Bimpay/XmlDSigSigner.php"
  },
  {
    "id": "MOD-04",
    "tool": "find_module",
    "query": "How does validation work for ISO messages?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["ValidationEngine", "validate", "ValidationResult"],
    "expected_file": "Bimpay/ValidationEngine.php"
  },
  {
    "id": "MOD-05",
    "tool": "find_module",
    "query": "What class handles the message envelope?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["MessageEnvelope", "AppHdr"],
    "expected_file": "Bimpay/MessageEnvelope.php"
  },
  {
    "id": "MOD-06",
    "tool": "find_module",
    "query": "Where are the XSD schemas loaded?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["XmlSchemaValidator", "schema"],
    "expected_file": "Bimpay/XmlSchemaValidator.php"
  },
  {
    "id": "MOD-07",
    "tool": "find_module",
    "query": "How is the BIC identifier validated?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["BicIdentifier", "validate", "format"],
    "expected_file": "Bimpay/BicIdentifier.php"
  },
  {
    "id": "MOD-08",
    "tool": "find_module",
    "query": "What tests exist for pacs.008?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["test-bimpay-pacs008", "assert"],
    "expected_file": "TestingBimpayClass/test-bimpay-pacs008"
  },
  {
    "id": "MOD-09",
    "tool": "find_module",
    "query": "How does the Amount class work?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["Amount", "currency", "value"],
    "expected_file": "Bimpay/Amount.php"
  },
  {
    "id": "MOD-10",
    "tool": "find_module",
    "query": "How is XML building done for ISO messages?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["XmlBuilder", "createElement", "DOMDocument"],
    "expected_file": "Bimpay/XmlBuilder.php"
  }
]
```

### 3.4 Error Questions (find_error)

```json
[
  {
    "id": "ERR-01",
    "tool": "find_error",
    "query": "What does RJCT status mean in pacs.002?",
    "params": {"status_code": "RJCT"},
    "expected_sources": ["annex_b_spec", "php_code"],
    "expected_content": ["Rejected", "RJCT", "reason code"]
  },
  {
    "id": "ERR-02",
    "tool": "find_error",
    "query": "What is reason code AC03?",
    "params": {"reason_code": "AC03"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["AC03", "InvalidCreditorAccountNumber", "account"]
  },
  {
    "id": "ERR-03",
    "tool": "find_error",
    "query": "How do I handle an AM04 insufficient funds rejection?",
    "params": {"reason_code": "AM04"},
    "expected_sources": ["annex_b_spec", "php_code"],
    "expected_content": ["AM04", "InsufficientFunds", "amount"]
  },
  {
    "id": "ERR-04",
    "tool": "find_error",
    "query": "What does ACSP status mean?",
    "params": {"status_code": "ACSP"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["AcceptedSettlementInProcess", "accepted", "processing"]
  },
  {
    "id": "ERR-05",
    "tool": "find_error",
    "query": "What is the FF01 invalid file format error?",
    "params": {"reason_code": "FF01"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["FF01", "InvalidFileFormat", "format"]
  },
  {
    "id": "ERR-06",
    "tool": "find_error",
    "query": "How to fix a PDNG pending status?",
    "params": {"status_code": "PDNG"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["Pending", "PDNG", "investigation"]
  },
  {
    "id": "ERR-07",
    "tool": "find_error",
    "query": "What happens when schema validation fails?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["XmlSchemaValidator", "validation", "error"]
  },
  {
    "id": "ERR-08",
    "tool": "find_error",
    "query": "What does DT01 invalid date error mean?",
    "params": {"reason_code": "DT01"},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["DT01", "InvalidDate", "date"]
  }
]
```

### 3.5 Free-Text Search Questions (search)

```json
[
  {
    "id": "FT-01",
    "tool": "search",
    "query": "How does Bimpay process instant payments?",
    "params": {},
    "expected_sources": ["tech_doc", "php_code"],
    "expected_content": ["payment", "process", "Bimpay"]
  },
  {
    "id": "FT-02",
    "tool": "search",
    "query": "What is the Odyssey project architecture?",
    "params": {},
    "expected_sources": ["tech_doc", "claude_context"],
    "expected_content": ["Odyssey", "architecture"]
  },
  {
    "id": "FT-03",
    "tool": "search",
    "query": "How is the Bimpay Docker infrastructure set up?",
    "params": {},
    "expected_sources": ["tech_doc"],
    "expected_content": ["Docker", "compose", "container"]
  },
  {
    "id": "FT-04",
    "tool": "search",
    "query": "What Postman endpoints are available for testing?",
    "params": {},
    "expected_sources": ["postman_collection"],
    "expected_content": ["POST", "endpoint", "request"]
  },
  {
    "id": "FT-05",
    "tool": "search",
    "query": "How do I add a new ISO message type to Bimpay?",
    "params": {},
    "expected_sources": ["php_code", "tech_doc"],
    "expected_content": ["BaseMessage", "extends", "register"]
  },
  {
    "id": "FT-06",
    "tool": "search",
    "query": "What is the difference between pacs.008 and pain.001?",
    "params": {},
    "expected_sources": ["annex_b_spec"],
    "expected_content": ["pacs.008", "pain.001", "credit transfer", "initiation"]
  },
  {
    "id": "FT-07",
    "tool": "search",
    "query": "How are XML namespaces handled?",
    "params": {},
    "expected_sources": ["php_code"],
    "expected_content": ["XmlNamespaces", "namespace", "URI"]
  }
]
```

### 3.6 Cross-Domain Questions (multi-tool scenarios)

```json
[
  {
    "id": "XD-01",
    "description": "Full message implementation workflow",
    "steps": [
      {"tool": "find_message_type", "query": "pacs.008 overview", "params": {"message_type": "pacs.008"}},
      {"tool": "find_business_rule", "query": "mandatory fields pacs.008", "params": {"message_type": "pacs.008"}},
      {"tool": "find_module", "query": "pacs.008 builder class", "params": {}},
      {"tool": "find_module", "query": "pacs.008 tests", "params": {}}
    ],
    "expected": "All 4 steps should return relevant results with consistent pacs.008 context"
  },
  {
    "id": "XD-02",
    "description": "Error investigation workflow",
    "steps": [
      {"tool": "find_error", "query": "RJCT AC03", "params": {"status_code": "RJCT", "reason_code": "AC03"}},
      {"tool": "find_message_type", "query": "pacs.002 status report", "params": {"message_type": "pacs.002"}},
      {"tool": "find_module", "query": "status report handler", "params": {}}
    ],
    "expected": "Should trace from error → message type → implementation"
  },
  {
    "id": "XD-03",
    "description": "Recall message full context",
    "steps": [
      {"tool": "find_message_type", "query": "camt.056 recall", "params": {"message_type": "camt.056"}},
      {"tool": "find_business_rule", "query": "camt.056 mandatory fields", "params": {"message_type": "camt.056"}},
      {"tool": "find_message_type", "query": "camt.029 resolution", "params": {"message_type": "camt.029"}},
      {"tool": "find_module", "query": "recall implementation", "params": {}}
    ],
    "expected": "Should cover recall request → rules → response → implementation"
  }
]
```

---

## 4. Automated Evaluation Runner

```python
# tests/evaluation/test_evaluation_suite.py
import json
import pytest
from pathlib import Path

@pytest.fixture(scope="module")
def questions():
    path = Path(__file__).parent / "evaluation_questions.json"
    return json.loads(path.read_text())

@pytest.mark.evaluation
class TestEvaluationSuite:
    async def test_precision_at_5(self, questions, retrieval_engine):
        """Average Precision@5 across all questions should be ≥ 0.70."""
        precisions = []
        for q in questions:
            results = await retrieval_engine.search(q["query"], q.get("params", {}))
            relevant = sum(
                1 for e in results.evidence[:5]
                if e.source_type in q["expected_sources"]
            )
            precisions.append(relevant / 5)
        avg_precision = sum(precisions) / len(precisions)
        assert avg_precision >= 0.70, f"Precision@5 = {avg_precision:.2f} (target ≥ 0.70)"

    async def test_recall_at_10(self, questions, retrieval_engine):
        """Average Recall@10 should be ≥ 0.80."""
        recalls = []
        for q in questions:
            results = await retrieval_engine.search(q["query"], q.get("params", {}))
            found_sources = {e.source_type for e in results.evidence[:10]}
            expected = set(q["expected_sources"])
            recall = len(found_sources & expected) / len(expected) if expected else 1.0
            recalls.append(recall)
        avg_recall = sum(recalls) / len(recalls)
        assert avg_recall >= 0.80, f"Recall@10 = {avg_recall:.2f} (target ≥ 0.80)"

    async def test_mrr(self, questions, retrieval_engine):
        """Mean Reciprocal Rank should be ≥ 0.75."""
        rrs = []
        for q in questions:
            results = await retrieval_engine.search(q["query"], q.get("params", {}))
            rr = 0.0
            for rank, e in enumerate(results.evidence, 1):
                if any(kw.lower() in e.text.lower() for kw in q["expected_content"]):
                    rr = 1.0 / rank
                    break
            rrs.append(rr)
        mrr = sum(rrs) / len(rrs)
        assert mrr >= 0.75, f"MRR = {mrr:.2f} (target ≥ 0.75)"

    async def test_content_match(self, questions, retrieval_engine):
        """At least one expected keyword should appear in top-5 results for each question."""
        misses = []
        for q in questions:
            results = await retrieval_engine.search(q["query"], q.get("params", {}))
            top5_text = " ".join(e.text for e in results.evidence[:5]).lower()
            found = any(kw.lower() in top5_text for kw in q["expected_content"])
            if not found:
                misses.append(q["id"])
        miss_rate = len(misses) / len(questions)
        assert miss_rate <= 0.20, f"Content miss rate: {miss_rate:.0%}. Misses: {misses}"
```

---

## 5. Evaluation Report

After running `pytest tests/evaluation/ -v`, a report is generated:

```
═══ EVALUATION REPORT ═══
Date: 2026-03-XX
Questions: 60

Precision@5:  0.XX (target ≥ 0.70) ✓/✗
Recall@10:    0.XX (target ≥ 0.80) ✓/✗
MRR:          0.XX (target ≥ 0.75) ✓/✗
Content Match: XX% (target ≥ 80%) ✓/✗

Weak categories:
 - ERR-XX: ...
 - BR-XX: ...

Recommendations:
 - ...
═══════════════════════════
```
