"use client";

import { useState } from "react";
import type { HealthResponse, DbStats } from "@/types/api";
import { RefreshCw, CheckCircle2, XCircle, Database } from "lucide-react";
import { Button } from "@/components/ui/button";

interface SettingsPanelProps {
  health: HealthResponse;
  dbStats: DbStats | null;
}

export function SettingsPanel({ health: initialHealth, dbStats: initialDbStats }: SettingsPanelProps) {
  const [health, setHealth] = useState(initialHealth);
  const [dbStats, setDbStats] = useState(initialDbStats);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      const [healthRes, dbRes] = await Promise.all([
        fetch("/api/health-check"),
        fetch("/api/stats/db"),
      ]);
      const healthData = await healthRes.json().catch(() => null);
      const dbData = await dbRes.json().catch(() => null);
      if (healthData?.services) setHealth(healthData);
      if (dbData?.database_size) setDbStats(dbData);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Service Status */}
      <div className="border border-border/50 bg-card rounded-md shadow-sm">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <h3 className="font-serif text-lg text-primary">Service Status</h3>
          <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={`h-4 w-4 mr-1 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-3">
            <span className={`w-3 h-3 rounded-full ${health.status === "ok" ? "bg-green-500" : "bg-amber-500"}`} />
            <span className="text-sm font-medium">
              Overall: <span className="capitalize">{health.status}</span>
            </span>
            <span className="text-xs text-muted-foreground font-mono">v{health.version}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {Object.entries(health.services).map(([name, status]) => (
              <div
                key={name}
                className="flex items-center gap-2 border border-border/30 rounded-md p-3"
              >
                {status === "ok" ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-destructive" />
                )}
                <div>
                  <p className="text-sm font-medium capitalize">{name.replace(/_/g, " ")}</p>
                  <p className="text-xs text-muted-foreground capitalize">{status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="border border-border/50 bg-card rounded-md shadow-sm">
        <div className="px-4 py-3 border-b border-border/50">
          <h3 className="font-serif text-lg text-primary">Configuration</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <ConfigItem label="RAG API URL" value={process.env.RAG_API_URL ?? "http://localhost:8080"} />
            <ConfigItem label="Embedding Model" value="nomic-embed-text-v1.5" />
            <ConfigItem label="Embedding Dimension" value="768" />
            <ConfigItem label="LLM Provider" value="Ollama" />
            <ConfigItem label="Reranker" value="ms-marco-MiniLM-L-6-v2" />
            <ConfigItem label="MCP Transport" value="HTTP (SSE)" />
          </div>
        </div>
      </div>

      {/* Environment */}
      <div className="border border-border/50 bg-card rounded-md shadow-sm">
        <div className="px-4 py-3 border-b border-border/50">
          <h3 className="font-serif text-lg text-primary">Environment</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <ConfigItem label="Node.js" value={process.version ?? "—"} />
            <ConfigItem label="Next.js" value="16.x" />
            <ConfigItem label="Environment" value={process.env.NODE_ENV ?? "development"} />
          </div>
        </div>
      </div>

      {/* Database Stats */}
      {dbStats && (
        <div className="border border-border/50 bg-card rounded-md shadow-sm">
          <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            <h3 className="font-serif text-lg text-primary">Database</h3>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total Size</p>
              <p className="font-mono text-2xl">{dbStats.database_size}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Row Counts</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(dbStats.row_counts).map(([table, count]) => (
                  <div key={table} className="border border-border/30 rounded-md p-3">
                    <p className="text-xs text-muted-foreground capitalize">{table.replace(/_/g, " ")}</p>
                    <p className="font-mono text-lg">{count >= 0 ? count.toLocaleString() : "—"}</p>
                  </div>
                ))}
              </div>
            </div>
            {dbStats.table_sizes.length > 0 && (
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Table Sizes</p>
                <div className="border border-border/30 rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/30">
                        <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Table</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Size</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dbStats.table_sizes.map((ts) => (
                        <tr key={ts.table} className="border-b border-border/20">
                          <td className="px-3 py-1.5 font-mono text-xs">{ts.table}</td>
                          <td className="px-3 py-1.5 font-mono text-xs text-right">{ts.size}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className="font-mono text-sm mt-0.5">{value}</p>
    </div>
  );
}
