export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { StatsOverview, CoverageData, HealthResponse, JobsResponse } from "@/types/api";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { IngestChart } from "@/components/dashboard/ingest-chart";
import { GapAlerts } from "@/components/dashboard/gap-alerts";

async function getOverview(): Promise<StatsOverview> {
  return ragFetch<StatsOverview>("/api/v1/stats/overview");
}

async function getCoverage(): Promise<CoverageData> {
  return ragFetch<CoverageData>("/api/v1/stats/coverage");
}

async function getHealth(): Promise<HealthResponse> {
  return ragFetch<HealthResponse>("/health");
}

async function getRecentJobs(): Promise<JobsResponse> {
  return ragFetch<JobsResponse>("/api/v1/jobs?limit=10");
}

export default async function DashboardPage() {
  const [overview, coverage, health, recentJobs] = await Promise.all([
    getOverview(),
    getCoverage(),
    getHealth(),
    getRecentJobs(),
  ]);

  // Calculate coverage percentage: message_types with at least 1 chunk
  const totalMessageTypes = coverage.message_types.length;
  const coveredCount = coverage.message_types.filter((mt) =>
    coverage.matrix.some((c) => c.message_type === mt && c.chunk_count > 0)
  ).length;
  const coveragePercent = totalMessageTypes > 0
    ? Math.round((coveredCount / totalMessageTypes) * 100)
    : 0;

  // Find gaps — message_types with zero total chunks
  const gaps = coverage.message_types.filter((mt) => {
    const total = coverage.matrix
      .filter((c) => c.message_type === mt)
      .reduce((sum, c) => sum + c.chunk_count, 0);
    return total === 0;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Dashboard Overview</h2>
        <p className="text-muted-foreground text-sm">System status and key metrics</p>
      </div>

      <KpiCards
        totalDocuments={overview.total_documents}
        totalChunks={overview.total_chunks}
        coveragePercent={coveragePercent}
        health={health}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <IngestChart data={overview.ingests_per_day} />
        <RecentActivity jobs={recentJobs.jobs} />
      </div>

      {gaps.length > 0 && <GapAlerts gaps={gaps} />}
    </div>
  );
}
