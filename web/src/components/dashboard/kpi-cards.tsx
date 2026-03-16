import { FileText, Layers, PieChart, Heart } from "lucide-react";
import type { HealthResponse } from "@/types/api";

interface KpiCardsProps {
  totalDocuments: number;
  totalChunks: number;
  coveragePercent: number;
  health: HealthResponse;
}

const healthColor: Record<string, string> = {
  ok: "bg-green-500",
  degraded: "bg-amber-500",
  error: "bg-red-500",
};

export function KpiCards({ totalDocuments, totalChunks, coveragePercent, health }: KpiCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        icon={FileText}
        label="Total Documents"
        value={totalDocuments.toLocaleString()}
        accent="border-t-primary"
      />
      <KpiCard
        icon={Layers}
        label="Total Chunks"
        value={totalChunks.toLocaleString()}
        accent="border-t-secondary"
      />
      <KpiCard
        icon={PieChart}
        label="Coverage"
        value={`${coveragePercent}%`}
        accent="border-t-chart-3"
      />
      <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm border-t-4 border-t-chart-4">
        <div className="flex items-center gap-2 text-muted-foreground mb-2">
          <Heart className="h-4 w-4" />
          <p className="text-sm font-medium">Health Status</p>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span className={`w-3 h-3 rounded-full ${healthColor[health.status] ?? "bg-gray-400"} block`} />
          <span className="text-lg font-mono capitalize">{health.status}</span>
        </div>
        <div className="mt-2 flex gap-2 flex-wrap">
          {Object.entries(health.services).map(([name, status]) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${status === "ok" ? "bg-green-500" : "bg-red-500"}`} />
              {name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className={`border border-border/50 bg-card rounded-md p-4 shadow-sm border-t-4 ${accent}`}>
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        <Icon className="h-4 w-4" />
        <p className="text-sm font-medium">{label}</p>
      </div>
      <p className="text-2xl font-mono">{value}</p>
    </div>
  );
}
