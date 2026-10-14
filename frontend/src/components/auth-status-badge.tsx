import { useState, useEffect } from "react";
import { Lock, LogOut, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { getAuthToken, setAuthToken, clearAuthToken, isUiOnlyMode } from "@/lib/sessions-store";

export function AuthStatusBadge() {
  const [token, setToken] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [inputToken, setInputToken] = useState("");

  const syncAuth = () => {
    setToken(getAuthToken());
  };

  useEffect(() => {
    syncAuth();
    const handleAuthChange = () => syncAuth();
    const handleUnauthorized = () => {
      syncAuth();
      setDialogOpen(true);
    };

    window.addEventListener("autohr:auth-change", handleAuthChange);
    window.addEventListener("autohr:unauthorized", handleUnauthorized);
    window.addEventListener("storage", handleAuthChange);

    return () => {
      window.removeEventListener("autohr:auth-change", handleAuthChange);
      window.removeEventListener("autohr:unauthorized", handleUnauthorized);
      window.removeEventListener("storage", handleAuthChange);
    };
  }, []);

  const handleSave = () => {
    if (!inputToken.trim()) return;
    setAuthToken(inputToken.trim());
    setInputToken("");
    setDialogOpen(false);
  };

  const handleLogout = () => {
    clearAuthToken();
    syncAuth();
  };

  const isDev = import.meta.env.DEV;
  const isUiOnly = isUiOnlyMode();
  const isAuthenticated = Boolean(token);

  if (isUiOnly) {
    return (
      <div className="flex items-center gap-2">
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
          title="Hosted in UI-Only Mode: Live backend connection disabled until Windows runner is connected."
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
          UI-Only Mode
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {isAuthenticated ? (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            {isDev ? "Dev Session" : "Authenticated"}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            title="Log out (clear session token)"
            className="h-8 px-2 text-muted-foreground hover:text-foreground"
          >
            <LogOut className="w-3.5 h-3.5" />
          </Button>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setDialogOpen(true)}
          className="h-8 gap-1.5 text-xs border-amber-500/30 text-amber-600 dark:text-amber-400 hover:bg-amber-500/10"
        >
          <Lock className="w-3.5 h-3.5" />
          Authenticate
        </Button>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-primary" />
              Demo Session Access
            </DialogTitle>
            <DialogDescription>
              Enter the shared demo access token configured for this AutoHR presentation runner.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label htmlFor="token-input" className="text-xs font-semibold text-muted-foreground">
                Session Bearer Token
              </label>
              <Input
                id="token-input"
                type="password"
                placeholder="Paste authorized access token..."
                value={inputToken}
                onChange={(e) => setInputToken(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSave()}
                autoFocus
              />
              <p className="text-[11px] text-muted-foreground">
                Tokens are stored strictly in temporary browser session memory (never permanently written to disk).
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={!inputToken.trim()}>
              Save & Connect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
