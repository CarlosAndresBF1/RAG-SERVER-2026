import { AlertTriangle } from "lucide-react";

export function GapAlerts({ gaps }: { gaps: string[] }) {
  return (
    <div className="border border-destructive/30 bg-destructive/5 rounded-md p-4">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="h-4 w-4 text-destructive" />
        <h3 className="font-serif text-lg text-destructive">ISO 20022 Coverage Gaps</h3>
      </div>
      <p className="text-sm text-muted-foreground mb-3">
        The following ISO 20022 message types (BimPay / IPS) have no indexed chunks:
      </p>
      <div className="flex flex-wrap gap-2">
        {gaps.map((gap) => (
          <span
            key={gap}
            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono bg-destructive/10 text-destructive border border-destructive/20"
          >
            {gap}
          </span>
        ))}
      </div>
    </div>
  );
}
