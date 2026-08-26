import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Plus, FileSpreadsheet, Presentation, MoreHorizontal, Check, Minus, Trash2, Pencil } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { StatusBadge } from "@/components/status-badge";
import { deleteSession, useSessions } from "@/lib/sessions-store";

export const Route = createFileRoute("/sessions/")({
  head: () => ({
    meta: [
      { title: "Sessions — AutoHR" },
      { name: "description", content: "All induction sessions." },
    ],
  }),
  component: SessionsPage,
});

function SessionsPage() {
  const sessions = useSessions();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const filtered = sessions.filter((s) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      s.title.toLowerCase().includes(q) ||
      s.department.toLowerCase().includes(q) ||
      s.trainer.toLowerCase().includes(q)
    );
  });

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteSession(pendingDelete);
      toast.success("Session deleted");
    } catch (err) {
      console.error(err);
      toast.error("Failed to delete session on backend");
    }
    setPendingDelete(null);
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Sessions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage every induction session across departments.
          </p>
        </div>
        <Button asChild size="lg">
          <Link to="/sessions/new">
            <Plus className="h-4 w-4" />
            Create Session
          </Link>
        </Button>
      </header>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 gap-4 pb-3">
          <CardTitle className="text-base font-semibold">
            All sessions <span className="text-muted-foreground font-normal">({filtered.length})</span>
          </CardTitle>
          <Input
            placeholder="Search by title, department or trainer"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="max-w-sm"
          />
        </CardHeader>
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-sm text-muted-foreground">
                {sessions.length === 0
                  ? "No induction sessions created yet."
                  : "No sessions match your search."}
              </p>
              {sessions.length === 0 && (
                <Button className="mt-4" onClick={() => navigate({ to: "/sessions/new" })}>
                  <Plus className="h-4 w-4" /> Create First Session
                </Button>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Session name</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Trainer</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-center">Presentation</TableHead>
                  <TableHead className="text-center">Employees</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>
                      <Link
                        to="/sessions/$id"
                        params={{ id: s.id }}
                        className="font-medium hover:text-primary transition-colors"
                      >
                        {s.title}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{s.department}</TableCell>
                    <TableCell className="text-muted-foreground">{s.trainer}</TableCell>
                    <TableCell className="text-muted-foreground">{s.date}</TableCell>
                    <TableCell>
                      <StatusBadge status={s.status} />
                    </TableCell>
                    <TableCell className="text-center">
                      <UploadIndicator ok={!!s.presentationFile} icon={<Presentation className="h-3.5 w-3.5" />} />
                    </TableCell>
                    <TableCell className="text-center">
                      <UploadIndicator ok={!!s.employeesFile} icon={<FileSpreadsheet className="h-3.5 w-3.5" />} />
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link to="/sessions/$id" params={{ id: s.id }}>Open</Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <Link to="/sessions/$id" params={{ id: s.id }}>
                              <Pencil className="h-4 w-4" /> Edit
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => setPendingDelete(s.id)}
                          >
                            <Trash2 className="h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this session?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove the session and its uploaded files. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function UploadIndicator({ ok, icon }: { ok: boolean; icon: React.ReactNode }) {
  if (ok) {
    return (
      <span className="inline-flex items-center gap-1.5 text-success text-xs font-medium">
        {icon}
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground/60 text-xs">
      {icon}
      <Minus className="h-3.5 w-3.5" />
    </span>
  );
}
