"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  LayoutDashboard,
  Files,
  Upload,
  Search,
  PieChart,
  Activity,
  MessageSquare,
  Key,
  Settings,
} from "lucide-react";

const pages = [
  { href: "/", label: "Overview", icon: LayoutDashboard, keywords: "dashboard home stats" },
  { href: "/sources", label: "Sources", icon: Files, keywords: "documents files browse" },
  { href: "/ingest", label: "Ingest", icon: Upload, keywords: "upload import add" },
  { href: "/search", label: "Search", icon: Search, keywords: "query find playground" },
  { href: "/coverage", label: "Coverage", icon: PieChart, keywords: "matrix heatmap gaps" },
  { href: "/jobs", label: "Jobs", icon: Activity, keywords: "history pipeline status" },
  { href: "/feedback", label: "Feedback", icon: MessageSquare, keywords: "ratings quality" },
  { href: "/tokens", label: "Tokens", icon: Key, keywords: "api keys mcp auth" },
  { href: "/settings", label: "Settings", icon: Settings, keywords: "config health" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const navigate = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />
      {/* Dialog */}
      <div className="absolute left-1/2 top-[20%] w-full max-w-lg -translate-x-1/2">
        <Command
          className="rounded-lg border border-border bg-popover text-popover-foreground shadow-2xl overflow-hidden"
          shouldFilter={true}
        >
          <Command.Input
            placeholder="Type a page name or keyword…"
            className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
            autoFocus
          />
          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>
            <Command.Group heading="Pages" className="px-1 py-1.5 text-xs font-medium text-muted-foreground">
              {pages.map((page) => (
                <Command.Item
                  key={page.href}
                  value={`${page.label} ${page.keywords}`}
                  onSelect={() => navigate(page.href)}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm cursor-pointer transition-colors data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground"
                >
                  <page.icon className="h-4 w-4 text-muted-foreground" />
                  {page.label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
          <div className="border-t border-border px-3 py-2">
            <p className="text-xs text-muted-foreground">
              <kbd className="px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] font-mono">↵</kbd>{" "}
              to select{" "}
              <kbd className="px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] font-mono">↑↓</kbd>{" "}
              to navigate{" "}
              <kbd className="px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] font-mono">esc</kbd>{" "}
              to close
            </p>
          </div>
        </Command>
      </div>
    </div>
  );
}
