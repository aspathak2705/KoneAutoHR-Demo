import { useState } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { LayoutDashboard, CalendarDays, Plus, Bot, Menu, X, Cpu } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { AuthStatusBadge } from "./auth-status-badge";

const primaryNav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/sessions", label: "Inductions", icon: CalendarDays, exact: false },
  { to: "/sessions/new", label: "Create Induction", icon: Plus, exact: true },
];

const diagnosticNav = [
  { to: "/meeting-bot", label: "Bot Diagnostics", icon: Bot, exact: true },
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const renderNavLinks = (onNavigate?: () => void) => (
    <div className="flex flex-col h-full justify-between">
      <div className="space-y-6">
        <div>
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
            Workspaces
          </div>
          <nav className="space-y-1">
            {primaryNav.map((item) => {
              const active = item.exact ? pathname === item.to : pathname.startsWith(item.to);
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-semibold"
                      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div>
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 flex items-center gap-1">
            <Cpu className="h-3 w-3" /> Advanced Diagnostics
          </div>
          <nav className="space-y-1">
            {diagnosticNav.map((item) => {
              const active = item.exact ? pathname === item.to : pathname.startsWith(item.to);
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-xs font-medium transition-colors opacity-80 hover:opacity-100",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-semibold"
                      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="pt-4 border-t border-sidebar-border/40 text-[11px] text-muted-foreground px-3">
        KONE AutoHR v0.1-rc
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 z-20 w-60 flex-col border-r border-border bg-sidebar">
        <div className="flex h-16 items-center px-5 border-b border-sidebar-border">
          <KoneLogo />
        </div>
        <div className="flex-1 px-3 py-4">
          {renderNavLinks()}
        </div>
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative flex w-64 max-w-[80vw] flex-col bg-sidebar border-r border-border p-4 shadow-xl z-10">
            <div className="flex items-center justify-between pb-4 border-b border-sidebar-border mb-4">
              <KoneLogo />
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1">
              {renderNavLinks(() => setMobileMenuOpen(false))}
            </div>
          </div>
        </div>
      )}

      {/* Main column */}
      <div className="flex-1 md:pl-60 flex flex-col min-w-0">
        <header className="sticky top-0 z-10 h-16 border-b border-border bg-background/80 backdrop-blur">
          <div className="h-full flex items-center gap-3 px-4 md:px-6">
            {/* Mobile Hamburger Button */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="md:hidden p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
              aria-label="Open navigation menu"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="md:hidden">
              <KoneLogo />
            </div>
            <div className="flex-grow" />

            <AuthStatusBadge />

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
          <div className="mx-auto w-full max-w-7xl px-4 md:px-6 py-6 md:py-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
