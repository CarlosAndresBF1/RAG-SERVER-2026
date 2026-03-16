export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { JobsResponse } from "@/types/api";
import { JobsTimeline } from "@/components/jobs/jobs-timeline";

interface Props {
  searchParams: Promise<{ page?: string; status?: string }>;
}

export default async function JobsPage({ searchParams }: Props) {
  const params = await searchParams;
  const page = Math.max(1, parseInt(params.page ?? "1", 10));
  const statusFilter = params.status ?? "";
  const limit = 30;
  const offset = (page - 1) * limit;

  const statusParam = statusFilter ? `&status=${statusFilter}` : "";
  const data = await ragFetch<JobsResponse>(`/api/v1/jobs?limit=${limit}&offset=${offset}${statusParam}`);
  const totalPages = Math.ceil(data.total / limit);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Ingestion History</h2>
        <p className="text-muted-foreground text-sm">
          Timeline of all ingestion jobs ({data.total} total)
        </p>
      </div>
      <JobsTimeline jobs={data.jobs} page={page} totalPages={totalPages} currentStatus={statusFilter} />
    </div>
  );
}
