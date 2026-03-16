export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { CoverageData } from "@/types/api";
import { CoverageMatrix } from "@/components/coverage/coverage-matrix";

export default async function CoveragePage() {
  const data = await ragFetch<CoverageData>("/api/v1/stats/coverage");

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Coverage Matrix</h2>
        <p className="text-muted-foreground text-sm">
          Chunk distribution by message type and source type
        </p>
      </div>
      <CoverageMatrix data={data} />
    </div>
  );
}
