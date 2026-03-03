"""Handler for oddysey_rag.find_error MCP tool.

Troubleshoots ISO 20022 errors using transaction status codes (RJCT/ACSP/PDNG),
reason codes (AC03/FF01/AM04), and Odyssey error handling patterns.

Returns standard evidence + extended ``resolution`` with actionable guidance.
"""

from __future__ import annotations

from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.mcp_server.tools._output import to_mcp_output

# ISO 20022 transaction status descriptions
_STATUS_MEANINGS: dict[str, str] = {
    "RJCT": "Transaction rejected by the IPS or receiving participant",
    "ACSP": "Accepted settlement in process",
    "PDNG": "Pending — awaiting further instruction or confirmation",
    "ACCC": "Accepted credit completed — funds credited to beneficiary account",
    "ACSC": "Accepted settlement completed — debtor account debited",
    "ACTC": "Accepted technical validation — technical checks passed",
    "RCVD": "Received — payment order received by the agent",
}

# Common ISO reason code descriptions
_REASON_MEANINGS: dict[str, str] = {
    "AC03": "Invalid creditor account number",
    "AC04": "Closed account number",
    "AM04": "Insufficient funds",
    "FF01": "Invalid file format / message failed XSD schema validation",
    "MD07": "End customer is deceased",
    "DUPL": "Duplicate payment",
    "FRAD": "Fraudulent origin",
    "TECH": "Technical problem",
    "MS03": "Not specified reason — agent to agent",
    "NARR": "Narrative — see additional information",
    "RR04": "Regulatory reason",
    "BE04": "Missing creditor address",
    "AG01": "Transaction forbidden on this account",
}


def _build_resolution(
    iso_status: str | None,
    reason_code: str | None,
    response,
) -> dict:
    """Build a structured resolution guide from known codes and evidence."""
    resolution: dict = {}

    if iso_status:
        resolution["status_meaning"] = (
            f"{iso_status} = {_STATUS_MEANINGS.get(iso_status, 'See ISO 20022 code set')}"
        )
    if reason_code:
        resolution["reason_meaning"] = (
            f"{reason_code} = {_REASON_MEANINGS.get(reason_code, 'See ISO 20022 reason code set')}"
        )

    # Derive Odyssey touchpoints from citations in evidence
    touchpoints: list[dict] = []
    seen_paths: set[str] = set()
    for item in response.evidence:
        for citation in item.citations:
            if citation.source_path and citation.source_path not in seen_paths:
                seen_paths.add(citation.source_path)
                touchpoints.append(
                    {
                        "path": citation.source_path,
                        "section": citation.section or "",
                    }
                )
    if touchpoints:
        resolution["odyssey_touchpoints"] = touchpoints

    return resolution


async def find_error_handler(
    iso_status: str | None = None,
    reason_code: str | None = None,
    code_type: str | None = None,
    message_type_hint: str | None = None,
    error_fragment: str | None = None,
    top_k: int = 10,
) -> dict:
    """Return evidence and resolution for an ISO 20022 error."""
    engine = get_retrieval_engine()

    parts: list[str] = []
    if iso_status:
        parts.append(iso_status)
        parts.append(_STATUS_MEANINGS.get(iso_status, ""))
    if reason_code:
        parts.append(reason_code)
        parts.append(_REASON_MEANINGS.get(reason_code, ""))
    if code_type:
        parts.append(code_type)
    if message_type_hint:
        parts.append(message_type_hint)
    if error_fragment:
        parts.append(error_fragment)
    if not parts:
        parts.append("error handling status codes reason codes")
    query = " ".join(p for p in parts if p)

    tool_context: dict[str, str] = {"focus": "validator"}
    if message_type_hint:
        tool_context["message_type"] = message_type_hint
    if iso_status:
        tool_context["iso_status"] = iso_status
    if reason_code:
        tool_context["reason_code"] = reason_code

    response = await engine.search(
        query,
        tool_name="find_error",
        tool_context=tool_context,
    )

    output = to_mcp_output(response)
    output["resolution"] = _build_resolution(iso_status, reason_code, response)
    return output
