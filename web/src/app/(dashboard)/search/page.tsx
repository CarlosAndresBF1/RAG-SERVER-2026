"use client";

import { useState } from "react";
import { Search as SearchIcon, Loader2, ThumbsUp, ThumbsDown, ExternalLink, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { SearchResponse, EvidenceItem } from "@/types/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [messageType, setMessageType] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [topK, setTopK] = useState(8);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [showMeta, setShowMeta] = useState(false);

  const doSearch = async (q?: string) => {
    const searchQuery = q ?? query;
    if (!searchQuery.trim()) return;
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          message_type: messageType || undefined,
          source_type: sourceType || undefined,
          top_k: topK,
        }),
      });
      const data: SearchResponse = await res.json();
      setResult(data);
      setHistory((prev) => [searchQuery, ...prev.filter((h) => h !== searchQuery)].slice(0, 10));
    } catch {
      // error silently
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Search Playground</h2>
        <p className="text-muted-foreground text-sm">Query the knowledge base and explore results</p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
            placeholder="Search the knowledge base..."
            className="pl-9"
            disabled={loading}
          />
        </div>
        <Button onClick={() => doSearch()} disabled={loading || !query.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Message type:</label>
          <Input
            value={messageType}
            onChange={(e) => setMessageType(e.target.value)}
            placeholder="e.g. pacs.008"
            className="w-36 h-8 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Source type:</label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value="">All</option>
            <option value="annex_b_spec">Annex B Spec</option>
            <option value="annex_a_spec">Annex A Spec</option>
            <option value="annex_c_spec">Annex C Spec</option>
            <option value="tech_doc">Tech Doc</option>
            <option value="php_code">PHP Code</option>
            <option value="xml_example">XML Example</option>
            <option value="postman_collection">Postman</option>
            <option value="alias_doc">Aliases</option>
            <option value="qr_doc">QR</option>
            <option value="banking_doc">Home Banking</option>
            <option value="integration_doc">Integration</option>
            <option value="pdf_doc">PDF Document</option>
            <option value="word_doc">Word Document</option>
            <option value="generic_text">General Text</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Top K:</label>
          <input
            type="range"
            min={1}
            max={20}
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
            className="w-24"
          />
          <span className="font-mono text-sm">{topK}</span>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {result.evidence.length} results in {result.metadata.search_time_ms}ms
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowMeta(!showMeta)}
            >
              <Info className="h-4 w-4 mr-1" />
              Metadata
            </Button>
          </div>

          {/* Search metadata panel */}
          {showMeta && (
            <div className="border border-border/50 bg-muted/30 rounded-md p-4 space-y-2">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Search Metadata</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Candidates</p>
                  <p className="font-mono">{result.metadata.total_candidates}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Latency</p>
                  <p className="font-mono">{result.metadata.search_time_ms}ms</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Results</p>
                  <p className="font-mono">{result.evidence.length}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Gaps</p>
                  <p className="font-mono">{result.gaps.length}</p>
                </div>
              </div>
            </div>
          )}

          {result.evidence.map((ev, i) => (
            <EvidenceCard key={i} evidence={ev} index={i} query={result.query} />
          ))}

          {result.gaps.length > 0 && (
            <div className="border border-amber-300/50 bg-amber-50 dark:bg-amber-950/20 rounded-md p-4">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200 mb-2">Gaps detected</p>
              <ul className="text-sm text-amber-700 dark:text-amber-300 space-y-1">
                {result.gaps.map((gap, i) => (
                  <li key={i}>• {gap}</li>
                ))}
              </ul>
            </div>
          )}

          {result.followups.length > 0 && (
            <div className="border border-border/50 bg-card rounded-md p-4">
              <p className="text-sm font-medium mb-2">Suggested follow-ups</p>
              <div className="flex flex-wrap gap-2">
                {result.followups.map((f, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQuery(f);
                      doSearch(f);
                    }}
                    className="text-xs bg-muted px-2 py-1 rounded-md hover:bg-muted/80 transition-colors"
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 0 && !loading && (
        <div className="border border-border/50 bg-card rounded-md p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Recent searches</p>
          <div className="flex flex-wrap gap-2">
            {history.map((h, i) => (
              <button
                key={i}
                onClick={() => {
                  setQuery(h);
                  doSearch(h);
                }}
                className="text-xs bg-muted px-2 py-1 rounded-md hover:bg-muted/80 transition-colors"
              >
                {h}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EvidenceCard({ evidence, index, query }: { evidence: EvidenceItem; index: number; query: string }) {
  const relevancePercent = Math.round(evidence.relevance * 100);
  const [feedbackSent, setFeedbackSent] = useState<"up" | "down" | null>(null);

  const sendFeedback = async (rating: 1 | -1) => {
    const chunkId = evidence.citations[0]
      ? evidence.citations[0].source_path
      : "00000000-0000-0000-0000-000000000000";
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, chunk_id: chunkId, rating }),
      });
      setFeedbackSent(rating === 1 ? "up" : "down");
    } catch {
      // fail silently
    }
  };

  return (
    <div className="border border-border/50 bg-card rounded-md shadow-sm p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">#{index + 1}</span>
          <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full"
              style={{ width: `${relevancePercent}%` }}
            />
          </div>
          <span className="font-mono text-xs text-muted-foreground">{relevancePercent}%</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            {evidence.message_type && <Badge variant="outline">{evidence.message_type}</Badge>}
            {evidence.source_type && <Badge variant="secondary">{evidence.source_type}</Badge>}
          </div>
          {/* Feedback thumbs */}
          <div className="flex gap-1 ml-2">
            <button
              onClick={() => sendFeedback(1)}
              disabled={feedbackSent !== null}
              className={`p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors ${feedbackSent === "up" ? "text-green-600 bg-green-100 dark:bg-green-900/30" : "text-muted-foreground"}`}
              title="Helpful"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => sendFeedback(-1)}
              disabled={feedbackSent !== null}
              className={`p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors ${feedbackSent === "down" ? "text-red-600 bg-red-100 dark:bg-red-900/30" : "text-muted-foreground"}`}
              title="Not helpful"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
      <pre className="text-sm whitespace-pre-wrap font-mono bg-muted/30 p-3 rounded-md">{evidence.text}</pre>
      {evidence.citations.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {evidence.citations.map((c, j) => (
            <a
              key={j}
              href={`/sources?search=${encodeURIComponent(c.source_path)}`}
              className="inline-flex items-center gap-1 text-xs font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded hover:bg-primary/10 hover:text-primary transition-colors"
            >
              {c.source_path.split("/").pop()} §{c.section} #{c.chunk_index}
              <ExternalLink className="h-3 w-3" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
