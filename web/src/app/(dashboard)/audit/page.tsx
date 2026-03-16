"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronLeft, ChevronRight, Loader2, Shield } from "lucide-react";

interface AuditEntry {
  id: string;
  token_id: string;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  tool_name: string | null;
  created_at: string | null;
}

const ACTIONS = ["", "tool_call", "auth", "revoke", "create"];

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 50;

  const fetchAudit = async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (action) params.set("action", action);
    const res = await fetch(`/api/audit?${params}`);
    const data = await res.json();
    setEntries(data.entries ?? []);
    setTotal(data.total ?? 0);
    setLoading(false);
  };

  useEffect(() => {
    fetchAudit();
  }, [page, action]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Audit Log</h2>
        <p className="text-muted-foreground text-sm">
          MCP token usage and authentication activity ({total} entries)
        </p>
      </div>

      {/* Action filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-muted-foreground">Action:</span>
        {ACTIONS.map((a) => (
          <Button
            key={a || "all"}
            variant={action === a ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setAction(a);
              setPage(1);
            }}
          >
            {a || "All"}
          </Button>
        ))}
      </div>

      {/* Audit table */}
      <div className="border border-border/50 rounded-md bg-card shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Tool</TableHead>
              <TableHead>IP</TableHead>
              <TableHead>User Agent</TableHead>
              <TableHead>Token ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : entries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  No audit entries found
                </TableCell>
              </TableRow>
            ) : (
              entries.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="text-xs font-mono text-muted-foreground whitespace-nowrap">
                    {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-muted">
                      <Shield className="h-3 w-3" />
                      {e.action}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs font-mono">{e.tool_name ?? "—"}</TableCell>
                  <TableCell className="text-xs font-mono text-muted-foreground">
                    {e.ip_address ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-xs truncate">
                    {e.user_agent ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs font-mono text-muted-foreground">
                    {e.token_id.slice(0, 8)}…
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
