import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { 
  Bot, 
  Play, 
  Pause,
  Square, 
  Camera, 
  Users, 
  MessageSquare, 
  Volume2, 
  VolumeX, 
  Video, 
  Activity,
  UserCheck,
  ExternalLink,
  RefreshCw,
  LogOut
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/sessions-store";

export const Route = createFileRoute("/meeting-bot")({
  head: () => ({
    meta: [
      { title: "Teams Meeting Bot — AutoHR" },
      { name: "description", content: "Autonomous Teams bot lifecycle control dashboard." },
    ],
  }),
  component: MeetingBotDashboard,
});

interface BotStatus {
  state: string;
  meeting_url: string | null;
  health: {
    browser_alive: boolean;
    page_alive: boolean;
    meeting_active: boolean;
    bot_state: string;
    is_healthy: boolean;
  };
  audio_state: {
    playing: boolean;
    track: string | null;
  };
  last_screenshot_path: string | null;
}

function MeetingBotDashboard() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [meetingUrl, setMeetingUrl] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [displayName, setDisplayName] = useState("KONE AI HR Officer");
  const [participants, setParticipants] = useState<string[]>([]);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [pollingActive, setPollingActive] = useState(true);
  const [selectedAudioTrack, setSelectedAudioTrack] = useState("");
  const [audioPlayList, setAudioPlayList] = useState<string[]>([]);
  const [isSessionValidated, setIsSessionValidated] = useState(false);
  const [sessionSummary, setSessionSummary] = useState<any>(null);
  const [meetingStatus, setMeetingStatus] = useState<any>(null);
  const prevNarrationState = useRef("idle");

  const fetchBotStatus = async () => {
    try {
      const sId = sessionId.trim();
      const query = sId ? `?session_id=${encodeURIComponent(sId)}` : "";
      const data = await apiFetch(`/meeting-bot/status${query}`);
      setStatus(data);
      
      if (sId) {
        try {
          const metStatus = await apiFetch(`/runtime/${encodeURIComponent(sId)}/meeting-status`);
          setMeetingStatus(metStatus);
          
          const summary = await apiFetch(`/runtime/${sId}/summary`);
          setSessionSummary(summary);
          
          const currentNarrationState = metStatus?.narration_state;
          if (currentNarrationState && currentNarrationState !== prevNarrationState.current) {
            if (currentNarrationState === "speaking_greeting") {
              toast.info("KONE AI: Starting welcome greeting narration...");
            } else if (currentNarrationState === "finished_greeting") {
              toast.success("KONE AI: Completed welcome greeting narration.");
            } else if (currentNarrationState.startsWith("speaking_slide_")) {
              const num = currentNarrationState.split("_").pop();
              toast.info(`KONE AI: Starting narration for Slide ${num}...`);
            } else if (currentNarrationState.startsWith("finished_slide_")) {
              const num = currentNarrationState.split("_").pop();
              toast.success(`KONE AI: Completed narration for Slide ${num}!`);
            } else if (currentNarrationState === "speaking_closing") {
              toast.info("KONE AI: Starting closing farewell narration...");
            } else if (currentNarrationState === "finished_closing") {
              toast.success("KONE AI: Completed closing farewell narration!");
            }
            prevNarrationState.current = currentNarrationState;
          }
        } catch (err) {
          console.error("Failed to fetch meeting status:", err);
          setMeetingStatus(null);
        }
      } else {
        setMeetingStatus(null);
        setSessionSummary(null);
      }
      
      if (data.state === "CONNECTED" || data.health?.meeting_connected) {
        const parts = await apiFetch(`/meeting-bot/participants${query}`);
        setParticipants(parts.participants || []);
        
        const chat = await apiFetch(`/meeting-bot/chat${query}`);
        setChatMessages(chat.messages || []);
      }
    } catch (err) {
      console.error("Failed to fetch meeting bot status:", err);
    }
  };



  useEffect(() => {
    fetchBotStatus();
    let interval: any = null;
    if (pollingActive) {
      interval = setInterval(fetchBotStatus, 3000);
    }
    return () => clearInterval(interval);
  }, [pollingActive, sessionId]);

  const handleValidateSession = async () => {
    if (!sessionId.trim()) {
      toast.error("Session ID is required.");
      return;
    }
    setLoading(true);
    try {
      const summary = await apiFetch(`/runtime/${sessionId.trim()}/summary`);
      setSessionSummary(summary);
      
      if (summary.runtime_status === "READY" || summary.runtime_status === "BROWSER_READY" || summary.runtime_status === "CONNECTED") {
        setIsSessionValidated(true);
        setMeetingUrl(summary.meeting_url || "");
        toast.success("Session validation successful! Ready to join.");
        
        // Fetch audio list
        const audios = await apiFetch(`/runtime/${sessionId.trim()}/audio`);
        setAudioPlayList(audios);
        if (audios.length > 0) setSelectedAudioTrack(audios[0]);
      } else {
        toast.error(`Session is not ready. Current Status: ${summary.runtime_status}`);
        setIsSessionValidated(false);
      }
    } catch (err: any) {
      toast.error(`Validation failed: ${err.message || "Ensure session runtime is prepared."}`);
      setIsSessionValidated(false);
    } finally {
      setLoading(false);
    }
  };

  const handleJoinMeeting = async () => {
    if (!sessionId.trim() || !meetingUrl) {
      toast.error("Validated Session ID and Meeting URL are required.");
      return;
    }
    setLoading(true);
    try {
      // 1. Prepare runtime on backend if not done
      if (sessionSummary?.runtime_status === "NOT_CREATED") {
        await apiFetch(`/runtime/${sessionId.trim()}/prepare`, { method: "POST" });
      }
      
      // 2. Start induction browser
      await apiFetch(`/runtime/${sessionId.trim()}/start-induction`, { method: "POST" });

      // 3. Join the meeting, passing the custom meeting URL in payload
      await apiFetch(`/runtime/${sessionId.trim()}/join-meeting`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_url: meetingUrl })
      });
      
      toast.success("Bot joined meeting successfully.");
      fetchBotStatus();
    } catch (err: any) {
      toast.error(`Join failed: ${err.message || err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLeaveMeeting = async () => {
    setLoading(true);
    try {
      if (sessionId.trim()) {
        await apiFetch(`/runtime/${sessionId.trim()}/end`, { method: "POST" });
      } else {
        await apiFetch("/meeting-bot/leave", { method: "POST" });
      }
      toast.success("Bot left meeting and stopped runtime.");
      setStatus(null);
      setParticipants([]);
      setChatMessages([]);
    } catch (err: any) {
      toast.error(`Leave failed: ${err.message || err}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePlayAudio = async () => {
    if (!selectedAudioTrack || !sessionId.trim()) {
      toast.error("Please select a track and ensure Session ID is present.");
      return;
    }
    try {
      await apiFetch(`/runtime/${sessionId.trim()}/audio/play`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track: selectedAudioTrack })
      });
      toast.success("Audio playback started!");
      fetchBotStatus();
    } catch (err: any) {
      toast.error(`Play audio failed: ${err.message || err}`);
    }
  };

  const handleStopAudio = async () => {
    if (!sessionId.trim()) return;
    try {
      await apiFetch(`/runtime/${sessionId.trim()}/audio/stop`, { method: "POST" });
      toast.success("Audio playback stopped.");
      fetchBotStatus();
    } catch (err: any) {
      toast.error(`Stop audio failed: ${err.message || err}`);
    }
  };

  const handlePauseSession = async () => {
    if (!sessionId.trim()) return;
    setLoading(true);
    try {
      await apiFetch(`/runtime/${sessionId.trim()}/presentation/pause`, { method: "POST" });
      toast.success("Presentation and narration paused.");
      fetchBotStatus();
    } catch (err: any) {
      toast.error(`Pause failed: ${err.message || err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResumeSession = async () => {
    if (!sessionId.trim()) return;
    setLoading(true);
    try {
      await apiFetch(`/runtime/${sessionId.trim()}/presentation/resume`, { method: "POST" });
      toast.success("Presentation and narration resumed.");
      fetchBotStatus();
    } catch (err: any) {
      toast.error(`Resume failed: ${err.message || err}`);
    } finally {
      setLoading(false);
    }
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case "CONNECTED": return "bg-green-500 hover:bg-green-600 text-white";
      case "JOINING": return "bg-blue-500 hover:bg-blue-600 text-white";
      case "READY": return "bg-indigo-500 hover:bg-indigo-600 text-white";
      case "FAILED": return "bg-rose-500 hover:bg-rose-600 text-white";
      default: return "bg-zinc-500 hover:bg-zinc-600 text-white";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-border/40 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Teams Meeting Bot (MVP)</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Autonomous MS Teams integration capabilities container.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={`text-xs px-3 py-1 font-semibold ${getStateColor(status?.state || "STOPPED")}`}>
            {status?.state || "STOPPED"}
          </Badge>
        </div>
      </div>      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Control Panel */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="border-border/60">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Bot className="h-4 w-4 text-primary" /> Bot Control Panel
              </CardTitle>
              <CardDescription>Enter Session ID to initialize and join meeting</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Session ID (Mandatory)</label>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Enter prepared Session ID..."
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                    />
                    <Button onClick={handleValidateSession} disabled={loading} size="sm">
                      Validate
                    </Button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Teams Meeting Link</label>
                  <Input
                    placeholder="https://teams.microsoft.com/l/meetup-join/..."
                    value={meetingUrl}
                    onChange={(e) => setMeetingUrl(e.target.value)}
                    disabled={!isSessionValidated}
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Display Name</label>
                  <Input
                    placeholder="KONE AI HR Officer"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    disabled={!isSessionValidated}
                  />
                </div>
              </div>

              <div className="space-y-2 pt-2">
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    onClick={handleJoinMeeting}
                    disabled={loading || !isSessionValidated}
                    variant="outline"
                    className="text-green-600 hover:text-white border-green-600/30 hover:bg-green-600 gap-1.5"
                  >
                    <Video className="h-4 w-4" /> Join
                  </Button>
                  <Button
                    onClick={handleLeaveMeeting}
                    disabled={loading}
                    variant="outline"
                    className="text-rose-600 hover:text-white border-rose-600/30 hover:bg-rose-600 gap-1.5"
                  >
                    <LogOut className="h-4 w-4" /> Leave
                  </Button>
                </div>
                
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    onClick={handleResumeSession}
                    disabled={
                      loading || 
                      !sessionId.trim() || 
                      !meetingStatus?.presentation_detected || 
                      meetingStatus?.narration_state === "idle" ||
                      meetingStatus?.narration_state === "finished_closing" ||
                      sessionSummary?.runtime_status !== "PAUSED"
                    }
                    variant="outline"
                    className="text-emerald-600 hover:text-white border-emerald-600/30 hover:bg-emerald-600 gap-1.5"
                  >
                    <Play className="h-4 w-4" /> Resume
                  </Button>
                  <Button
                    onClick={handlePauseSession}
                    disabled={
                      loading || 
                      !sessionId.trim() || 
                      !meetingStatus?.presentation_detected || 
                      meetingStatus?.narration_state === "idle" ||
                      meetingStatus?.narration_state === "finished_closing" ||
                      sessionSummary?.runtime_status === "PAUSED"
                    }
                    variant="outline"
                    className="text-amber-600 hover:text-white border-amber-600/30 hover:bg-amber-600 gap-1.5"
                  >
                    <Pause className="h-4 w-4" /> Pause
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Meeting Readiness Panel */}
          {isSessionValidated && (
            <Card className="border-primary/40 bg-primary/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" /> Meeting Readiness
                </CardTitle>
                <CardDescription>HR authorization checkpoint before starting slide narration</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3.5 text-xs">
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Presentation Screen:</span>
                    <Badge variant={meetingStatus?.presentation_detected ? "default" : "secondary"}>
                      {meetingStatus?.presentation_detected ? "DETECTED" : "NOT DETECTED"}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Audio Resources:</span>
                    <Badge variant={meetingStatus?.audio_ready ? "default" : "secondary"}>
                      {meetingStatus?.audio_ready ? "LOADED" : "PENDING"}
                    </Badge>
                  </div>
                  {meetingStatus?.reason && meetingStatus.reason !== "Waiting for bot to connect to meeting" && (
                    <p className="text-[10px] text-amber-600 font-medium italic mt-1 text-center">
                      * {meetingStatus.reason}
                    </p>
                  )}
                </div>

                <Button
                  onClick={async () => {
                    try {
                      toast.info("Initializing and starting induction presentation...");
                      await apiFetch(`/runtime/${sessionId.trim()}/start-induction`, { method: "POST" });
                      toast.success("Presentation started successfully!");
                      fetchBotStatus();
                    } catch (e: any) {
                      toast.error(e.message || "Failed to start induction presentation.");
                    }
                  }}
                   disabled={
                    !meetingStatus?.presentation_detected || 
                    !meetingStatus?.audio_ready || 
                    status?.state === "PRESENTING" || 
                    (meetingStatus?.narration_state && meetingStatus?.narration_state !== "idle")
                  }
                  className="w-full bg-primary hover:bg-primary/95 text-primary-foreground font-bold gap-2 mt-1"
                >
                  <Play className="h-4.5 w-4.5" /> Start Induction
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Liveness health panel */}
          <Card className="border-border/60">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" /> Health & Liveness
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Browser process connected:</span>
                <Badge 
                  variant={status?.health?.browser_alive ? "default" : "secondary"}
                  className={status?.health?.browser_alive ? "bg-green-500 hover:bg-green-600 text-white" : ""}
                >
                  {status?.health?.browser_alive ? "ACTIVE" : "INACTIVE"}
                </Badge>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Teams Tab alive:</span>
                <Badge 
                  variant={status?.health?.page_alive ? "default" : "secondary"}
                  className={status?.health?.page_alive ? "bg-green-500 hover:bg-green-600 text-white" : ""}
                >
                  {status?.health?.page_alive ? "ACTIVE" : "INACTIVE"}
                </Badge>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Call session connected:</span>
                <Badge 
                  variant={status?.health?.meeting_connected ? "default" : "secondary"}
                  className={status?.health?.meeting_connected ? "bg-green-500 hover:bg-green-600 text-white" : ""}
                >
                  {status?.health?.meeting_connected ? "ACTIVE" : "INACTIVE"}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
