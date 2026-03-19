"use client";

import type { SourceTypeSummary } from "@/types/api";
import { FileText, Layers } from "lucide-react";

const TYPE_LABELS: Record<string, string> = {
  annex_b_spec: "Annex B (IPS)",
  annex_a_spec: "Annex A",
  annex_c_spec: "Annex C",
  tech_doc: "Technical Doc",
  claude_context: "Claude Context",
  alias_doc: "Aliases",
  qr_doc: "QR / Código QR",
  banking_doc: "Home Banking",
  integration_doc: "Integration",
  php_code: "PHP Code",
  xml_example: "XML Example",
  postman_collection: "Postman Collection",
  pdf_doc: "PDF Document",
  word_doc: "Word Document",
  generic_text: "General Text",
};

function labelFor(sourceType: string): string {
  return TYPE_LABELS[sourceType] ?? sourceType.replace(/_/g, " ");
}

export function SourceTypeSummaryTable({ summary }: { summary: SourceTypeSummary[] }) {
  const totalDocs = summary.reduce((s, r) => s + r.doc_count, 0);
  const totalChunks = summary.reduce((s, r) => s + r.chunk_count, 0);

  if (summary.length === 0) {
    return (
      <div className="border border-border/50 bg-card rounded-md p-8 text-center">
        <p className="text-muted-foreground">No documents ingested yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-xl font-serif text-primary">Documentation Overview</h3>

      {/* KPI strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Source Types</p>
          <p className="font-mono text-2xl">{summary.length}</p>
        </div>
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Documents</p>
          </div>
          <p className="font-mono text-2xl">{totalDocs.toLocaleString()}</p>
        </div>
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <div className="flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-muted-foreground" />
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Chunks</p>
          </div>
          <p className="font-mono text-2xl">{totalChunks.toLocaleString()}</p>
        </div>
      </div>

      {/* Table */}
      <div className="border border-border/50 bg-card rounded-md shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/50">
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Source Type</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground">Documents</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground">Chunks</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {summary.map((row) => {
              const pct = totalChunks > 0 ? Math.round((row.chunk_count / totalChunks) * 100) : 0;
              return (
                <tr key={row.source_type} className="border-b border-border/30 hover:bg-muted/20">
                  <td className="px-4 py-2 font-medium">{labelFor(row.source_type)}</td>
                  <td className="px-4 py-2 text-center font-mono">{row.doc_count}</td>
                  <td className="px-4 py-2 text-center font-mono">{row.chunk_count.toLocaleString()}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground font-mono w-10 text-right">{pct}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-border font-medium">
              <td className="px-4 py-2">Total</td>
              <td className="px-4 py-2 text-center font-mono">{totalDocs}</td>
              <td className="px-4 py-2 text-center font-mono">{totalChunks.toLocaleString()}</td>
              <td className="px-4 py-2 font-mono text-xs text-muted-foreground">100%</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
