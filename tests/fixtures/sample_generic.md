# BIMPAY Technical Documentation

## Overview

BIMPAY implements the IPS (Instant Payment System) protocol for real-time interbank transfers.
The system supports multiple ISO 20022 message types including pacs.008 credit transfers and
pacs.002 payment status reports.

## Architecture

The payment engine is composed of three main modules:

- **MessageValidator**: validates incoming XML against XSD schemas
- **MessageRouter**: routes messages to appropriate processing queues
- **MessageStore**: persists message history for audit and reconciliation

Each module communicates via an internal event bus.

## Processing Flow

When a pacs.008 FIToFICstmrCdtTrf message arrives:

1. XML signature is verified
2. Message structure is validated against pacs.008.001.12 schema
3. Duplicate detection runs (UETR check)
4. Settlement information is extracted
5. Message is forwarded to clearing system
6. A pacs.002 status report is returned to the originator

## Error Handling

If processing fails at any step:

- The error is logged with the original message ID
- A pacs.002 RJCT (rejected) status report is generated
- The originator receives notification within 10 seconds

## Settlement

Settlement uses the IPS clearing system with code `CLRG`. Settlement date is always
the same business day for messages received before the cut-off time of 17:00 CET.
