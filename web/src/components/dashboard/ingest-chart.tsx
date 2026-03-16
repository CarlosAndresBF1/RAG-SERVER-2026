"use client";

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

interface IngestChartProps {
  data: { date: string; count: number }[];
}

export function IngestChart({ data }: IngestChartProps) {
  const chartData = data.map((d) => ({
    date: new Date(d.date).toLocaleDateString([], { month: "short", day: "numeric" }),
    count: d.count,
  }));

  return (
    <div className="border border-border/50 bg-card rounded-md shadow-sm">
      <div className="px-4 py-3 border-b border-border/50">
        <h3 className="font-serif text-lg text-primary">Ingestions (last 30 days)</h3>
      </div>
      <div className="p-4 h-64">
        {chartData.length === 0 ? (
          <p className="flex items-center justify-center h-full text-sm text-muted-foreground">
            No ingestion data yet
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-card)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
