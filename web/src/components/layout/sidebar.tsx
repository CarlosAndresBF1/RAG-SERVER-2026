import Link from "next/link";
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
  Users,
  ScrollText,
  X,
} from "lucide-react";

interface SidebarProps {
  open?: boolean;
  onClose?: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const links = [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/sources", label: "Sources", icon: Files },
    { href: "/ingest", label: "Ingest", icon: Upload },
    { href: "/search", label: "Search", icon: Search },
    { href: "/coverage", label: "Coverage", icon: PieChart },
    { href: "/jobs", label: "Jobs", icon: Activity },
    { href: "/feedback", label: "Feedback", icon: MessageSquare },
    { href: "/tokens", label: "Tokens", icon: Key },
    { href: "/users", label: "Users", icon: Users },
    { href: "/audit", label: "Audit Log", icon: ScrollText },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  const nav = (
    <>
      <div className="h-14 flex items-center justify-between px-4 border-b border-sidebar-border bg-sidebar/50">
        <h1 className="font-serif text-lg text-primary font-bold tracking-tight">Odyssey RAG</h1>
        {onClose && (
          <button onClick={onClose} className="md:hidden inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-sidebar-accent" aria-label="Close sidebar">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={onClose}
                className="flex items-center gap-3 px-3 py-2 text-sm font-medium text-sidebar-foreground rounded-md hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
              >
                <Icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <div className="hidden md:flex w-64 flex-shrink-0 bg-sidebar border-r border-sidebar-border h-full flex-col font-sans">
        {nav}
      </div>
      {/* Mobile sidebar overlay */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={onClose} />
          <div className="relative w-64 h-full bg-sidebar border-r border-sidebar-border flex flex-col font-sans animate-in slide-in-from-left duration-200">
            {nav}
          </div>
        </div>
      )}
    </>
  );
}
