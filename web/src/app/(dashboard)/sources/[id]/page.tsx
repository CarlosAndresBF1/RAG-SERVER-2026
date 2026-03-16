export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { SourceDetailResponse } from "@/types/api";
import { SourceDetailClient } from "@/components/sources/source-detail-client";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function SourceDetailPage({ params }: Props) {
  const { id } = await params;
  const source = await ragFetch<SourceDetailResponse>(`/api/v1/sources/${id}`);

  return <SourceDetailClient source={source} />;
}
