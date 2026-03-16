export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { SourceListResponse } from "@/types/api";
import { SourcesTable } from "@/components/sources/sources-table";

interface Props {
  searchParams: Promise<{ page?: string; source_type?: string; q?: string }>;
}

export default async function SourcesPage({ searchParams }: Props) {
  const params = await searchParams;
  const page = Math.max(1, parseInt(params.page ?? "1", 10));
  const pageSize = 25;

  const queryParams = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (params.source_type) queryParams.set("source_type", params.source_type);

  const data = await ragFetch<SourceListResponse>(
    `/api/v1/sources?${queryParams.toString()}`
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Sources</h2>
        <p className="text-muted-foreground text-sm">
          Browse and manage indexed source documents
        </p>
      </div>

      <SourcesTable
        items={data.items}
        total={data.total}
        page={page}
        pageSize={pageSize}
        currentSourceType={params.source_type}
      />
    </div>
  );
}
