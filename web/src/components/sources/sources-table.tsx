"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { SourceItem } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronLeft, ChevronRight, Eye, ArrowUpDown, Trash2, Loader2, Download } from "lucide-react";

const SOURCE_TYPE_COLORS: Record<string, string> = {
  annex_b_spec: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  php_code: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  xml_example: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  tech_doc: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  postman_collection: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  generic_text: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
};

const SOURCE_TYPES = [
  "annex_b_spec",
  "php_code",
  "xml_example",
  "tech_doc",
  "postman_collection",
  "generic_text",
];

interface Props {
  items: SourceItem[];
  total: number;
  page: number;
  pageSize: number;
  currentSourceType?: string;
}

export function SourcesTable({ items, total, page, pageSize, currentSourceType }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const totalPages = Math.ceil(total / pageSize);
  const [sortKey, setSortKey] = useState<"name" | "chunks" | "date" | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const toggleSort = (key: "name" | "chunks" | "date") => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sortedItems = useMemo(() => {
    if (!sortKey) return items;
    const sorted = [...items].sort((a, b) => {
      if (sortKey === "name") {
        const an = a.source_path.split("/").pop() ?? "";
        const bn = b.source_path.split("/").pop() ?? "";
        return an.localeCompare(bn);
      }
      if (sortKey === "chunks") return a.total_chunks - b.total_chunks;
      if (sortKey === "date") return new Date(a.ingested_at).getTime() - new Date(b.ingested_at).getTime();
      return 0;
    });
    return sortDir === "desc" ? sorted.reverse() : sorted;
  }, [items, sortKey, sortDir]);

  const toggleAll = () => {
    if (selected.size === items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map((i) => i.id)));
    }
  };

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulkDelete = async () => {
    if (selected.size === 0) return;
    setBulkDeleting(true);
    try {
      await Promise.all(
        [...selected].map((id) =>
          fetch(`/api/sources/${id}`, { method: "DELETE" })
        )
      );
      setSelected(new Set());
      router.refresh();
    } finally {
      setBulkDeleting(false);
    }
  };

  const exportCsv = () => {
    const header = "Name,Type,Chunks,Hash,Ingested\n";
    const rows = items
      .map((i) =>
        [i.source_path.split("/").pop(), i.source_type, i.total_chunks, i.file_hash, i.ingested_at].join(",")
      )
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sources-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  function navigate(overrides: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(overrides)) {
      if (v) params.set(k, v);
      else params.delete(k);
    }
    router.push(`/sources?${params.toString()}`);
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-muted-foreground">Filter:</span>
        <Button
          variant={!currentSourceType ? "default" : "outline"}
          size="sm"
          onClick={() => navigate({ source_type: undefined, page: "1" })}
        >
          All
        </Button>
        {SOURCE_TYPES.map((st) => (
          <Button
            key={st}
            variant={currentSourceType === st ? "default" : "outline"}
            size="sm"
            onClick={() => navigate({ source_type: st, page: "1" })}
          >
            {st.replace(/_/g, " ")}
          </Button>
        ))}
        <div className="ml-auto">
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="h-4 w-4 mr-1" />
            CSV
          </Button>
        </div>
      </div>

      {/* Bulk actions bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-muted/50 border border-border/50 rounded-md">
          <span className="text-sm text-muted-foreground">{selected.size} selected</span>
          <Button
            variant="destructive"
            size="sm"
            onClick={bulkDelete}
            disabled={bulkDeleting}
          >
            {bulkDeleting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1" />}
            Delete selected
          </Button>
          <Button variant="outline" size="sm" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="border border-border/50 rounded-md bg-card shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  checked={items.length > 0 && selected.size === items.length}
                  onChange={toggleAll}
                  className="rounded border-border"
                />
              </TableHead>
              <TableHead>
                <button onClick={() => toggleSort("name")} className="inline-flex items-center gap-1 hover:text-foreground">
                  Name <ArrowUpDown className="h-3 w-3" />
                </button>
              </TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">
                <button onClick={() => toggleSort("chunks")} className="inline-flex items-center gap-1 hover:text-foreground">
                  Chunks <ArrowUpDown className="h-3 w-3" />
                </button>
              </TableHead>
              <TableHead>Hash</TableHead>
              <TableHead>
                <button onClick={() => toggleSort("date")} className="inline-flex items-center gap-1 hover:text-foreground">
                  Ingested <ArrowUpDown className="h-3 w-3" />
                </button>
              </TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No sources found
                </TableCell>
              </TableRow>
            ) : (
              sortedItems.map((item) => (
                <TableRow key={item.id} className={selected.has(item.id) ? "bg-muted/30" : ""}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selected.has(item.id)}
                      onChange={() => toggleOne(item.id)}
                      className="rounded border-border"
                    />
                  </TableCell>
                  <TableCell className="font-medium max-w-xs truncate">
                    {item.source_path.split("/").pop()}
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${SOURCE_TYPE_COLORS[item.source_type] ?? SOURCE_TYPE_COLORS.generic_text}`}
                    >
                      {item.source_type.replace(/_/g, " ")}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">{item.total_chunks}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {item.file_hash.slice(0, 12)}…
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(item.ingested_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <Link href={`/sources/${item.id}`}>
                      <Button variant="ghost" size="sm">
                        <Eye className="h-4 w-4" />
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {total} source{total !== 1 ? "s" : ""} · Page {page} of {totalPages}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => navigate({ page: String(page - 1) })}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => navigate({ page: String(page + 1) })}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
