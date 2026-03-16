export const dynamic = "force-dynamic";

import { ragFetch } from "@/lib/api-client";
import type { HealthResponse, DbStats } from "@/types/api";
import { SettingsPanel } from "@/components/settings/settings-panel";

export default async function SettingsPage() {
  const [health, dbStats] = await Promise.all([
    ragFetch<HealthResponse>("/health"),
    ragFetch<DbStats>("/api/v1/stats/db").catch(() => null),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Settings</h2>
        <p className="text-muted-foreground text-sm">System configuration and service status</p>
      </div>
      <SettingsPanel health={health} dbStats={dbStats} />
    </div>
  );
}
