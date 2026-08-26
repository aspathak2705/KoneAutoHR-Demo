import { createFileRoute, Link } from "@tanstack/react-router";
import { BarChart3, Users, Calendar, ArrowUpRight, GraduationCap, Info } from "lucide-react";
import { useState, useEffect } from "react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getAnalyticsDashboard, getAnalyticsRuns } from "@/lib/sessions-store";
import { StatusBadge } from "@/components/status-badge";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Reports & Analytics — AutoHR" },
      { name: "description", content: "Analytics on employee induction sessions." },
    ],
  }),
  component: ReportsPage,
});

interface AnalyticsSummary {
  total_inductions: number;
  employees_onboarded: number;
  departments_covered: string;
  compliance_rate: number;
}

function ReportsPage() {
  const [stats, setStats] = useState<AnalyticsSummary>({
    total_inductions: 0,
    employees_onboarded: 0,
    departments_covered: "—",
    compliance_rate: 0,
  });
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getAnalyticsDashboard(), getAnalyticsRuns()])
      .then(([dashboard, runsData]) => {
        setStats(dashboard);
        setRuns(runsData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="py-20 text-center text-sm text-muted-foreground animate-pulse">
        Loading reports & analytics...
      </div>
    );
  }

  const noSessionsExist = stats.total_inductions === 0;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Reports & Analytics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Track induction completions, employee attendance, and departmental analytics.
        </p>
      </header>

      {noSessionsExist ? (
        <div className="flex items-center gap-3 p-4 border border-info/20 bg-info/5 text-info text-sm rounded-xl">
          <Info className="h-5 w-5 text-primary shrink-0" />
          <div>
            <p className="font-semibold text-primary">No induction runs available</p>
            <p className="text-muted-foreground text-xs mt-0.5">
              Create and run your first induction session to populate real-time completion analytics and logs.
            </p>
          </div>
        </div>
      ) : null}

      {/* Grid of metrics cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <Card className="border-border/60">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Total Inductions</CardDescription>
            <CardTitle className="text-3xl font-bold">
              {noSessionsExist ? "—" : stats.total_inductions}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Induction sessions scheduled</p>
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Compliance Rate</CardDescription>
            <CardTitle className="text-3xl font-bold">
              {noSessionsExist ? "—" : `${stats.compliance_rate}%`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Completion vs scheduled ratio</p>
          </CardContent>
        </Card>
      </div>

      {/* Sessions history table card */}
      <Card className="border-border/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-primary" /> Training Run Log
          </CardTitle>
          <CardDescription>Historical run logs of active and completed inductions.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {runs.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground italic">
              No induction runs available. Complete an induction run to view logs here.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Session</TableHead>
                  <TableHead>Presentation</TableHead>
                  <TableHead className="text-center">Employees</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-center">Meeting</TableHead>
                  <TableHead className="text-center">Duration</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-semibold">
                      <Link to="/sessions/$id" params={{ id: s.id }} className="hover:text-primary transition-colors">
                        {s.title}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{s.presentation}</TableCell>
                    <TableCell className="text-center text-muted-foreground">{s.employees}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{s.created}</TableCell>
                    <TableCell>
                      <StatusBadge status={s.status} />
                    </TableCell>
                    <TableCell className="text-center text-muted-foreground text-xs">{s.meeting || "—"}</TableCell>
                    <TableCell className="text-center text-muted-foreground text-xs">{s.duration || "—"}</TableCell>
                    <TableCell>
                      <Link to="/sessions/$id" params={{ id: s.id }} className="text-primary hover:underline inline-flex items-center gap-0.5 text-xs font-semibold">
                        Open <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
