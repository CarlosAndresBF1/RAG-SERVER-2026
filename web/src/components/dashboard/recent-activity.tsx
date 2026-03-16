import type { IngestJob } from "@/types/api";
import { Badge } from "@/components/ui/badge";

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  running: "secondary",
  pending: "outline",
  failed: "destructive",
};

export function RecentActivity({ jobs }: { jobs: IngestJob[] }) {
  return (
    <div className="border border-border/50 bg-card rounded-md shadow-sm">
      <div className="px-4 py-3 border-b border-border/50">
        <h3 className="font-serif text-lg text-primary">Recent Activity</h3>
      </div>
      <div className="divide-y divide-border/30 max-h-80 overflow-y-auto">
        {jobs.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground text-center">No recent activity</p>
        ) : (
          jobs.map((job) => (
            <div key={job.id} className="px-4 py-3 flex items-center gap-3">
              <Badge variant={statusVariant[job.status] ?? "outline"}>
                {job.status}
              </Badge>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {job.source_path.split("/").pop()}
                </p>
                <p className="text-xs text-muted-foreground font-mono">
                  {job.source_type} · {job.chunks_created} chunks
                </p>
              </div>
              <time className="text-xs text-muted-foreground font-mono whitespace-nowrap">
                {job.created_at
                  ? new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                  : "—"}
              </time>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
