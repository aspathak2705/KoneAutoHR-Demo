import { Link, useRouterState } from "@tanstack/react-router";
import { LayoutDashboard, CalendarDays, Plus, BarChart3, Search, Bot } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/sessions", label: "Inductions", icon: CalendarDays, exact: false },
  { to: "/sessions/new", label: "Create induction", icon: Plus, exact: true },
  { to: "/reports", label: "Reports", icon: BarChart3, exact: true },
  { to: "/meeting-bot", label: "Meeting Bot", icon: Bot, exact: true },
];

function KoneLogo() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-9 items-center justify-center rounded-md bg-primary px-2.5">
        <span className="text-primary-foreground font-semibold tracking-tight text-lg leading-none">
          KONE
        </span>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Sidebar */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 z-20 w-60 flex-col border-r border-border bg-sidebar">
        <div className="flex h-16 items-center px-5 border-b border-sidebar-border">
          <KoneLogo />
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map((item) => {
            const active = item.exact ? pathname === item.to : pathname.startsWith(item.to);
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex-1 md:pl-60 flex flex-col min-w-0">
        <header className="sticky top-0 z-10 h-16 border-b border-border bg-background/80 backdrop-blur">
          <div className="h-full flex items-center gap-4 px-6">
            <div className="md:hidden">
              <KoneLogo />
            </div>
            <div className="flex-grow" />

            <Link 
              to="/profile" 
              className="flex items-center gap-3 pl-2 border-l border-border hover:opacity-80 transition-opacity"
            >
              <div className="h-9 w-9 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
                HR
              </div>
            </Link>
          </div>
        </header>

        <main className="flex-1 min-w-0">
          <div className="mx-auto w-full max-w-7xl px-6 py-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
