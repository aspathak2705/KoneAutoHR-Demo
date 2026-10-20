import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL, type SessionStatus } from "@/lib/sessions-store";
import { cn } from "@/lib/utils";

const styles: Partial<Record<SessionStatus, string>> = {
  PENDING: "bg-muted text-muted-foreground border-border",
  UPLOADED: "bg-muted text-muted-foreground border-border",
  VALIDATING: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  PARSING: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  GENERATING_SCRIPT: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  GENERATING_AUDIO: "bg-purple-500/10 text-purple-600 border-purple-500/20",
  REGISTERING_ASSETS: "bg-indigo-500/10 text-indigo-600 border-indigo-500/20",
  VERIFYING: "bg-indigo-500/10 text-indigo-600 border-indigo-500/20",
  READY: "bg-success/10 text-success border-success/20",
  COMPLETED: "bg-info/10 text-info border-info/20",
  FAILED: "bg-destructive/10 text-destructive border-destructive/20",
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <Badge variant="outline" className={cn("font-medium text-xs", styles[status] || "bg-muted text-muted-foreground")}>
      {STATUS_LABEL[status] || status}
    </Badge>
  );
}
