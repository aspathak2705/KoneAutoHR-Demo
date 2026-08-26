import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { User, ShieldAlert, Sparkles, Building, Bot, Save } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getConfiguration, saveConfiguration, getAgentConfig, connectAgentMicrosoft, disconnectAgentMicrosoft, AgentConfiguration } from "@/lib/sessions-store";
import { Key } from "lucide-react";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Profile & AI Persona — AutoHR" },
      { name: "description", content: "Customize your HR profile and AI Persona settings." },
    ],
  }),
  component: ProfilePage,
});

interface ProfileSettings {
  companyName: string;
  companyDomain: string;
  aiName: string;
  trainerName: string;
  aiRole: string;
  aiTone: string;
  aiStyle: string;
}

const DEFAULT_SETTINGS: ProfileSettings = {
  companyName: "KONE",
  companyDomain: "kone.com",
  aiName: "KONE AI Induction Officer",
  trainerName: "KONE AI Trainer",
  aiRole: "HR Induction Officer",
  aiTone: "Professional, Friendly",
  aiStyle: "Conversational",
};

function ProfilePage() {
  const [settings, setSettings] = useState<ProfileSettings>(DEFAULT_SETTINGS);
  const [agentConfig, setAgentConfig] = useState<AgentConfiguration | null>(null);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    getConfiguration()
      .then((cfg) => {
        if (cfg) {
          setSettings({
            companyName: cfg.company_name,
            companyDomain: cfg.company_domain,
            aiName: cfg.ai_officer_name,
            trainerName: cfg.ai_trainer_name,
            aiRole: cfg.ai_role_description,
            aiTone: cfg.vocal_tone,
            aiStyle: cfg.communication_style,
          });
        }
      })
      .catch((err) => {
        console.log("No configuration found, using defaults", err);
      });

    getAgentConfig()
      .then((cfg) => {
        setAgentConfig(cfg);
      })
      .catch((err) => {
        console.log("Failed to load agent configuration", err);
      });
  }, []);

  const handleSave = () => {
    const payload = {
      company_name: settings.companyName,
      company_domain: settings.companyDomain,
      ai_officer_name: settings.aiName,
      ai_trainer_name: settings.trainerName,
      ai_role_description: settings.aiRole,
      vocal_tone: settings.aiTone,
      communication_style: settings.aiStyle,
    };
    saveConfiguration(payload)
      .then(() => {
        toast.success("Profile and AI Persona configurations saved to database!");
      })
      .catch((err: any) => {
        toast.error(err.message || "Failed to save configuration to database");
      });
  };

  const handleConnect = () => {
    setConnecting(true);
    toast.info("Opening Microsoft sign-in window. Please authenticate on the screen...");
    connectAgentMicrosoft()
      .then((cfg) => {
        setAgentConfig(cfg);
        toast.success("Microsoft Account connected successfully!");
      })
      .catch((err: any) => {
        toast.error(err.message || "Microsoft account connection failed.");
      })
      .finally(() => {
        setConnecting(false);
      });
  };

  const handleDisconnect = () => {
    disconnectAgentMicrosoft()
      .then((cfg) => {
        setAgentConfig(cfg);
        toast.success("Microsoft Account disconnected.");
      })
      .catch((err: any) => {
        toast.error(err.message || "Failed to disconnect account.");
      });
  };

  return (
    <div className="space-y-8 max-w-4xl">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Profile & AI Persona</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Customize the identities and behaviors used by the AI context generation engine.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          {/* Company configurations card */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Building className="h-5 w-5 text-primary" /> Company Profile
              </CardTitle>
              <CardDescription>Configure host organization identifiers.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="companyName" className="text-xs font-semibold text-muted-foreground">Company Name</label>
                  <Input
                    id="companyName"
                    value={settings.companyName}
                    onChange={(e) => setSettings({ ...settings, companyName: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="companyDomain" className="text-xs font-semibold text-muted-foreground">Company Domain</label>
                  <Input
                    id="companyDomain"
                    value={settings.companyDomain}
                    onChange={(e) => setSettings({ ...settings, companyDomain: e.target.value })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* AI Persona configurations card */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" /> AI Agent Persona
              </CardTitle>
              <CardDescription>Identity and character variables used in script narration templates.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="aiName" className="text-xs font-semibold text-muted-foreground">AI Officer Name</label>
                  <Input
                    id="aiName"
                    value={settings.aiName}
                    onChange={(e) => setSettings({ ...settings, aiName: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="trainerName" className="text-xs font-semibold text-muted-foreground">AI Trainer Name</label>
                  <Input
                    id="trainerName"
                    value={settings.trainerName}
                    onChange={(e) => setSettings({ ...settings, trainerName: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="aiRole" className="text-xs font-semibold text-muted-foreground">AI Role Description</label>
                <Input
                  id="aiRole"
                  value={settings.aiRole}
                  onChange={(e) => setSettings({ ...settings, aiRole: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">AI Vocal Tone</label>
                  <Select
                    value={settings.aiTone}
                    onValueChange={(val) => setSettings({ ...settings, aiTone: val })}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select tone" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Professional, Friendly">Professional, Friendly</SelectItem>
                      <SelectItem value="Warm, Empathetic">Warm, Empathetic</SelectItem>
                      <SelectItem value="Direct, Instructive">Direct, Instructive</SelectItem>
                      <SelectItem value="Polite, Formal">Polite, Formal</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Communication Style</label>
                  <Select
                    value={settings.aiStyle}
                    onValueChange={(val) => setSettings({ ...settings, aiStyle: val })}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select style" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Conversational">Conversational</SelectItem>
                      <SelectItem value="Structured & Explanatory">Structured & Explanatory</SelectItem>
                      <SelectItem value="Interactive & Question-based">Interactive & Question-based</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Microsoft Account integration card */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Key className="h-5 w-5 text-primary" /> Microsoft Teams Account
              </CardTitle>
              <CardDescription>Connect a Microsoft host account to authenticate the AutoHR bot when joining Teams.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 border border-border/40 bg-muted/10 rounded-xl gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-semibold">
                    Connection Status:{" "}
                    <span className={agentConfig?.is_connected ? "text-green-500" : "text-amber-500"}>
                      {agentConfig?.is_connected ? "Connected" : "Disconnected"}
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {agentConfig?.is_connected
                      ? `Authenticated as: ${agentConfig.email || "connected@microsoft.com"}`
                      : "The bot will join meetings using an anonymous guest profile until an account is connected."}
                  </p>
                </div>
                <div className="flex gap-2">
                  {agentConfig?.is_connected ? (
                    <>
                      <Button variant="outline" onClick={handleConnect} disabled={connecting}>
                        Reconnect
                      </Button>
                      <Button variant="destructive" onClick={handleDisconnect}>
                        Disconnect
                      </Button>
                    </>
                  ) : (
                    <Button onClick={handleConnect} disabled={connecting}>
                      {connecting ? "Connecting..." : "Connect Microsoft"}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button size="lg" className="gap-2" onClick={handleSave}>
              <Save className="h-4 w-4" /> Save Configuration
            </Button>
          </div>
        </div>

        {/* Preview card */}
        <div className="space-y-6">
          <Card className="border-border/60 bg-muted/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-primary" /> Live Persona Preview
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="p-4 border border-border/40 bg-background rounded-xl space-y-3">
                <p className="text-xs font-semibold text-primary uppercase tracking-wide">Dynamic Introduction Preview</p>
                <blockquote className="italic text-muted-foreground pl-3 border-l-2 border-primary/40 leading-relaxed">
                  "Hello, and welcome to your new journey! I am your <strong>{settings.aiName || "AI Officer"}</strong>. 
                  As the <strong>{settings.aiRole || "AI Induction Partner"}</strong>, I am here to help you get acquainted with 
                  our values and operations at <strong>{settings.companyName || "our organization"}</strong>."
                </blockquote>
              </div>
              <div className="space-y-1 text-xs">
                <p className="text-muted-foreground">
                  <strong>Current Tone:</strong> {settings.aiTone}
                </p>
                <p className="text-muted-foreground">
                  <strong>Current Style:</strong> {settings.aiStyle}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
