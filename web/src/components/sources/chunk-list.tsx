"use client";

import { useState } from "react";
import type { ChunkSummary } from "@/types/api";
import { ChevronDown, ChevronRight } from "lucide-react";

export function ChunkList({ chunks }: { chunks: ChunkSummary[] }) {
  return (
    <div className="space-y-2">
      <h3 className="font-serif text-lg text-primary">
        Chunks ({chunks.length})
      </h3>
      <div className="space-y-1">
        {chunks.map((chunk) => (
          <ChunkCard key={chunk.id} chunk={chunk} />
        ))}
      </div>
    </div>
  );
}

function ChunkCard({ chunk }: { chunk: ChunkSummary }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-border/50 bg-card rounded-md shadow-sm">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0 flex items-center gap-3">
          <span className="font-mono text-xs text-muted-foreground w-8">
            #{chunk.chunk_index}
          </span>
          <span className="text-sm truncate">
            {chunk.section ?? "—"}
            {chunk.subsection ? ` › ${chunk.subsection}` : ""}
          </span>
        </div>
        <span className="font-mono text-xs text-muted-foreground">
          {chunk.token_count} tokens
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-border/30">
          <pre className="mt-3 text-sm whitespace-pre-wrap font-mono bg-muted/30 p-3 rounded-md max-h-96 overflow-y-auto">
            {chunk.content}
          </pre>
          {Object.keys(chunk.metadata).length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Metadata</p>
              <pre className="text-xs font-mono bg-muted/30 p-2 rounded-md overflow-x-auto">
                {JSON.stringify(chunk.metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
