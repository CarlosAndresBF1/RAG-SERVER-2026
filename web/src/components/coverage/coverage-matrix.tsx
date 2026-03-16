"use client";

import { useState } from "react";
import type { CoverageData } from "@/types/api";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

function cellColor(count: number): string {
  if (count === 0) return "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300";
  if (count <= 5) return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300";
}

export function CoverageMatrix({ data }: { data: CoverageData }) {
  const { matrix, message_types, source_types } = data;
  const [drilldown, setDrilldown] = useState<{
    mt: string;
    st: string;
    count: number;
    sources: { id: string; source_path: string; total_chunks: number }[];
    loading: boolean;
  } | null>(null);

  const openDrilldown = async (mt: string, st: string, count: number) => {
    if (count === 0) return;
    setDrilldown({ mt, st, count, sources: [], loading: true });
    try {
      const res = await fetch(`/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: mt,
          message_type: mt,
          source_type: st,
          top_k: 5,
        }),
      });
      const data = await res.json();
      const sources = (data.evidence ?? []).map(
        (ev: { citations: { source_path: string; chunk_index: number }[] }, i: number) => ({
          id: String(i),
          source_path: ev.citations?.[0]?.source_path ?? "—",
          total_chunks: ev.citations?.length ?? 0,
        })
      );
      setDrilldown((prev) => (prev ? { ...prev, sources, loading: false } : null));
    } catch {
      setDrilldown((prev) => (prev ? { ...prev, loading: false } : null));
    }
  };

  if (message_types.length === 0 || source_types.length === 0) {
    return (
      <div className="border border-border/50 bg-card rounded-md p-8 text-center">
        <p className="text-muted-foreground">No coverage data yet. Ingest some documents first.</p>
      </div>
    );
  }

  // Build lookup: message_type -> source_type -> count
  const lookup = new Map<string, Map<string, number>>();
  for (const cell of matrix) {
    if (!lookup.has(cell.message_type)) lookup.set(cell.message_type, new Map());
    lookup.get(cell.message_type)!.set(cell.source_type, cell.chunk_count);
  }

  // Row totals
  const rowTotals = new Map<string, number>();
  for (const mt of message_types) {
    const total = source_types.reduce(
      (sum, st) => sum + (lookup.get(mt)?.get(st) ?? 0),
      0
    );
    rowTotals.set(mt, total);
  }

  // Column totals
  const colTotals = new Map<string, number>();
  for (const st of source_types) {
    const total = message_types.reduce(
      (sum, mt) => sum + (lookup.get(mt)?.get(st) ?? 0),
      0
    );
    colTotals.set(st, total);
  }

  const grandTotal = [...rowTotals.values()].reduce((a, b) => a + b, 0);
  const coveredTypes = message_types.filter((mt) => (rowTotals.get(mt) ?? 0) > 0).length;
  const coveragePercent = Math.round((coveredTypes / message_types.length) * 100);

  // Gaps
  const gaps = message_types.filter((mt) => (rowTotals.get(mt) ?? 0) === 0);

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Coverage</p>
          <p className="font-mono text-2xl">{coveragePercent}%</p>
          <p className="text-xs text-muted-foreground">{coveredTypes}/{message_types.length} types</p>
        </div>
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Chunks</p>
          <p className="font-mono text-2xl">{grandTotal.toLocaleString()}</p>
        </div>
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Gaps</p>
          <p className="font-mono text-2xl text-destructive">{gaps.length}</p>
        </div>
      </div>

      {/* Matrix table */}
      <div className="border border-border/50 bg-card rounded-md shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/50">
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Message Type</th>
              {source_types.map((st) => (
                <th key={st} className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">
                  {st.replace(/_/g, " ")}
                </th>
              ))}
              <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Total</th>
            </tr>
          </thead>
          <tbody>
            {message_types.map((mt) => (
              <tr key={mt} className="border-b border-border/30 hover:bg-muted/20">
                <td className="px-3 py-2 font-mono text-sm">{mt}</td>
                {source_types.map((st) => {
                  const count = lookup.get(mt)?.get(st) ?? 0;
                  return (
                    <td key={st} className="px-3 py-2 text-center">
                      <button
                        onClick={() => openDrilldown(mt, st, count)}
                        disabled={count === 0}
                        className={`inline-block min-w-[2.5rem] px-2 py-0.5 rounded-full text-xs font-mono ${cellColor(count)} ${count > 0 ? "cursor-pointer hover:ring-2 hover:ring-primary/50 transition-all" : ""}`}
                      >
                        {count}
                      </button>
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-center font-mono text-sm font-medium">
                  {rowTotals.get(mt) ?? 0}
                </td>
              </tr>
            ))}
            {/* Column totals */}
            <tr className="border-t-2 border-border font-medium">
              <td className="px-3 py-2 text-sm">Totals</td>
              {source_types.map((st) => (
                <td key={st} className="px-3 py-2 text-center font-mono text-sm">
                  {colTotals.get(st) ?? 0}
                </td>
              ))}
              <td className="px-3 py-2 text-center font-mono text-sm font-bold">{grandTotal}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Gaps list */}
      {gaps.length > 0 && (
        <div className="border border-destructive/30 bg-destructive/5 rounded-md p-4">
          <p className="text-sm font-medium text-destructive mb-2">
            Message types with zero coverage:
          </p>
          <div className="flex flex-wrap gap-2">
            {gaps.map((g) => (
              <span
                key={g}
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono bg-destructive/10 text-destructive border border-destructive/20"
              >
                {g}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Drill-down dialog */}
      {drilldown && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-lg w-full mx-4 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-serif text-primary">
                {drilldown.mt} × {drilldown.st.replace(/_/g, " ")}
              </h3>
              <Button variant="ghost" size="sm" onClick={() => setDrilldown(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {drilldown.count} chunks in this cell
            </p>
            {drilldown.loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : drilldown.sources.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">No matching results found</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {drilldown.sources.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between p-3 border border-border/30 rounded-md"
                  >
                    <span className="text-sm font-mono truncate">{s.source_path.split("/").pop()}</span>
                    <span className="text-xs text-muted-foreground">{s.total_chunks} citations</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
