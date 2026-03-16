"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import type { SourceDetailResponse } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChunkList } from "@/components/sources/chunk-list";
import {
  ArrowLeft,
  RefreshCw,
  Trash2,
  Download,
  Info,
  Loader2,
} from "lucide-react";

export function SourceDetailClient({ source }: { source: SourceDetailResponse }) {
  const router = useRouter();
  const [reingesting, setReingesting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showMeta, setShowMeta] = useState(false);

  const reingest = async () => {
    setReingesting(true);
    try {
      await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_path: source.source_path,
          source_type: source.source_type,
          replace_existing: true,
        }),
      });
      toast.success("Re-ingestion started");
      router.refresh();
    } catch {
      toast.error("Re-ingestion failed");
    } finally {
      setReingesting(false);
    }
  };

  const deleteSource = async () => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/sources/${source.id}`, { method: "DELETE" });
      if (res.ok) {
        toast.success("Source deleted");
        router.push("/sources");
      } else {
        toast.error("Delete failed");
      }
    } catch {
      toast.error("Delete failed");
    } finally {
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(source.chunks, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${source.source_path.split("/").pop()}-chunks.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Collect unique metadata keys across chunks
  const metaKeys = new Set<string>();
  for (const c of source.chunks) {
    for (const k of Object.keys(c.metadata)) metaKeys.add(k);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/sources"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Sources
        </Link>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowMeta(!showMeta)}>
            <Info className="h-4 w-4 mr-1" />
            Metadata
          </Button>
          <Button variant="outline" size="sm" onClick={downloadJson}>
            <Download className="h-4 w-4 mr-1" />
            JSON
          </Button>
          <Button variant="outline" size="sm" onClick={reingest} disabled={reingesting}>
            {reingesting ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-1" />
            )}
            Re-ingest
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            disabled={deleting}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            Delete
          </Button>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-lg space-y-4">
            <h3 className="text-lg font-serif text-primary">Confirm Delete</h3>
            <p className="text-sm text-muted-foreground">
              This will permanently delete <strong>{source.source_path.split("/").pop()}</strong> and
              all {source.total_chunks} associated chunks. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={deleteSource} disabled={deleting}>
                {deleting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Header card */}
      <div className="border border-border/50 bg-card rounded-md p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="space-y-2">
            <h2 className="text-2xl font-serif text-primary tracking-tight">
              {source.source_path.split("/").pop()}
            </h2>
            <p className="text-sm text-muted-foreground font-mono">{source.source_path}</p>
          </div>
          <Badge variant="secondary">{source.source_type.replace(/_/g, " ")}</Badge>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-4 border-t border-border/30">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Chunks</p>
            <p className="font-mono text-lg">{source.total_chunks}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Hash</p>
            <p className="font-mono text-sm">{source.file_hash.slice(0, 16)}…</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Status</p>
            <p className="text-sm">{source.is_current ? "Current" : "Superseded"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Ingested</p>
            <p className="text-sm">{new Date(source.ingested_at).toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* Metadata summary panel */}
      {showMeta && (
        <div className="border border-border/50 bg-muted/30 rounded-md p-4 space-y-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Metadata Summary</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <p className="text-xs text-muted-foreground">Total tokens</p>
              <p className="font-mono">
                {source.chunks.reduce((s, c) => s + c.token_count, 0).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Avg tokens/chunk</p>
              <p className="font-mono">
                {source.chunks.length > 0
                  ? Math.round(
                      source.chunks.reduce((s, c) => s + c.token_count, 0) / source.chunks.length
                    )
                  : 0}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Sections</p>
              <p className="font-mono">
                {new Set(source.chunks.map((c) => c.section).filter(Boolean)).size}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Metadata keys</p>
              <p className="font-mono">{metaKeys.size}</p>
            </div>
          </div>
          {metaKeys.size > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {[...metaKeys].sort().map((k) => (
                <span
                  key={k}
                  className="text-xs font-mono bg-muted px-2 py-0.5 rounded text-muted-foreground"
                >
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Chunk list */}
      <ChunkList chunks={source.chunks} />
    </div>
  );
}
