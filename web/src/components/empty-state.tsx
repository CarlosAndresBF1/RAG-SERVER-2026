import { FileText, Search, MessageSquare, Key, BarChart3, Upload } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon = FileText, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {/* Line-art style: large faded icon with a decorative circle */}
      <div className="relative mb-6">
        <div className="w-24 h-24 rounded-full bg-muted/50 flex items-center justify-center border-2 border-dashed border-border">
          <Icon className="h-10 w-10 text-muted-foreground/50" />
        </div>
      </div>
      <h3 className="font-serif text-lg text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* Pre-configured empty states for each page */

export function EmptySources() {
  return (
    <EmptyState
      icon={FileText}
      title="No sources indexed"
      description="Upload and ingest documents to start building the knowledge base."
    />
  );
}

export function EmptySearch() {
  return (
    <EmptyState
      icon={Search}
      title="Start searching"
      description="Enter a query above to search the knowledge base for relevant evidence."
    />
  );
}

export function EmptyFeedback() {
  return (
    <EmptyState
      icon={MessageSquare}
      title="No feedback collected"
      description="Feedback will appear here as users interact with MCP tools and rate responses."
    />
  );
}

export function EmptyTokens() {
  return (
    <EmptyState
      icon={Key}
      title="No MCP tokens"
      description="Create a token to allow AI clients to connect to the MCP server."
    />
  );
}

export function EmptyCoverage() {
  return (
    <EmptyState
      icon={BarChart3}
      title="No coverage data"
      description="Ingest some documents first to see the coverage matrix."
    />
  );
}

export function EmptyJobs() {
  return (
    <EmptyState
      icon={Upload}
      title="No ingestion jobs"
      description="Jobs will appear here after you ingest documents into the knowledge base."
    />
  );
}
