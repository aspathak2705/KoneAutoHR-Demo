import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL, type SessionStatus } from "@/lib/sessions-store";
import { cn } from "@/lib/utils";

const styles: Record<SessionStatus, string> = {
  CREATED: "bg-muted text-muted-foreground border-border",
  READY: "bg-success/10 text-success border-success/20",
  RUNNING: "bg-warning/15 text-warning-foreground border-warning/30",
  COMPLETED: "bg-info/10 text-info border-info/20",
  FAILED: "bg-destructive/10 text-destructive border-destructive/20",
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <Badge variant="outline" className={cn("font-medium text-xs", styles[status])}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
