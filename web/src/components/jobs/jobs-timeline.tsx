"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { IngestJob } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, CheckCircle2, XCircle, Clock, Loader2, RefreshCw, Ban, Trash2 } from "lucide-react";

const statusConfig: Record<string, {
  variant: "default" | "secondary" | "destructive" | "outline";
  icon: React.ComponentType<{ className?: string }>;
}> = {
  completed: { variant: "default", icon: CheckCircle2 },
  failed: { variant: "destructive", icon: XCircle },
  cancelled: { variant: "outline", icon: Ban },
  pending: { variant: "outline", icon: Clock },
  running: { variant: "secondary", icon: Loader2 },
};

const STATUSES = ["", "pending", "running", "completed", "failed", "cancelled"];

interface Props {
  jobs: IngestJob[];
  page: number;
  totalPages: number;
  currentStatus?: string;
}

export function JobsTimeline({ jobs, page, totalPages, currentStatus = "" }: Props) {
  const router = useRouter();
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const rerunJob = async (job: IngestJob) => {
    setRerunningId(job.id);
    try {
      await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_path: job.source_path,
          source_type: job.source_type,
          replace_existing: true,
        }),
      });
      router.refresh();
    } finally {
      setRerunningId(null);
    }
  };

  const cancelJob = async (job: IngestJob) => {
    setCancellingId(job.id);
    try {
      await fetch(`/api/jobs/${job.id}/cancel`, { method: "POST" });
      router.refresh();
    } finally {
      setCancellingId(null);
    }
  };

  const deleteJob = async (job: IngestJob) => {
    setDeletingId(job.id);
    try {
      await fetch(`/api/jobs/${job.id}`, { method: "DELETE" });
      router.refresh();
    } finally {
      setDeletingId(null);
    }
  };

  const buildUrl = (overrides: Record<string, string>) => {
    const p = new URLSearchParams();
    const page = overrides.page ?? "1";
    const status = overrides.status ?? currentStatus;
    if (page !== "1") p.set("page", page);
    if (status) p.set("status", status);
    return `/jobs${p.toString() ? `?${p}` : ""}`;
  };

  return (
    <div className="space-y-4">
      {/* Status filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-muted-foreground">Status:</span>
        {STATUSES.map((s) => (
          <Link key={s || "all"} href={buildUrl({ status: s, page: "1" })}>
            <Button variant={currentStatus === s ? "default" : "outline"} size="sm">
              {s || "All"}
            </Button>
          </Link>
        ))}
      </div>
      {/* Timeline */}
      <div className="space-y-1">
        {jobs.length === 0 ? (
          <div className="border border-border/50 bg-card rounded-md p-8 text-center">
            <p className="text-muted-foreground">No ingestion jobs found</p>
          </div>
        ) : (
          jobs.map((job) => {
            const config = statusConfig[job.status] ?? statusConfig.pending;
            const Icon = config.icon;
            const duration =
              job.started_at && job.completed_at
                ? Math.round(
                    (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000
                  )
                : null;

            return (
              <div
                key={job.id}
                className="flex items-start gap-4 border border-border/50 bg-card rounded-md p-4 shadow-sm hover:bg-muted/20 transition-colors"
              >
                <div className="mt-0.5">
                  <Icon className={`h-5 w-5 ${job.status === "failed" ? "text-destructive" : job.status === "completed" ? "text-green-600" : job.status === "cancelled" ? "text-muted-foreground" : "text-muted-foreground"}`} />
                </div>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium truncate">
                      {job.source_path.split("/").pop()}
                    </p>
                    <Badge variant={config.variant}>{job.status}</Badge>
                    <span className="text-xs font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {job.source_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {job.chunks_created > 0 && (
                      <span>{job.chunks_created} chunks</span>
                    )}
                    {duration !== null && <span>{duration}s</span>}
                    {job.created_at && (
                      <time className="font-mono">
                        {new Date(job.created_at).toLocaleString()}
                      </time>
                    )}
                  </div>
                  {job.error_message && (
                    <p className="text-xs text-destructive mt-1 font-mono">{job.error_message}</p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {/* Cancel — only for pending/running */}
                  {(job.status === "pending" || job.status === "running") && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => cancelJob(job)}
                      disabled={cancellingId === job.id}
                      title="Cancel job"
                    >
                      {cancellingId === job.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Ban className="h-4 w-4 text-destructive" />
                      )}
                    </Button>
                  )}
                  {/* Re-run — for completed/failed/cancelled */}
                  {(job.status === "completed" || job.status === "failed" || job.status === "cancelled") && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => rerunJob(job)}
                      disabled={rerunningId === job.id}
                      title="Re-run ingestion"
                    >
                      {rerunningId === job.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                  {/* Delete — for completed/failed/cancelled */}
                  {(job.status === "completed" || job.status === "failed" || job.status === "cancelled") && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteJob(job)}
                      disabled={deletingId === job.id}
                      title="Delete job record"
                    >
                      {deletingId === job.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      )}
                    </Button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Link href={buildUrl({ page: String(page - 1) })}>
              <Button variant="outline" size="sm" disabled={page <= 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </Link>
            <Link href={buildUrl({ page: String(page + 1) })}>
              <Button variant="outline" size="sm" disabled={page >= totalPages}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
