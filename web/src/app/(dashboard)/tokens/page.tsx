"use client";

import { useState, useEffect, useCallback } from "react";
import { Key, Plus, Trash2, Copy, Eye, ShieldCheck, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { McpToken, TokenAuditEntry } from "@/types/api";

export default function TokensPage() {
  const [tokens, setTokens] = useState<McpToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [revealedToken, setRevealedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [auditLog, setAuditLog] = useState<{ tokenId: string; entries: TokenAuditEntry[] } | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // New token form state
  const [newName, setNewName] = useState("");
  const [newScopes, setNewScopes] = useState<string[]>(["read"]);
  const [newExpiry, setNewExpiry] = useState("");
  const [newRateLimit, setNewRateLimit] = useState(60);

  const fetchTokens = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tokens");
      const data = await res.json();
      setTokens(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTokens();
  }, [fetchTokens]);

  const createToken = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);

    // Generate token client-side, hash it, send hash to server
    const rawToken = `odr_${generateRandomString(48)}`;
    const hash = await sha256(rawToken);
    const prefix = rawToken.slice(0, 12);

    try {
      const res = await fetch("/api/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName,
          token_hash: hash,
          token_prefix: prefix,
          scopes: newScopes,
          expires_at: newExpiry || undefined,
          rate_limit_rpm: newRateLimit,
        }),
      });

      if (res.ok) {
        setDialogOpen(false);
        setRevealedToken(rawToken);
        setNewName("");
        setNewScopes(["read"]);
        setNewExpiry("");
        setNewRateLimit(60);
        await fetchTokens();
      } else {
        const err = await res.json().catch(() => null);
        setCreateError(err?.detail ?? `Error creating token (${res.status})`);
      }
    } catch {
      setCreateError("Network error — could not reach the server");
    } finally {
      setCreating(false);
    }
  };

  const revokeToken = async (id: string) => {
    await fetch(`/api/tokens/${id}`, { method: "DELETE" });
    await fetchTokens();
  };

  const viewAudit = async (tokenId: string) => {
    const res = await fetch(`/api/tokens/${tokenId}/audit`);
    const entries: TokenAuditEntry[] = await res.json();
    setAuditLog({ tokenId, entries });
  };

  const copyToken = async (token: string) => {
    await navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const mcpConfigSnippet = (token: string) =>
    JSON.stringify(
      {
        servers: {
          "oddysey-rag": {
            type: "sse",
            url: "http://localhost:3010/sse",
            headers: { Authorization: `Bearer ${token}` },
          },
        },
      },
      null,
      2
    );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-serif text-primary tracking-tight">MCP Tokens</h2>
          <p className="text-muted-foreground text-sm">Manage access tokens for MCP clients</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) setCreateError(null); }}>
          <DialogTrigger render={<span />} nativeButton={false}>
            <Button>
              <Plus className="h-4 w-4 mr-1" /> New Token
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-serif">Create MCP Token</DialogTitle>
              <DialogDescription>Generate a new token for AI client access</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Name</label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Carlos - VS Code"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Scopes</label>
                <div className="flex gap-3">
                  {["read", "write", "admin"].map((scope) => (
                    <label key={scope} className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={newScopes.includes(scope)}
                        onChange={(e) =>
                          setNewScopes(
                            e.target.checked
                              ? [...newScopes, scope]
                              : newScopes.filter((s) => s !== scope)
                          )
                        }
                        className="rounded border-border"
                      />
                      {scope}
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Expires</label>
                  <Input
                    type="date"
                    value={newExpiry}
                    onChange={(e) => setNewExpiry(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Rate limit (RPM)</label>
                  <Input
                    type="number"
                    value={newRateLimit}
                    onChange={(e) => setNewRateLimit(parseInt(e.target.value) || 60)}
                  />
                </div>
              </div>
              {createError && (
                <p className="text-sm text-destructive">{createError}</p>
              )}
              <Button onClick={createToken} disabled={creating || !newName.trim()} className="w-full">
                {creating ? "Creating…" : "Generate Token"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Token revealed dialog */}
      {revealedToken && (
        <div className="border-2 border-secondary bg-secondary/5 rounded-md p-4 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-secondary" />
            <p className="text-sm font-medium">Copy this token now. It will not be shown again.</p>
          </div>
          <div className="bg-muted rounded-md p-3 font-mono text-sm break-all">{revealedToken}</div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => copyToken(revealedToken)}>
              <Copy className="h-4 w-4 mr-1" /> {copied ? "Copied!" : "Copy Token"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => copyToken(mcpConfigSnippet(revealedToken))}>
              <Copy className="h-4 w-4 mr-1" /> Copy MCP Config
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRevealedToken(null)}>
              Dismiss
            </Button>
          </div>
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground">.vscode/mcp.json snippet</summary>
            <pre className="mt-2 bg-muted rounded-md p-2 overflow-x-auto font-mono text-xs">
              {mcpConfigSnippet(revealedToken)}
            </pre>
          </details>
        </div>
      )}

      {/* Token list */}
      <div className="space-y-2">
        {loading ? (
          <div className="border border-border/50 bg-card rounded-md p-8 text-center">
            <p className="text-muted-foreground">Loading tokens…</p>
          </div>
        ) : tokens.length === 0 ? (
          <div className="border border-border/50 bg-card rounded-md p-8 text-center">
            <Key className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">No tokens yet. Create one to get started.</p>
          </div>
        ) : (
          tokens.map((token) => (
            <div
              key={token.id}
              className={`border border-border/50 bg-card rounded-md p-4 shadow-sm ${!token.is_active ? "opacity-60" : ""}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm">{token.name}</p>
                    {!token.is_active && <Badge variant="destructive">Revoked</Badge>}
                  </div>
                  <p className="font-mono text-xs text-muted-foreground">{token.token_prefix}…</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    {token.scopes.map((scope) => (
                      <Badge key={scope} variant="outline">{scope}</Badge>
                    ))}
                    <span className="text-xs text-muted-foreground">
                      {token.rate_limit_rpm} RPM
                    </span>
                    {token.expires_at && (
                      <span className="text-xs text-muted-foreground">
                        Expires {new Date(token.expires_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" onClick={() => viewAudit(token.id)}>
                    <Eye className="h-4 w-4" />
                  </Button>
                  {token.is_active && (
                    <Button variant="ghost" size="sm" onClick={() => revokeToken(token.id)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                <span>Used {token.usage_count} times</span>
                {token.last_used_at && (
                  <span>Last used {new Date(token.last_used_at).toLocaleString()}</span>
                )}
                <span>Created {new Date(token.created_at).toLocaleString()}</span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Audit log dialog */}
      {auditLog && (
        <div className="border border-border/50 bg-card rounded-md shadow-sm">
          <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
            <h3 className="font-serif text-lg text-primary">
              Audit Log ({auditLog.entries.length} entries)
            </h3>
            <Button variant="ghost" size="sm" onClick={() => setAuditLog(null)}>
              Close
            </Button>
          </div>
          <div className="divide-y divide-border/30 max-h-64 overflow-y-auto">
            {auditLog.entries.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground text-center">No audit entries</p>
            ) : (
              auditLog.entries.map((entry) => (
                <div key={entry.id} className="px-4 py-2 flex items-center gap-3 text-sm">
                  <Badge variant={entry.action === "revoked" ? "destructive" : "outline"}>
                    {entry.action}
                  </Badge>
                  <span className="font-mono text-xs text-muted-foreground">
                    {entry.ip_address ?? "—"}
                  </span>
                  {entry.tool_name && (
                    <span className="text-xs text-muted-foreground">{entry.tool_name}</span>
                  )}
                  <time className="ml-auto font-mono text-xs text-muted-foreground">
                    {new Date(entry.created_at).toLocaleString()}
                  </time>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Crypto helpers
function generateRandomString(length: number): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const values = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(values, (v) => chars[v % chars.length]).join("");
}

async function sha256(message: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}
