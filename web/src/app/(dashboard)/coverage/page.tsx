export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { CoverageData } from "@/types/api";
import { CoverageMatrix } from "@/components/coverage/coverage-matrix";
import { SourceTypeSummaryTable } from "@/components/coverage/source-type-summary";

export default async function CoveragePage() {
  const data = await ragFetch<CoverageData>("/api/v1/stats/coverage");

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Knowledge Base Coverage</h2>
        <p className="text-muted-foreground text-sm">
          Overview of all ingested documentation and ISO 20022 message type coverage
        </p>
      </div>

      {/* Source type overview — ALL documents */}
      <SourceTypeSummaryTable summary={data.source_type_summary} />

      {/* ISO 20022 message type matrix — BimPay / IPS */}
      {data.message_types.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-col gap-1">
            <h3 className="text-xl font-serif text-primary">ISO 20022 Message Coverage</h3>
            <p className="text-muted-foreground text-sm">
              Chunk distribution by message type and source type (BimPay / IPS integration)
            </p>
          </div>
          <CoverageMatrix data={data} />
        </div>
      )}
    </div>
  );
}
