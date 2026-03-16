export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { FeedbackStats } from "@/types/api";
import { FeedbackDashboard } from "@/components/feedback/feedback-dashboard";

export default async function FeedbackPage() {
  const stats = await ragFetch<FeedbackStats>("/api/v1/stats/feedback");

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Feedback Dashboard</h2>
        <p className="text-muted-foreground text-sm">Response quality metrics and feedback analysis</p>
      </div>
      <FeedbackDashboard stats={stats} />
    </div>
  );
}
