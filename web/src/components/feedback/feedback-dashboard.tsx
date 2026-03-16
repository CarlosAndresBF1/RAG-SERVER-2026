"use client";

import type { FeedbackStats } from "@/types/api";
import { ThumbsUp, ThumbsDown, Minus, MessageSquare, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  CartesianGrid,
} from "recharts";

const CHART_COLORS = {
  positive: "#2E7D32",
  neutral: "#B8860B",
  negative: "#8B2500",
};

export function FeedbackDashboard({ stats }: { stats: FeedbackStats }) {
  const chartData = [
    { name: "Positive", value: stats.distribution.positive, color: CHART_COLORS.positive },
    { name: "Neutral", value: stats.distribution.neutral, color: CHART_COLORS.neutral },
    { name: "Negative", value: stats.distribution.negative, color: CHART_COLORS.negative },
  ];

  const exportCsv = () => {
    const header = "Date,Query,Rating,Comment,Tool,Created At\n";
    const rows = stats.rows
      .map((r) =>
        [r.created_at ?? "", `"${(r.query ?? "").replace(/"/g, '""')}"`, r.rating, `"${(r.comment ?? "").replace(/"/g, '""')}"`, r.tool_name ?? "", r.created_at ?? ""].join(",")
      )
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "feedback-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={MessageSquare} label="Total Feedback" value={stats.total.toLocaleString()} />
        <KpiCard icon={ThumbsUp} label="Positivity Rate" value={`${stats.positivity_rate}%`} />
        <KpiCard icon={Minus} label="Avg Rating" value={stats.average_rating.toFixed(2)} />
        <KpiCard icon={ThumbsDown} label="Negative" value={stats.distribution.negative.toLocaleString()} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Distribution chart */}
        <div className="border border-border/50 bg-card rounded-md shadow-sm">
          <div className="px-4 py-3 border-b border-border/50">
            <h3 className="font-serif text-lg text-primary">Rating Distribution</h3>
          </div>
          <div className="p-4 h-64">
            {stats.total === 0 ? (
              <p className="flex items-center justify-center h-full text-sm text-muted-foreground">
                No feedback collected yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "6px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Trend chart (last 30 days) */}
        <div className="border border-border/50 bg-card rounded-md shadow-sm">
          <div className="px-4 py-3 border-b border-border/50">
            <h3 className="font-serif text-lg text-primary">30-Day Trend</h3>
          </div>
          <div className="p-4 h-64">
            {stats.trend.length === 0 ? (
              <p className="flex items-center justify-center h-full text-sm text-muted-foreground">
                No trend data yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={stats.trend.map((t) => ({ ...t, date: t.date.slice(5, 10) }))}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="count" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="rating" orientation="right" domain={[-1, 1]} tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "6px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar yAxisId="count" dataKey="count" fill="#6366f1" opacity={0.5} radius={[2, 2, 0, 0]} />
                  <Line yAxisId="rating" type="monotone" dataKey="avg_rating" stroke="#2E7D32" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Per-query feedback table */}
      <div className="border border-border/50 bg-card rounded-md shadow-sm">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <h3 className="font-serif text-lg text-primary">Recent Feedback</h3>
          {stats.rows.length > 0 && (
            <Button variant="outline" size="sm" onClick={exportCsv}>
              <Download className="h-4 w-4 mr-1" />
              CSV
            </Button>
          )}
        </div>
        <div className="overflow-x-auto">
          {stats.rows.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">No feedback entries yet</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Date</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Query</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground">Rating</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Comment</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Tool</th>
                </tr>
              </thead>
              <tbody>
                {stats.rows.map((row) => (
                  <tr key={row.id} className="border-b border-border/30 hover:bg-muted/20">
                    <td className="px-4 py-2 text-xs font-mono text-muted-foreground whitespace-nowrap">
                      {row.created_at ? new Date(row.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-2 max-w-xs truncate">{row.query}</td>
                    <td className="px-4 py-2 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          row.rating === 1
                            ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                            : row.rating === -1
                            ? "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
                            : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                        }`}
                      >
                        {row.rating === 1 ? "👍" : row.rating === -1 ? "👎" : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground max-w-xs truncate">
                      {row.comment || "—"}
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-muted-foreground">
                      {row.tool_name || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm border-t-4 border-t-primary">
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        <Icon className="h-4 w-4" />
        <p className="text-sm font-medium">{label}</p>
      </div>
      <p className="text-2xl font-mono">{value}</p>
    </div>
  );
}
