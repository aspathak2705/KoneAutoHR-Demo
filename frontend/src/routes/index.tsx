import { createFileRoute, Link } from "@tanstack/react-router";
import { Plus, ArrowRight, CalendarDays, Users, Clock, BookOpen, User, Calendar } from "lucide-react";
import { useMemo, useState, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import {
  getInductionContent,
  useSessions,
  getPresentations,
  getEmployeeLists,
  SavedPresentation,
  SavedEmployeeList,
  type InductionSession
} from "@/lib/sessions-store";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — AutoHR" },
      { name: "description", content: "Your induction sessions at a glance." },
    ],
  }),
  component: DashboardPage,
});

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function DashboardPage() {
  const sessions = useSessions();
  const today = todayISO();
  const [presentations, setPresentations] = useState<SavedPresentation[]>([]);
  const [employeeLists, setEmployeeLists] = useState<SavedEmployeeList[]>([]);

  useEffect(() => {
    getPresentations().then((p) => setPresentations(p.slice(0, 3))).catch(console.error);
    getEmployeeLists().then((e) => setEmployeeLists(e.slice(0, 3))).catch(console.error);
  }, []);

  const { todays, upcoming, recent } = useMemo(() => {
    const sorted = [...sessions].sort((a, b) => (a?.date || "").localeCompare(b?.date || ""));
    return {
      todays: sorted.filter((s) => s && s.date === today && s.status !== "COMPLETED"),
      upcoming: sorted.filter((s) => s && s.date > today && s.status !== "COMPLETED").slice(0, 5),
      recent: [...sessions]
        .filter((s) => s && (s.status === "COMPLETED" || s.date < today))
        .sort((a, b) => (b?.date || "").localeCompare(a?.date || ""))
        .slice(0, 5),
    };
  }, [sessions, today]);

  return (
    <div className="space-y-10">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Welcome, HR</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Here's what's happening with your inductions.
          </p>
        </div>
        <Button asChild size="lg">
          <Link to="/sessions/new">
            <Plus className="h-4 w-4 mr-1.5" />
            Create new induction
          </Link>
        </Button>
      </header>

      <Section
        title="Today's sessions"
        empty="No inductions scheduled for today."
        items={todays}
      />

      <Section
        title="Upcoming inductions"
        empty="Nothing scheduled yet."
        items={upcoming}
      />

      {/* Library History sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Saved Presentations card */}
        <Card className="border-border/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-primary" /> Saved Presentations
            </CardTitle>
            <CardDescription>Induction slide decks available for training runs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {presentations.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-3 text-center">No saved presentations yet.</p>
            ) : (
              presentations.map((p) => (
                <div key={p.id} className="p-3 border border-border/60 bg-muted/10 rounded-xl flex items-center justify-between text-sm">
                  <div className="truncate pr-4">
                    <p className="font-semibold text-card-foreground truncate">{p.name}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{p.original_filename}</p>
                  </div>
                  <div className="text-[10px] text-muted-foreground text-right shrink-0">
                    <p>Used {p.session_count} times</p>
                    <p>Last used {new Date(p.last_used).toLocaleDateString()}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Saved Employee Lists card */}
        <Card className="border-border/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" /> Saved Employee Lists
            </CardTitle>
            <CardDescription> attendee records registers for employee batches.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {employeeLists.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-3 text-center">No saved employee lists yet.</p>
            ) : (
              employeeLists.map((e) => (
                <div key={e.id} className="p-3 border border-border/60 bg-muted/10 rounded-xl flex items-center justify-between text-sm">
                  <div className="truncate pr-4">
                    <p className="font-semibold text-card-foreground truncate">{e.name}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{e.original_filename}</p>
                  </div>
                  <div className="text-[10px] text-muted-foreground text-right shrink-0">
                    <p>{e.employee_count} Employees</p>
                    <p>Uploaded {new Date(e.uploaded_at).toLocaleDateString()}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Section
        title="Recent inductions"
        empty="No past inductions yet."
        items={recent}
        muted
      />
    </div>
  );
}

function Section({
  title,
  items,
  empty,
  muted,
}: {
  title: string;
  items: InductionSession[];
  empty: string;
  muted?: boolean;
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {items.length > 0 && (
          <Button variant="ghost" size="sm" asChild>
            <Link to="/sessions">
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        )}
      </div>
      {items.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            {empty}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((s) => (
            <SessionCard key={s.id} session={s} muted={muted} />
          ))}
        </div>
      )}
    </section>
  );
}

function SessionCard({ session, muted }: { session: InductionSession; muted?: boolean }) {
  const content = getInductionContent(session);
  return (
    <Link
      to="/sessions/$id"
      params={{ id: session.id }}
      className="group block"
    >
      <Card className={muted ? "opacity-90 hover:opacity-100 transition" : "hover:border-primary/40 transition"}>
        <CardContent className="p-5 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-semibold truncate group-hover:text-primary transition-colors">
                {session.title}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">{session.department}</p>
            </div>
            <StatusBadge status={session.status} />
          </div>
          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" /> {session.date}
            </span>
            {content.employees.length > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5" /> {content.employees.length} employees
              </span>
            )}
            {content.estimatedMinutes > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" /> ~{content.estimatedMinutes} min
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
