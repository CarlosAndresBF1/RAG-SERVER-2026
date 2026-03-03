# IPS Annex B — Message Specifications

## pacs.008.001.12 — FI-to-FI Customer Credit Transfer

The pacs.008 message type implements the FI-to-FI Customer Credit Transfer (FIToFICstmrCdtTrf).
This is the primary payment instruction in the IPS network, version pacs.008.001.12.

### Group Header (GrpHdr)

The Group Header contains information common to all pacs.008 transactions.

| XPath | Tag | Mult | Status | Type | Description |
|-------|-----|------|--------|------|-------------|
| GrpHdr/MsgId | <MsgId> | [1..1] | M | Max35Text | Unique message identification assigned by the instructing party. |
| GrpHdr/CreDtTm | <CreDtTm> | [1..1] | M | ISODateTime | Date and time at which the message was created. |
| GrpHdr/NbOfTxs | <NbOfTxs> | [1..1] | M | Max15NumericText | Number of individual transactions contained in the message. |
| GrpHdr/SttlmInf | <SttlmInf> | [1..1] | M | SettlementInstruction13 | Specifies the details on how the settlement of the transaction(s) is to be completed. |

### Credit Transfer Transaction Information (CdtTrfTxInf)

Each pacs.008 credit transfer must contain at least one CdtTrfTxInf block.

| XPath | Tag | Mult | Status | Type | Description |
|-------|-----|------|--------|------|-------------|
| CdtTrfTxInf/PmtId | <PmtId> | [1..1] | M | PaymentIdentification7 | Set of elements used to reference a payment instruction. |
| CdtTrfTxInf/IntrBkSttlmAmt | <IntrBkSttlmAmt> | [1..1] | M | ActiveCurrencyAndAmount | Amount of money moved between the instructing agent and the instructed agent. |
| CdtTrfTxInf/Dbtr | <Dbtr> | [1..1] | M | PartyIdentification135 | Party that owes an amount of money to the (ultimate) creditor. |
| CdtTrfTxInf/Cdtr | <Cdtr> | [1..1] | M | PartyIdentification135 | Party to which an amount of money is due. |
| CdtTrfTxInf/Purp | <Purp> | [0..1] | O | Purpose2Choice | Underlying reason for the payment transaction. |

## pacs.002.001.14 — FI-to-FI Payment Status Report

The pacs.002 message type provides the FIToFIPmtStsRpt (Payment Status Report).
It is returned in response to pacs.008 to acknowledge receipt or rejection.

### Original Group Information (OrgnlGrpInf)

References the original pacs.002 message being reported on.

| XPath | Tag | Mult | Status | Type | Description |
|-------|-----|------|--------|------|-------------|
| OrgnlGrpInf/OrgnlMsgId | <OrgnlMsgId> | [1..1] | M | Max35Text | Point-to-point reference, as assigned by the original instructing party. |
| OrgnlGrpInf/OrgnlMsgNmId | <OrgnlMsgNmId> | [1..1] | M | Max35Text | Specifies the original message name identifier to pacs.002.001.14. |
