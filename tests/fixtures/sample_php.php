<?php

namespace Bimpay\Messages;

/**
 * Pacs008CreditTransfer — builds pacs.008 FI-to-FI Customer Credit Transfer XML.
 *
 * @package Bimpay\Messages
 */
class Pacs008CreditTransfer extends BaseMessage
{
    const MESSAGE_TYPE = 'pacs.008.001.12';
    const NAMESPACE = 'urn:iso:std:iso:20022:tech:xsd:pacs.008.001.12';

    protected string $msgId;
    protected \DateTimeImmutable $creDtTm;
    protected array $transactions = [];

    /**
     * Build the XML document for a pacs.008 message.
     *
     * @param XmlBuilder $xml  XML builder instance.
     * @param array      $data Structured payment data.
     *
     * @return void
     */
    public function buildDocument(XmlBuilder $xml, array $data): void
    {
        $xml->startElement('FIToFICstmrCdtTrf');
        $this->buildGroupHeader($xml, $data['grpHdr']);
        foreach ($data['transactions'] as $tx) {
            $this->buildCreditTransferTxInfo($xml, $tx);
        }
        $xml->endElement();
    }

    /**
     * Build the Group Header element.
     *
     * @param XmlBuilder $xml    XML builder instance.
     * @param array      $grpHdr Group header data.
     *
     * @return void
     */
    protected function buildGroupHeader(XmlBuilder $xml, array $grpHdr): void
    {
        $xml->startElement('GrpHdr');
        $xml->writeElement('MsgId', $grpHdr['msgId']);
        $xml->writeElement('CreDtTm', $grpHdr['creDtTm']);
        $xml->writeElement('NbOfTxs', count($this->transactions));
        $xml->endElement();
    }

    /**
     * Build a single Credit Transfer Transaction Information element.
     *
     * @param XmlBuilder $xml XML builder.
     * @param array      $tx  Transaction data.
     *
     * @return void
     */
    private function buildCreditTransferTxInfo(XmlBuilder $xml, array $tx): void
    {
        $xml->startElement('CdtTrfTxInf');
        $xml->writeElement('PmtId', $tx['pmtId']);
        $xml->writeElement('IntrBkSttlmAmt', $tx['amount'], ['Ccy' => $tx['currency']]);
        $xml->endElement();
    }
}
