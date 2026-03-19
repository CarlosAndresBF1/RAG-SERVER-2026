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

  // Calculate message-type coverage percentage (BimPay / ISO 20022)
  const totalMessageTypes = coverage.message_types.length;
  const coveredCount = coverage.message_types.filter((mt) =>
    coverage.matrix.some((c) => c.message_type === mt && c.chunk_count > 0)
  ).length;
  const coveragePercent = totalMessageTypes > 0
    ? Math.round((coveredCount / totalMessageTypes) * 100)
    : 0;

  // Calculate overall knowledge base coverage (source types with docs)
  const totalSourceTypes = (coverage.source_type_summary ?? []).length;
  const overallCoverage = totalSourceTypes > 0 ? 100 : 0; // all present types have docs by definition

  // Find message-type gaps — message_types with zero total chunks
  const gaps = coverage.message_types.filter((mt) => {
    const total = coverage.matrix
      .filter((c) => c.message_type === mt)
      .reduce((sum, c) => sum + c.chunk_count, 0);
    return total === 0;
  });

  // Overall stats
  const totalDocs = (coverage.source_type_summary ?? []).reduce((s, r) => s + r.doc_count, 0);
  const totalChunks = (coverage.source_type_summary ?? []).reduce((s, r) => s + r.chunk_count, 0);

  // Use the broader metric (total docs / source types) as the main coverage KPI
  const displayCoverage = totalMessageTypes > 0
    ? coveragePercent
    : (totalDocs > 0 ? 100 : 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Dashboard Overview</h2>
        <p className="text-muted-foreground text-sm">System status and key metrics</p>
      </div>

      <KpiCards
        totalDocuments={overview.total_documents}
        totalChunks={overview.total_chunks}
        coveragePercent={displayCoverage}
        health={health}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <IngestChart data={overview.ingests_per_day} />
        <RecentActivity jobs={recentJobs.jobs} />
      </div>

      {gaps.length > 0 && <GapAlerts gaps={gaps} />}

      {/* Source-type summary on dashboard */}
      {(coverage.source_type_summary ?? []).length > 0 && (
        <div className="border border-border/50 bg-card rounded-md p-4 shadow-sm">
          <h3 className="font-serif text-lg text-primary mb-3">Knowledge Base by Source Type</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {coverage.source_type_summary.map((st) => (
              <div key={st.source_type} className="flex flex-col p-3 border border-border/30 rounded-md">
                <span className="text-xs text-muted-foreground">{st.source_type.replace(/_/g, " ")}</span>
                <span className="font-mono text-lg">{st.doc_count} doc{st.doc_count !== 1 ? "s" : ""}</span>
                <span className="text-xs text-muted-foreground">{st.chunk_count.toLocaleString()} chunks</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
