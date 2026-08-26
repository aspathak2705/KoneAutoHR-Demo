import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  Presentation,
  FileSpreadsheet,
  Check,
  Trash2,
  Pencil,
  Users,
  Clock,
  CalendarDays,
  PlayCircle,
  Sparkles,
  MessageCircleQuestion,
  ClipboardCheck,
  ChevronRight,
  HelpCircle,
  FileText,
  Video,
  CheckCircle,
  Volume2,
  Download,
  AlertTriangle,
  VolumeX,
  Mail,
  Copy,
} from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import {
  BACKEND_BASE,
  deleteSession,
  getInductionContent,
  getPreparationSteps,
  updateSession,
  useSession,
  syncFromBackend,
  getPresentationScript,
  updatePresentationScript,
  regeneratePresentationScript,
  getPresentationQuestions,
  updatePresentationQuestions,
  regeneratePresentationQuestions,
  getMeetingForSession,
  saveMeeting,
  generateInvitationDrafts,
  getInvitationDrafts,
  updateInvitationDraft,
  validateSessionReadiness,
  startMeetingRuntime,
  stopMeetingRuntime,
  advanceMeetingSlide,
  backtrackMeetingSlide,
  getMeetingRuntimeStatus,
  askQuestion,
  getConversationHistory,
  prepareMeetingRuntime,
  startInductionRuntime,
  joinPreparedMeeting,
  startRuntimeSpeech,
  stopRuntimeSpeech,
  getAttendanceReport,
  getTranscriptData,
  simulateReconnect,
  triggerScriptGeneration,
  triggerAudioGeneration,
  getSessionJobs,
  getRuntimeSummary,
  getRuntimeAudioList,
  playRuntimeAudioTrack,
  stopRuntimeAudioTrack,
  apiFetch,
  type MeetingDetails,
  type InvitationDraft,
  type ReadinessStatus,
  type RuntimeStatus,
  type PresentationScript,
  type PresentationQuestion,
  type InductionSession,
} from "@/lib/sessions-store";
import { cn } from "@/lib/utils";
import { SessionAccordion } from "@/components/review/SessionAccordion";

export const Route = createFileRoute("/sessions/$id")({
  head: () => ({
    meta: [
      { title: "Induction — AutoHR" },
      { name: "description", content: "Prepare and review an employee induction." },
    ],
  }),
  component: SessionDetailPage,
  notFoundComponent: SessionNotFound,
});

const DEPARTMENTS = [
  "Engineering",
  "Operations",
  "Sales",
  "Human Resources",
  "Finance",
  "Marketing",
  "Customer Support",
];

const getSessionScriptData = (scriptObj: any) => {
  if (!scriptObj) return null;
  const content = scriptObj.script_content;
  if (!content) return null;

  const opening = content.opening || {
    greeting: content.welcome_flow?.greeting || "Hello and welcome to today's onboarding session.",
    presenter_intro: content.welcome_flow?.intro || "I am your AI HR Trainer, here to guide you today.",
    employee_welcome: "A warm welcome to all our new joiners.",
    audio_check: "Before we begin, can everyone hear me clearly?",
    ice_breaker: "Please post your name and department in the chat window.",
    session_rules: content.welcome_flow?.rules || "Please stay muted during slides and use chat for questions.",
    agenda: "Today we will cover company values, safety policies, and key onboarding steps."
  };

  const slides = content.slides || Object.entries(content.slide_narrations || {}).map(([num, data]: [string, any]) => {
    const numVal = parseInt(num) || 1;
    return {
      slide_number: numVal,
      title: data.title || `Slide {numVal}`,
      objective: data.learning_objective || `Explain slide ${numVal} topics.`,
      transition_in: `Let's move onto slide ${numVal}.`,
      narration: data.narration || "",
      understanding_check: "Does anyone have any questions on this slide?",
      transition_out: `That completes slide ${numVal}.`,
      video_prompt: "",
      quiz_question: ""
    };
  });

  const closing = content.closing || {
    summary: content.closing_script?.summary || "That summarizes KONE's values, safety rules, and next steps.",
    next_steps: "Please complete your mandatory training portal items by the end of this week.",
    farewell: "Thank you all for your time! Welcome to the KONE family, and have a great day!"
  };

  return { opening, slides, closing };
};

function SessionDetailPage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const session = useSession(id);
  const [editOpen, setEditOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Meeting states
  const [meeting, setMeeting] = useState<MeetingDetails | null>(null);
  const [loadingMeeting, setLoadingMeeting] = useState(true);
  const [scheduling, setScheduling] = useState(false);
  const [drafts, setDrafts] = useState<InvitationDraft[]>([]);
  const [readiness, setReadiness] = useState<ReadinessStatus | null>(null);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<string[]>([]);

  // Form states
  const [formUrl, setFormUrl] = useState("");
  const [formPasscode, setFormPasscode] = useState("");
  const [formDate, setFormDate] = useState("");
  const [formTime, setFormTime] = useState("");
  const [formOrganizer, setFormOrganizer] = useState("");

  // Edit draft states
  const [editDraftId, setEditDraftId] = useState<string | null>(null);
  const [editDraftSubject, setEditDraftSubject] = useState("");
  const [editDraftBody, setEditDraftBody] = useState("");
  const [copiedDraftId, setCopiedDraftId] = useState<string | null>(null);

  const handleCopyDraft = (draft: any) => {
    // Convert HTML line breaks / tags into clean plain text lines
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = draft.body || "";
    const cleanBodyText = tempDiv.textContent || tempDiv.innerText || "";

    const textToCopy = `To: ${draft.recipient_name} <${draft.recipient_email}>\nSubject: ${draft.subject}\n\n${cleanBodyText.trim()}`;

    navigator.clipboard.writeText(textToCopy);
    setCopiedDraftId(draft.id);
    toast.success(`Copied email draft for ${draft.recipient_name}!`);

    setTimeout(() => {
      setCopiedDraftId(null);
    }, 2000);
  };

  useEffect(() => {
    if (session) {
      setFormDate(session.date || "");
      setFormOrganizer(session.trainer || "HR Trainer");
    }
  }, [session]);

  // Runtime states
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [slidesConfig, setSlidesConfig] = useState<any | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [newQuestionText, setNewQuestionText] = useState("");
  const [questionSpeaker, setQuestionSpeaker] = useState("");
  const [attendanceSummary, setAttendanceSummary] = useState<any | null>(null);
  const [audioPlayList, setAudioPlayList] = useState<string[]>([]);
  const [selectedAudioTrack, setSelectedAudioTrack] = useState<string>("");
  const prevNarrationState = useRef("idle");

  useEffect(() => {
    setLoadingMeeting(true);
    getMeetingForSession(id)
      .then((m) => {
        setMeeting(m);
        if (m) {
          setFormUrl(m.teams_meeting_url);
          setFormPasscode(m.meeting_passcode || "");
          setFormDate(m.meeting_date);
          setFormTime(m.meeting_time);
          setFormOrganizer(m.organizer_name);
        }
        
        // Load session assets and runtime status even if meeting configuration is missing
        getInvitationDrafts(id).then(setDrafts).catch(console.error);
        validateSessionReadiness(id).then(setReadiness).catch(console.error);
        getMeetingRuntimeStatus(id).then(setRuntimeStatus).catch(console.error);
        getConversationHistory(id).then(setMessages).catch(console.error);
        getAttendanceReport(id).then(setAttendanceSummary).catch(console.error);
        apiFetch(`/runtime/${id}/slide-controller`).then(setSlidesConfig).catch(console.error);
        getRuntimeAudioList(id).then((tracks) => {
          setAudioPlayList(tracks);
          if (tracks.length > 0) setSelectedAudioTrack(tracks[0]);
        }).catch(console.error);
      })
      .catch(console.error)
      .finally(() => setLoadingMeeting(false));
  }, [id]);

  useEffect(() => {
    if (!runtimeStatus) return;
    const isActive = ["READY", "BROWSER_READY", "INITIALIZING", "LAUNCHING", "JOINING", "WAITING", "CONNECTED", "DISCONNECTED", "RECONNECTING", "PRESENTING", "QUESTIONS", "FAILED", "PREPARING"].includes(runtimeStatus.state);
    if (!isActive) return;

     const interval = setInterval(() => {
      getMeetingRuntimeStatus(id)
        .then((status) => {
          setRuntimeStatus(status);
          getConversationHistory(id).then(setMessages);
          getAttendanceReport(id).then(setAttendanceSummary).catch(console.error);
          
          const currentNarrationState = status?.narration_state;
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

          if (status.state === "COMPLETED") {
            syncFromBackend(id);
          }
        })
        .catch(console.error);
    }, 3000);

    return () => clearInterval(interval);
  }, [id, runtimeStatus?.state]);

  // Pipeline progress & status states for all 6 steps
  const [valJobProgress, setValJobProgress] = useState<number | null>(null);
  const [valJobStatus, setValJobStatus] = useState<string | null>(null);
  const [parseJobProgress, setParseJobProgress] = useState<number | null>(null);
  const [parseJobStatus, setParseJobStatus] = useState<string | null>(null);
  const [scriptJobProgress, setScriptJobProgress] = useState<number | null>(null);
  const [scriptJobStatus, setScriptJobStatus] = useState<string | null>(null);
  const [audioJobProgress, setAudioJobProgress] = useState<number | null>(null);
  const [audioJobStatus, setAudioJobStatus] = useState<string | null>(null);
  const [packJobProgress, setPackJobProgress] = useState<number | null>(null);
  const [packJobStatus, setPackJobStatus] = useState<string | null>(null);
  const [verJobProgress, setVerJobProgress] = useState<number | null>(null);
  const [verJobStatus, setVerJobStatus] = useState<string | null>(null);
  const [generatingAudio, setGeneratingAudio] = useState(false);

  // Poll preparation jobs progress
  useEffect(() => {
    let interval: any = null;
    const pollJobs = () => {
      getSessionJobs(id).then((jobs) => {
        const valJob = jobs.find((j: any) => j.job_type === "VALIDATION");
        const parseJob = jobs.find((j: any) => j.job_type === "PARSING");
        const scriptJob = jobs.find((j: any) => j.job_type === "SCRIPT");
        const audioJob = jobs.find((j: any) => j.job_type === "AUDIO");
        const packJob = jobs.find((j: any) => j.job_type === "PACKAGE");
        const verJob = jobs.find((j: any) => j.job_type === "VERIFICATION");

        if (valJob) {
          setValJobProgress(Math.round(valJob.progress * 100));
          setValJobStatus(valJob.status);
        } else {
          setValJobProgress(null);
          setValJobStatus(null);
        }

        if (parseJob) {
          setParseJobProgress(Math.round(parseJob.progress * 100));
          setParseJobStatus(parseJob.status);
        } else {
          setParseJobProgress(null);
          setParseJobStatus(null);
        }

        if (scriptJob) {
          setScriptJobProgress(Math.round(scriptJob.progress * 100));
          setScriptJobStatus(scriptJob.status);
          if (scriptJob.status === "PROCESSING" || scriptJob.status === "PENDING") {
            setGeneratingScript(true);
          } else {
            setGeneratingScript(false);
          }
        } else {
          setScriptJobProgress(null);
          setScriptJobStatus(null);
        }

        if (audioJob) {
          setAudioJobProgress(Math.round(audioJob.progress * 100));
          setAudioJobStatus(audioJob.status);
          if (audioJob.status === "PROCESSING" || audioJob.status === "PENDING") {
            setGeneratingAudio(true);
          } else {
            setGeneratingAudio(false);
          }
        } else {
          setAudioJobProgress(null);
          setAudioJobStatus(null);
        }

        if (packJob) {
          setPackJobProgress(Math.round(packJob.progress * 100));
          setPackJobStatus(packJob.status);
        } else {
          setPackJobProgress(null);
          setPackJobStatus(null);
        }

        if (verJob) {
          setVerJobProgress(Math.round(verJob.progress * 100));
          setVerJobStatus(verJob.status);
        } else {
          setVerJobProgress(null);
          setVerJobStatus(null);
        }

        // Refresh session readiness
        validateSessionReadiness(id).then(setReadiness);
        syncFromBackend();
      }).catch(console.error);
    };

    pollJobs();
    interval = setInterval(pollJobs, 2500);
    return () => clearInterval(interval);
  }, [id]);

  // Script & Question edit states
  const [scriptRecord, setScriptRecord] = useState<PresentationScript | null>(null);
  const [sessionScript, setSessionScript] = useState<any>(null);
  const [questionsRecord, setQuestionsRecord] = useState<PresentationQuestion | null>(null);
  const [editWelcome, setEditWelcome] = useState("");
  const [editClosing, setEditClosing] = useState("");
  const [editNarrations, setEditNarrations] = useState<Record<string, string>>({});
  const [editFaqs, setEditFaqs] = useState<Array<{ question: string; answer: string }>>([]);

  const [savingScript, setSavingScript] = useState(false);
  const [savingQuestions, setSavingQuestions] = useState(false);
  const [generatingScript, setGeneratingScript] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);

  // Reassurance visual states
  const [showScriptEditor, setShowScriptEditor] = useState(false);
  const [showQuestionsEditor, setShowQuestionsEditor] = useState(false);

  // Edit session form state
  const [editForm, setEditForm] = useState({
    title: "",
    department: "",
    trainer: "",
    date: "",
    description: "",
  });

  // Fetch script and questions from backend
  useEffect(() => {
    setShowScriptEditor(false);
    setShowQuestionsEditor(false);

    if (session?.presentation_id) {
      getPresentationScript(session.presentation_id).then((s) => {
        setScriptRecord(s);
        if (s?.script_content) {
          setEditWelcome(s.script_content.welcome_flow?.greeting || "");
          setEditClosing(s.script_content.closing_script?.summary || "");
          const narrs: Record<string, string> = {};
          Object.entries(s.script_content.slide_narrations || {}).forEach(([num, data]: [string, any]) => {
            narrs[num] = data.narration || "";
          });
          setEditNarrations(narrs);
          setSessionScript(getSessionScriptData(s));
        }
      }).catch(console.error);

      getPresentationQuestions(session.presentation_id).then((q) => {
        setQuestionsRecord(q);
        if (q?.questions_content) {
          setEditFaqs(q.questions_content.map(f => ({ question: f.question, answer: f.answer })));
        }
      }).catch(console.error);
    }
  }, [session?.presentation_id]);

  useEffect(() => {
    if (session) {
      setEditForm({
        title: session.title,
        department: session.department,
        trainer: session.trainer,
        date: session.date,
        description: session.description || "",
      });
    }
  }, [session]);

  if (!session) return <SessionNotFound />;

  const content = getInductionContent(session);
  const prep = getPreparationSteps(session);
  const bothUploaded = !!session.presentationFile && !!session.employeesFile;

  // Auto-populate selected IDs on first load
  useEffect(() => {
    if (content?.employees && content.employees.length > 0 && selectedEmployeeIds.length === 0) {
      setSelectedEmployeeIds(
        content.employees.filter(e => !!e.email).map(e => e.id || "")
      );
    }
  }, [content?.employees, selectedEmployeeIds.length]);

  const readyToStart = session.status === "READY" || session.status === "COMPLETED";

  const handleOpeningChange = (field: any, value: string) => {
    setSessionScript((prev: any) => {
      if (!prev) return prev;
      return {
        ...prev,
        opening: { ...prev.opening, [field]: value }
      };
    });
  };

  const handleSlideChange = (index: number, field: any, value: any) => {
    setSessionScript((prev: any) => {
      if (!prev) return prev;
      const nextSlides = [...prev.slides];
      nextSlides[index] = { ...nextSlides[index], [field]: value };
      return { ...prev, slides: nextSlides };
    });
  };

  const handleClosingChange = (field: any, value: string) => {
    setSessionScript((prev: any) => {
      if (!prev) return prev;
      return {
        ...prev,
        closing: { ...prev.closing, [field]: value }
      };
    });
  };

  const handleSaveScript = async () => {
    if (!scriptRecord || !sessionScript) return;
    setSavingScript(true);
    try {
      await updatePresentationScript(scriptRecord.id, sessionScript);
      toast.success("Presentation script saved!");
      await syncFromBackend();
    } catch {
      toast.error("Failed to save script");
    } finally {
      setSavingScript(false);
    }
  };

  const handleSaveQuestions = async () => {
    if (!questionsRecord) return;
    setSavingQuestions(true);
    try {
      await updatePresentationQuestions(questionsRecord.id, editFaqs);
      toast.success("Employee questions saved!");
      await syncFromBackend();
    } catch {
      toast.error("Failed to save questions");
    } finally {
      setSavingQuestions(false);
    }
  };

  const handleGenerateScript = async () => {
    if (!session.presentation_id || !session.employee_list_id) return;
    setGeneratingScript(true);
    try {
      await triggerScriptGeneration(session.id);
      toast.success("AI script generation pipeline queued!");
    } catch {
      toast.error("Failed to start script pipeline");
      setGeneratingScript(false);
    }
  };

  const handleGenerateAudio = async () => {
    if (!session.presentation_id) return;
    setGeneratingAudio(true);
    try {
      await triggerAudioGeneration(session.id);
      toast.success("Speech audio generation pipeline queued!");
    } catch {
      toast.error("Failed to start audio pipeline");
      setGeneratingAudio(false);
    }
  };

  const handleGenerateQuestions = async () => {
    if (!session.presentation_id || !session.employee_list_id) return;
    setGeneratingQuestions(true);
    try {
      const q = await regeneratePresentationQuestions(session.presentation_id, session.employee_list_id);
      setQuestionsRecord(q);
      setEditFaqs(q.questions_content.map(f => ({ question: f.question, answer: f.answer })));
      toast.success("Expected employee questions generated!");
      setShowQuestionsEditor(true);
    } catch {
      toast.error("Failed to generate questions");
    } finally {
      setGeneratingQuestions(false);
    }
  };

  const handleSaveSession = async () => {
    try {
      await updateSession(session.id, editForm);
      setEditOpen(false);
      toast.success("Session details updated");
    } catch (err) {
      toast.error("Failed to update session");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteSession(session.id);
      toast.success("Session deleted");
      navigate({ to: "/sessions" });
    } catch (err) {
      toast.error("Failed to delete session");
    }
  };

  const handlePrepareMeetingManual = async (meetingUrl: string, passcode: string, date: string, time: string, organizer: string) => {
    if (!session) return;
    setScheduling(true);
    try {
      const m = await saveMeeting({
        session_id: session.id,
        teams_meeting_url: meetingUrl,
        meeting_passcode: passcode || null,
        organizer_name: organizer,
        meeting_date: date,
        meeting_time: time
      });
      setMeeting(m);
      toast.success("Teams meeting details saved successfully!");
      const r = await validateSessionReadiness(session.id);
      setReadiness(r);
      const d = await getInvitationDrafts(session.id);
      setDrafts(d);
    } catch (err: any) {
      toast.error(err.message || "Failed to save meeting details");
    } finally {
      setScheduling(false);
    }
  };

  const handleGenerateDrafts = async () => {
    if (!session) return;
    setLoadingDrafts(true);
    try {
      const idsToSend = selectedEmployeeIds.length > 0 ? selectedEmployeeIds : undefined;
      const d = await generateInvitationDrafts(session.id, idsToSend);
      setDrafts(d);
      toast.success("Common induction invitation draft generated!");
      const r = await validateSessionReadiness(session.id);
      setReadiness(r);
    } catch (err: any) {
      toast.error(err.message || "Failed to generate drafts");
    } finally {
      setLoadingDrafts(false);
    }
  };

  const handleUpdateDraft = async (draftId: string, subject: string, body: string) => {
    try {
      const updated = await updateInvitationDraft(draftId, subject, body);
      setDrafts(drafts.map(d => d.id === draftId ? updated : d));
      toast.success("Email invitation draft updated!");
    } catch (err: any) {
      toast.error(err.message || "Failed to update email draft");
    }
  };

  const handleStartRuntime = async () => {
    if (!session) return;
    try {
      await startMeetingRuntime(session.id);
      toast.success("AI meeting orchestration launched!");
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to start AI presentation session");
    }
  };

  const handleStopRuntime = async () => {
    if (!session) return;
    try {
      await stopMeetingRuntime(session.id);
      toast.success("AI presentation session stopped.");
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to stop presentation session");
    }
  };

  const handleNextSlide = async () => {
    if (!session) return;
    try {
      await advanceMeetingSlide(session.id);
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to advance slide");
    }
  };

  const handlePrevSlide = async () => {
    if (!session) return;
    try {
      await backtrackMeetingSlide(session.id);
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to go back a slide");
    }
  };
  const handleAskQuestion = async () => {
    if (!session || !newQuestionText.trim()) return;
    try {
      await askQuestion(session.id, questionSpeaker.trim() || "Attendee", newQuestionText.trim());
      const history = await getConversationHistory(session.id);
      setMessages(history);
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
      setNewQuestionText("");
    } catch (err: any) {
      toast.error(err.message || "Failed to submit question");
    }
  };

  const handlePrepareRuntime = async () => {
    if (!session) return;
    
    // Optimistically transition layout to PREPARING state instantly
    setRuntimeStatus(prev => ({
      session_id: session.id,
      state: "PREPARING",
      current_slide: prev?.current_slide || 0,
      presentation_ready: true,
      employees_ready: true,
      meeting_ready: true,
      ai_ready: true
    }));

    try {
      await prepareMeetingRuntime(session.id);
      toast.success("AutoHR runtime prepared.");
      
      // Force frontend store synchronization to fetch new session/job states
      await syncFromBackend();
      
      // Delay status polling slightly to let backend commit DB updates cleanly
      await new Promise((resolve) => setTimeout(resolve, 500));
      
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      // Revert/refresh status on failure
      const status = await getMeetingRuntimeStatus(session.id).catch(() => null);
      setRuntimeStatus(status);
      toast.error(err.message || "Failed to prepare runtime");
    }
  };

  const handleStartInduction = async () => {
    if (!session) return;
    try {
      toast.info("Initializing and starting induction presentation...");
      await startInductionRuntime(session.id);
      toast.success("Induction started, browser ready.");
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to start induction");
    }
  };

  const handleJoinPrepared = async () => {
    if (!session) return;
    try {
      await joinPreparedMeeting(session.id);
      toast.success("Joining meeting...");
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to join meeting");
    }
  };

  const handleStartSpeaking = async (narrationText: string) => {
    if (!session) return;
    try {
      await startRuntimeSpeech(session.id, narrationText);
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to start speech stream");
    }
  };

  const handleStopSpeaking = async () => {
    if (!session) return;
    try {
      await stopRuntimeSpeech(session.id);
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to interrupt speech stream");
    }
  };

  const handleTriggerReconnect = async () => {
    if (!session) return;
    try {
      await simulateReconnect(session.id);
      toast.warning("Simulating drop. Checking recovery...");
      const status = await getMeetingRuntimeStatus(session.id);
      setRuntimeStatus(status);
    } catch (err: any) {
      toast.error(err.message || "Failed to trigger reconnection simulation");
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="space-y-1">
          <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground">
            <Link to="/sessions">
              <ArrowLeft className="h-4 w-4 mr-1" /> Back to sessions
            </Link>
          </Button>
          <h1 className="text-3xl font-semibold tracking-tight">{session.title}</h1>
          <p className="text-sm text-muted-foreground">
            Created on {new Date(session.createdAt).toLocaleDateString()}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4 mr-1" /> Edit details
          </Button>
          <Button variant="outline" size="sm" className="text-destructive hover:bg-destructive/5" onClick={() => setConfirmDelete(true)}>
            <Trash2 className="h-4 w-4 mr-1" /> Delete
          </Button>
        </div>
      </div>

      {/* Main Grid layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Content & Editors */}
        <div className="lg:col-span-2 space-y-6">

          {/* Linked Presentation Summary card */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Presentation className="h-4.5 w-4.5 text-primary" /> Presentation
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-muted/20 p-4 rounded-xl border border-border/40">
                  <div className="space-y-1">
                    <h3 className="font-semibold text-sm">{session.presentation?.name || "General Presentation"}</h3>
                    <p className="text-xs text-muted-foreground truncate max-w-md">{session.presentation?.original_filename || session.presentationFile}</p>
                  </div>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      <span>{content.estimatedMinutes} minutes</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Users className="h-3.5 w-3.5" />
                      <span>{content.employees.length} Attendees</span>
                    </div>
                  </div>
                </div>

                {content.employees.length > 0 && (
                  <div className="space-y-3 pt-2">
                    <div className="flex justify-between items-center pb-2 border-b border-border/40">
                      <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Select Induction Recipients</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (selectedEmployeeIds.length === content.employees.length) {
                            setSelectedEmployeeIds([]);
                          } else {
                            setSelectedEmployeeIds(content.employees.map(e => e.id || ""));
                          }
                        }}
                        className="text-xs font-semibold h-7 text-primary hover:bg-primary/5"
                      >
                        {selectedEmployeeIds.length === content.employees.length ? "Deselect All" : "Select All"}
                      </Button>
                    </div>

                    <div className="max-h-[220px] overflow-y-auto space-y-2 pr-1">
                      {content.employees.map((emp) => {
                        const hasEmail = !!emp.email;
                        const isChecked = selectedEmployeeIds.includes(emp.id || "");
                        return (
                          <div
                            key={emp.id}
                            className={cn(
                              "flex items-center justify-between p-2.5 rounded-lg border transition-all text-xs",
                              isChecked
                                ? "bg-primary/5 border-primary/40 text-foreground"
                                : "bg-card border-border/60 text-muted-foreground",
                              !hasEmail && "opacity-60 cursor-not-allowed"
                            )}
                          >
                            <div className="flex items-center gap-2.5">
                              <input
                                type="checkbox"
                                checked={isChecked && hasEmail}
                                disabled={!hasEmail}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedEmployeeIds(prev => [...prev, emp.id || ""]);
                                  } else {
                                    setSelectedEmployeeIds(prev => prev.filter(id => id !== emp.id));
                                  }
                                }}
                                className="rounded border-input text-primary focus:ring-primary h-3.5 w-3.5"
                              />
                              <div>
                                <p className="font-semibold">{emp.name}</p>
                                <p className="text-[10px] text-muted-foreground">{emp.role} • {emp.department}</p>
                              </div>
                            </div>
                            <span className="font-mono text-[10px] pr-2">
                              {emp.email || "Missing Email address"}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    {content.employees.some(e => !e.email) && (
                      <div className="p-3 bg-amber-50/20 border border-amber-500/30 text-amber-700 rounded-lg text-xs leading-relaxed flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                        <div>
                          <strong>Warning:</strong> {content.employees.filter(e => !e.email).length} employee(s) cannot be included because their email address is missing.
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* AI Presentation Narration Editor */}
          {session.creation_mode === "AI" && (
            <SectionShell title="AI Presentation" icon={FileText}>
            {scriptRecord ? (
              <Card className="border-border/60">
                <CardContent className="p-5 space-y-4">
                  {scriptRecord && !showScriptEditor ? (
                    <div className="p-6 border border-green-100 bg-green-50/10 rounded-xl space-y-4 text-center">
                      <CheckCircle className="h-8 w-8 text-green-600 mx-auto" />
                      <div>
                        <h3 className="font-bold text-base text-foreground">Presentation Script Ready</h3>
                        <p className="text-xs text-muted-foreground mt-1">
                          An AI presentation script is already generated and verified for this presentation.
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-1">
                          Last Updated: {new Date(scriptRecord.generated_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                        </p>
                      </div>
                      <Button onClick={() => setShowScriptEditor(true)} variant="outline" size="sm">
                        View / Edit Content
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="max-h-[450px] overflow-y-auto pr-2 space-y-4">
                        {sessionScript && (
                          <SessionAccordion
                            sessionScript={sessionScript}
                            onOpeningChange={handleOpeningChange}
                            onSlideChange={handleSlideChange}
                            onClosingChange={handleClosingChange}
                          />
                        )}
                      </div>
                      <div className="flex justify-end pt-2 border-t border-border/40">
                        <Button onClick={handleSaveScript} disabled={savingScript}>
                          {savingScript ? "Saving..." : "Save Script"}
                        </Button>
                      </div>
                    </>
                  )}

                  {/* Advanced settings collapsible */}
                  <div className="mt-4 border-t border-border pt-4">
                    <details className="group">
                      <summary className="text-xs font-semibold text-muted-foreground hover:text-foreground cursor-pointer flex items-center gap-1.5 select-none">
                        <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
                        Advanced Settings
                      </summary>
                      <div className="mt-3 pl-5 space-y-4">
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground">
                            Regenerate the script from scratch using AI. This will overwrite any custom edits you have saved.
                          </p>
                          <div className="flex items-center gap-3">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleGenerateScript}
                              disabled={generatingScript}
                              className="text-amber-600 hover:text-white border-amber-600/30 hover:bg-amber-600 gap-1.5 shrink-0"
                            >
                              <Sparkles className="h-4 w-4" /> {generatingScript ? "Generating..." : "Generate New Script"}
                            </Button>
                            {scriptJobProgress !== null && (
                              <div className="flex-1 flex items-center gap-2">
                                <Progress value={scriptJobProgress} className="h-2 flex-1" />
                                <span className="text-[10px] font-mono text-muted-foreground">{scriptJobProgress}%</span>
                              </div>
                            )}
                          </div>

                          {(valJobStatus || parseJobStatus || scriptJobStatus) && (
                            <div className="mt-2 text-xs space-y-1.5 bg-muted/40 p-2.5 rounded-lg border border-border/40">
                              <p className="font-bold text-[10px] uppercase text-muted-foreground">Generation Pipelines</p>
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-muted-foreground">1. Input Validation:</span>
                                <span className="font-semibold">{valJobStatus || "PENDING"} {valJobProgress !== null ? `(${valJobProgress}%)` : ""}</span>
                              </div>
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-muted-foreground">2. Slide Deck & Sheet Parsing:</span>
                                <span className="font-semibold">{parseJobStatus || "PENDING"} {parseJobProgress !== null ? `(${parseJobProgress}%)` : ""}</span>
                              </div>
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-muted-foreground">3. AI Script Synthesis:</span>
                                <span className="font-semibold">{scriptJobStatus || "PENDING"} {scriptJobProgress !== null ? `(${scriptJobProgress}%)` : ""}</span>
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="space-y-2 border-t border-border/40 pt-3">
                          <p className="text-xs text-muted-foreground">
                            Pre-compile speech voice tracks (MP3) for welcome greetings and slide narrations.
                          </p>
                          <div className="flex items-center gap-3">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleGenerateAudio}
                              disabled={generatingAudio || !scriptRecord}
                              className="text-blue-600 hover:text-white border-blue-600/30 hover:bg-blue-600 gap-1.5 shrink-0"
                            >
                              <Volume2 className="h-4 w-4" /> {generatingAudio ? "Synthesizing..." : "Generate TTS Audio"}
                            </Button>
                            {audioJobProgress !== null && (
                              <div className="flex-1 flex items-center gap-2">
                                <Progress value={audioJobProgress} className="h-2 flex-1" />
                                <span className="text-[10px] font-mono text-muted-foreground">{audioJobProgress}%</span>
                              </div>
                            )}
                          </div>

                          {(audioJobStatus || packJobStatus || verJobStatus) && (
                            <div className="mt-2 text-xs space-y-1.5 bg-muted/40 p-2.5 rounded-lg border border-border/40">
                              <p className="font-bold text-[10px] uppercase text-muted-foreground">Deployment Pipelines</p>
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-muted-foreground">1. TTS Speech Audio Generation:</span>
                                <span className="font-semibold">{audioJobStatus || "PENDING"} {audioJobProgress !== null ? `(${audioJobProgress}%)` : ""}</span>
                              </div>
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-muted-foreground">2. Verification Checks:</span>
                                <span className="font-semibold">{verJobStatus || "PENDING"} {verJobProgress !== null ? `(${verJobProgress}%)` : ""}</span>
                              </div>
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-muted-foreground">3. Deployment Packaging:</span>
                                <span className="font-semibold">{packJobStatus || "PENDING"} {packJobProgress !== null ? `(${packJobProgress}%)` : ""}</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </details>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="border-border/60">
                <CardContent className="p-6 text-center space-y-4">
                  <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground">AI Script Generation Required</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      No script has been generated for this presentation yet. Please build the script to begin.
                    </p>
                  </div>

                  <div className="max-w-md mx-auto space-y-3">
                    <div className="flex items-center justify-center gap-3">
                      <Button
                        onClick={handleGenerateScript}
                        disabled={generatingScript}
                        className="bg-amber-600 hover:bg-amber-700 text-white gap-1.5 font-semibold"
                      >
                        <Sparkles className="h-4 w-4" /> {generatingScript ? "Queuing Pipeline..." : "Generate AI Script"}
                      </Button>
                    </div>
                    {(valJobStatus || parseJobStatus || scriptJobStatus) && (
                      <div className="space-y-2 mt-2 text-left bg-muted/40 p-3 rounded-lg border border-border/40">
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="text-muted-foreground">1. Input Validation:</span>
                          <span className="font-semibold">{valJobStatus || "PENDING"} {valJobProgress !== null ? `(${valJobProgress}%)` : ""}</span>
                        </div>
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="text-muted-foreground">2. Slide Deck & Sheet Parsing:</span>
                          <span className="font-semibold">{parseJobStatus || "PENDING"} {parseJobProgress !== null ? `(${parseJobProgress}%)` : ""}</span>
                        </div>
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="text-muted-foreground">3. AI Script Synthesis:</span>
                          <span className="font-semibold">{scriptJobStatus || "PENDING"} {scriptJobProgress !== null ? `(${scriptJobProgress}%)` : ""}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </SectionShell>
          )}

          {/* Expected Employee Questions Editor */}
          <SectionShell title="Expected Employee Questions" icon={MessageCircleQuestion}>
            {questionsRecord ? (
              <Card className="border-border/60">
                <CardContent className="p-5 space-y-4">
                  {questionsRecord && !showQuestionsEditor ? (
                    <div className="p-6 border border-green-100 bg-green-50/10 rounded-xl space-y-4 text-center">
                      <CheckCircle className="h-8 w-8 text-green-600 mx-auto" />
                      <div>
                        <h3 className="font-bold text-base text-foreground">Employee Questions Ready</h3>
                        <p className="text-xs text-muted-foreground mt-1">
                          Expected employee FAQs are prepared for this training deck.
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-1">
                          Last Updated: {new Date(questionsRecord.generated_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                        </p>
                      </div>
                      <Button onClick={() => setShowQuestionsEditor(true)} variant="outline" size="sm">
                        View / Edit Content
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="max-h-[400px] overflow-y-auto pr-2 space-y-4">
                        {editFaqs.map((faq, idx) => (
                          <div key={idx} className="space-y-3 p-4 border border-border/60 rounded-xl bg-card">
                            <div className="space-y-1">
                              <Label className="text-xs text-muted-foreground uppercase">Question {idx + 1}</Label>
                              <Input
                                value={faq.question}
                                onChange={(e) => {
                                  const next = [...editFaqs];
                                  next[idx].question = e.target.value;
                                  setEditFaqs(next);
                                }}
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs text-muted-foreground uppercase">Answer</Label>
                              <Textarea
                                value={faq.answer}
                                onChange={(e) => {
                                  const next = [...editFaqs];
                                  next[idx].answer = e.target.value;
                                  setEditFaqs(next);
                                }}
                                rows={2}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="flex justify-end pt-2 border-t border-border/40">
                        <Button onClick={handleSaveQuestions} disabled={savingQuestions}>
                          {savingQuestions ? "Saving..." : "Save Questions"}
                        </Button>
                      </div>
                    </>
                  )}

                  {/* More options collapsible */}
                  <div className="mt-4 border-t border-border pt-4">
                    <details className="group">
                      <summary className="text-xs font-semibold text-muted-foreground hover:text-foreground cursor-pointer flex items-center gap-1.5 select-none">
                        <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
                        More Options
                      </summary>
                      <div className="mt-3 pl-5 space-y-3">
                        <p className="text-xs text-muted-foreground">
                          Extract default FAQs again using AI. This will overwrite any custom edits.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleGenerateQuestions}
                          disabled={generatingQuestions}
                          className="text-amber-600 hover:text-white border-amber-600/30 hover:bg-amber-600 gap-1.5"
                        >
                          <Sparkles className="h-4 w-4" /> Generate New Questions
                        </Button>
                      </div>
                    </details>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <p className="text-sm text-muted-foreground italic px-2">No questions generated yet.</p>
            )}
          </SectionShell>

          {/* Personalized Invitation Email Drafts Section */}
          <SectionShell title="Personalized Email Drafts" icon={Mail}>
            <Card className="border-border/60">
              <CardContent className="p-5 space-y-4">
                {drafts.length === 0 ? (
                  <div className="p-6 border border-border/40 bg-muted/10 rounded-xl space-y-4 text-center">
                    <Mail className="h-8 w-8 text-primary mx-auto" />
                    <div>
                      <h3 className="font-bold text-base text-foreground">No Invitation Drafts Generated Yet</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        Personalized invitation email drafts can be generated for your attendees using the KONE company persona.
                      </p>
                    </div>
                    <Button
                      onClick={handleGenerateDrafts}
                      disabled={loadingDrafts}
                      className="bg-primary hover:bg-primary/95 text-primary-foreground text-xs h-9 px-4 gap-2 font-semibold"
                    >
                      <Sparkles className="h-4 w-4" />
                      {loadingDrafts ? "Generating Drafts..." : "Generate Invitation Drafts"}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center pb-2 border-b border-border/40">
                      <div>
                        <h4 className="font-bold text-sm text-foreground">Common Invitation Draft</h4>
                        <p className="text-xs text-muted-foreground">
                          Review or modify the common induction invitation draft.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleGenerateDrafts}
                        disabled={loadingDrafts}
                        className="text-xs gap-1.5"
                      >
                        <Sparkles className="h-3.5 w-3.5 text-primary" /> Regenerate Draft
                      </Button>
                    </div>

                    {drafts.map((draft) => {
                      // Count recipients
                      let recipientsList: string[] = [];
                      try {
                        recipientsList = draft.recipients ? JSON.parse(draft.recipients) : (draft.recipient_email ? draft.recipient_email.split(",").map(e => e.trim()) : []);
                      } catch {
                        recipientsList = draft.recipient_email ? draft.recipient_email.split(",").map(e => e.trim()) : [];
                      }

                      return (
                        <div key={draft.id} className="border border-border/60 rounded-xl p-5 bg-card space-y-4">
                          <div className="space-y-1.5 pb-2 border-b border-border/40 text-xs">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-muted-foreground uppercase text-[10px]">Recipients</span>
                              <span className={cn(
                                "text-[10px] px-2 py-0.5 rounded-full font-semibold border",
                                draft.status === "EDITED"
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : "bg-muted text-muted-foreground border-border"
                              )}>
                                {draft.status === "EDITED" ? "Modified" : "Draft"}
                              </span>
                            </div>
                            <p className="font-medium text-foreground">{recipientsList.length} employee(s) selected</p>
                            <p className="text-[10px] text-muted-foreground break-all max-h-[50px] overflow-y-auto bg-muted/20 p-1.5 rounded-md">
                              {recipientsList.join(", ")}
                            </p>
                          </div>

                          {editDraftId === draft.id ? (
                            <div className="space-y-3 pt-1">
                              <div className="space-y-1">
                                <Label className="text-xs font-semibold">Subject Line</Label>
                                <Input
                                  value={editDraftSubject}
                                  onChange={(e) => setEditDraftSubject(e.target.value)}
                                  className="h-8 text-xs"
                                />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-xs font-semibold">Email Body</Label>
                                <Textarea
                                  value={editDraftBody}
                                  onChange={(e) => setEditDraftBody(e.target.value)}
                                  rows={8}
                                  className="text-xs"
                                />
                              </div>
                              <div className="flex justify-end gap-2 pt-1">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setEditDraftId(null)}
                                  className="h-8 text-xs"
                                >
                                  Cancel
                                </Button>
                                <Button
                                  size="sm"
                                  onClick={() => {
                                    handleUpdateDraft(draft.id, editDraftSubject, editDraftBody);
                                    setEditDraftId(null);
                                  }}
                                  className="h-8 text-xs bg-primary text-primary-foreground"
                                >
                                  Save Draft
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <div className="space-y-3 pt-1">
                              <div>
                                <Label className="text-xs font-bold text-muted-foreground uppercase text-[10px]">Subject</Label>
                                <p className="font-semibold text-xs text-foreground mt-0.5">{draft.subject}</p>
                              </div>
                              <div>
                                <Label className="text-xs font-bold text-muted-foreground uppercase text-[10px]">Message</Label>
                                <div
                                  className="text-muted-foreground text-xs bg-muted/20 p-3 rounded-lg max-h-[220px] overflow-y-auto leading-relaxed border border-border/40 mt-1"
                                  dangerouslySetInnerHTML={{ __html: draft.body }}
                                />
                              </div>

                              <div className="flex flex-col sm:flex-row gap-2 pt-2">
                                <Button
                                  onClick={() => {
                                    // Open in Outlook trigger link mailto format
                                    const tempDiv = document.createElement("div");
                                    tempDiv.innerHTML = draft.body || "";
                                    const plainBody = tempDiv.textContent || tempDiv.innerText || "";
                                    const bccList = recipientsList.join(";");
                                    const mailtoUrl = `mailto:?bcc=${encodeURIComponent(bccList)}&subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(plainBody)}`;
                                    window.open(mailtoUrl, "_blank");
                                    toast.success("Outlook invitation draft prepared!");
                                  }}
                                  className="flex-1 bg-primary hover:bg-primary/95 text-primary-foreground text-xs h-9 gap-1.5 font-semibold"
                                >
                                  <Mail className="h-4 w-4" /> Open in Outlook
                                </Button>
                                <div className="flex gap-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleCopyDraft(draft)}
                                    className={cn(
                                      "h-9 text-xs font-semibold gap-1.5 transition-colors",
                                      copiedDraftId === draft.id
                                        ? "bg-green-50 text-green-700 border-green-300"
                                        : "hover:bg-accent text-foreground"
                                    )}
                                  >
                                    {copiedDraftId === draft.id ? (
                                      <>
                                        <Check className="h-3.5 w-3.5 text-green-600" /> Copied!
                                      </>
                                    ) : (
                                      <>
                                        <Copy className="h-3.5 w-3.5 text-primary" /> Copy Draft
                                      </>
                                    )}
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      setEditDraftId(draft.id);
                                      setEditDraftSubject(draft.subject);
                                      setEditDraftBody(draft.body);
                                    }}
                                    className="h-9 text-xs font-semibold gap-1.5"
                                  >
                                    <Pencil className="h-3.5 w-3.5 text-muted-foreground" /> Edit Draft
                                  </Button>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </SectionShell>

          {/* AI Meeting Control Console Card */}
          <Card className="border-primary/35 bg-primary/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold flex items-center gap-2 text-foreground">
                <PlayCircle className="h-5 w-5 text-primary" /> AI Meeting Control Console
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {(!runtimeStatus || 
                runtimeStatus.state === "NOT_CREATED" || 
                runtimeStatus.state === "IDLE" || 
                runtimeStatus.state === "STOPPED" || 
                runtimeStatus.state === "FINISHED") && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    All components are verified. Prepare the AutoHR meeting engine now.
                  </p>
                  <Button
                    onClick={handlePrepareRuntime}
                    disabled={!readiness?.is_ready}
                    className="w-full bg-primary hover:bg-primary/95 text-primary-foreground gap-2 font-semibold"
                  >
                    <PlayCircle className="h-4.5 w-4.5" /> Prepare Runtime
                  </Button>
                  {!readiness?.is_ready && (
                    <p className="text-[10px] text-amber-600 text-center font-medium">
                      * Please complete all runtime readiness checklist items first.
                    </p>
                  )}
                </div>
              )}
              {runtimeStatus?.state === "FAILED" && (
                <div className="space-y-3 p-4 border border-red-200 bg-red-50/20 rounded-xl">
                  <div className="flex items-center gap-2 text-red-700">
                    <AlertTriangle className="h-5 w-5" />
                    <h4 className="font-semibold text-xs">Runtime startup failed</h4>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed break-words">
                    {runtimeStatus.last_error || "Browser runtime failed to initialize. Check backend logs for diagnostics."}
                  </p>
                  <Button
                    onClick={handlePrepareRuntime}
                    disabled={!readiness?.is_ready}
                    className="w-full bg-primary hover:bg-primary/95 text-primary-foreground gap-2 font-semibold"
                  >
                    <PlayCircle className="h-4.5 w-4.5" /> Retry Prepare
                  </Button>
                </div>
              )}

              {runtimeStatus?.state === "PREPARING" && (
                <div className="flex flex-col items-center justify-center p-6 space-y-3 text-center bg-muted/10 border border-border/40 rounded-xl">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                  <div>
                    <h4 className="font-semibold text-foreground">Preparing Runtime...</h4>
                  </div>
                </div>
              )}
              {runtimeStatus?.state === "READY" && (
                <div className="space-y-4 p-4 border border-green-200 bg-green-50/20 rounded-xl">
                  <div className="flex items-center justify-between pb-2 border-b border-border/40">
                    <h4 className="font-bold text-xs text-green-800">Runtime Ready</h4>
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold bg-green-100 text-green-700">
                      READY
                    </span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex flex-col gap-1">
                      <Label className="text-[10px] font-bold text-muted-foreground uppercase">Session ID</Label>
                      <div className="flex gap-2 items-center">
                        <Input
                          readOnly
                          value={session.id}
                          className="bg-background text-foreground h-8 text-xs font-mono font-bold"
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs"
                          onClick={() => {
                            navigator.clipboard.writeText(session.id);
                            toast.success("Session ID copied!");
                          }}
                        >
                          Copy
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {runtimeStatus?.state === "STARTING" && (
                <div className="flex flex-col items-center justify-center p-6 space-y-3 text-center bg-muted/10 border border-border/40 rounded-xl">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                  <div>
                    <h4 className="font-semibold text-foreground">Starting Browser...</h4>
                  </div>
                </div>
              )}

              {runtimeStatus?.state === "BROWSER_READY" && (
                <div className="space-y-3">
                  <div className="p-3 bg-muted/30 border border-border/40 rounded-xl">
                    <p className="text-xs text-muted-foreground">
                      Browser is ready. Join the Teams meeting call now.
                    </p>
                  </div>
                  <Button
                    onClick={handleJoinPrepared}
                    className="w-full bg-primary hover:bg-primary/95 text-primary-foreground font-semibold gap-2"
                  >
                    <PlayCircle className="h-4.5 w-4.5" /> Join Meeting
                  </Button>
                </div>
              )}

              {runtimeStatus?.state === "JOINING" && (
                <div className="flex flex-col items-center justify-center p-6 space-y-3 text-center bg-muted/10 border border-border/40 rounded-xl">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                  <div>
                    <h4 className="font-semibold text-foreground">Entering Call Lobby...</h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      Connecting guest participant to Teams meeting URL.
                    </p>
                  </div>
                </div>
              )}

              {runtimeStatus?.state === "WAITING" && (
                <div className="space-y-4 p-4 border border-amber-200/60 bg-amber-50/15 rounded-xl">
                  <div className="flex items-center gap-2 text-amber-700">
                    <AlertTriangle className="h-5 w-5 animate-bounce" />
                    <h4 className="font-semibold text-xs">Waiting for approval</h4>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    The guest participant is waiting to be admitted. Please click 'Admit' inside Microsoft Teams UI.
                  </p>
                  <Button
                    onClick={() => handleJoinPrepared()}
                    className="w-full bg-amber-600 hover:bg-amber-700 text-white text-xs h-8"
                  >
                    Refresh Admittance Status
                  </Button>
                </div>
              )}

              {runtimeStatus?.state === "CONNECTED" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold bg-green-100 text-green-700 border border-green-200">
                      CONNECTED
                    </span>
                    <span className="text-xs text-muted-foreground font-medium">
                      Slide {runtimeStatus.current_slide} of {slidesConfig?.total_slides || 0}
                    </span>
                  </div>

                  {/* Narration box */}
                  <div className="p-3.5 bg-background border border-border/80 rounded-xl space-y-2">
                    <div className="flex justify-between items-center border-b border-border/40 pb-1.5 mb-1.5">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                        AI Speaking (Narration)
                      </span>
                      {runtimeStatus.speech_state === "SPEAKING" ? (
                        <span className="inline-flex items-center text-[10px] text-green-600 gap-1 font-semibold">
                          <Volume2 className="h-3 w-3 animate-pulse" /> Speaking Stream...
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-[10px] text-muted-foreground gap-1">
                          <VolumeX className="h-3 w-3" /> Speech Idle
                        </span>
                      )}
                    </div>
                    <p className="text-xs italic text-foreground leading-relaxed">
                      {slidesConfig?.slides?.[runtimeStatus.current_slide - 1]?.narration || "Narrating slide content..."}
                    </p>
                  </div>

                  {/* Refactored Audio Playback dropdown & buttons */}
                  <div className="space-y-2 border border-border/60 rounded-xl p-3 bg-card text-xs">
                    <Label className="text-[10px] font-bold text-muted-foreground uppercase">Generated Audio Playback</Label>
                    <div className="flex gap-2">
                      <select
                        value={selectedAudioTrack}
                        onChange={(e) => setSelectedAudioTrack(e.target.value)}
                        className="flex-1 rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground"
                      >
                        {audioPlayList.map((track) => (
                          <option key={track} value={track}>
                            {track}
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        onClick={async () => {
                          if (selectedAudioTrack) {
                            try {
                              await playRuntimeAudioTrack(session.id, selectedAudioTrack);
                              toast.success("Playing track: " + selectedAudioTrack);
                            } catch (e: any) {
                              toast.error(e.message || "Failed to play audio");
                            }
                          }
                        }}
                        className="h-8 text-xs font-semibold"
                      >
                        Play
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            await stopRuntimeAudioTrack(session.id);
                            toast.success("Audio playback stopped");
                          } catch (e: any) {
                            toast.error(e.message || "Failed to stop audio");
                          }
                        }}
                        className="h-8 text-xs"
                      >
                        Stop
                      </Button>
                    </div>
                  </div>

                  {/* Manual Slide overrides */}
                  <div className="flex justify-between items-center gap-3 pt-2 border-t border-border/40">
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handlePrevSlide}
                        disabled={runtimeStatus.current_slide <= 1}
                        className="h-8 px-3 text-xs"
                      >
                        Prev Slide
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleNextSlide}
                        disabled={runtimeStatus.current_slide >= (slidesConfig?.total_slides || 0)}
                        className="h-8 px-3 text-xs"
                      >
                        Next Slide
                      </Button>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleTriggerReconnect}
                        className="h-8 px-2 text-xs border-amber-300 text-amber-700 hover:bg-amber-50/20"
                      >
                        Simulate Drop
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleLeaveMeeting}
                        className="h-8 px-3 text-xs"
                      >
                        Disconnect Call
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {(runtimeStatus?.state === "DISCONNECTED" || runtimeStatus?.state === "RECONNECTING") && (
                <div className="flex flex-col items-center justify-center p-6 space-y-3 text-center bg-amber-50/10 border border-amber-200 rounded-xl">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-amber-500 border-t-transparent" />
                  <div>
                    <h4 className="font-semibold text-amber-700">Connection Interrupted</h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      Attempting reconnection to call stream (Count: {runtimeStatus.reconnect_count})...
                    </p>
                  </div>
                </div>
              )}

              {runtimeStatus?.state === "QUESTIONS" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                      Q&A Interactive Session
                    </span>
                    <span className="text-xs text-muted-foreground">Waiting for questions</span>
                  </div>

                  <p className="text-xs text-muted-foreground leading-relaxed">
                    AI narration has successfully completed. Attendees can now ask questions, or you can simulate them below.
                  </p>

                  {/* Chat log list */}
                  <div className="space-y-2 border border-border/40 rounded-xl p-3 bg-muted/10 max-h-[220px] overflow-y-auto">
                    {messages.length === 0 ? (
                      <p className="text-xs italic text-muted-foreground text-center py-4">No questions asked yet.</p>
                    ) : (
                      <div className="space-y-3">
                        {messages.map((msg) => (
                          <div key={msg.id} className="text-xs space-y-1">
                            <div className="flex justify-between">
                              <span className={cn(
                                "font-bold",
                                msg.speaker_name.includes("Assistant") || msg.speaker_name.includes("Trainer")
                                  ? "text-primary"
                                  : "text-foreground"
                              )}>
                                {msg.speaker_name}
                              </span>
                              <span className="text-[10px] text-muted-foreground">
                                {new Date(msg.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                            <p className="text-muted-foreground pl-2 border-l border-border/60">
                              {msg.message_text}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Ask Question Form */}
                  <div className="space-y-2 border border-border/60 rounded-xl p-3 bg-card">
                    <Label className="text-xs font-bold text-muted-foreground uppercase">Simulate Employee Question</Label>
                    <div className="grid grid-cols-3 gap-2">
                      <Input
                        placeholder="Name"
                        value={questionSpeaker}
                        onChange={(e) => setQuestionSpeaker(e.target.value)}
                        className="text-xs h-8 col-span-1"
                      />
                      <Input
                        placeholder="Type question here..."
                        value={newQuestionText}
                        onChange={(e) => setNewQuestionText(e.target.value)}
                        className="text-xs h-8 col-span-2"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleAskQuestion();
                        }}
                      />
                    </div>
                    <Button
                      onClick={handleAskQuestion}
                      className="w-full bg-secondary hover:bg-secondary/90 text-secondary-foreground text-xs h-7"
                    >
                      Submit Question
                    </Button>
                  </div>

                  <div className="flex justify-between pt-2 border-t border-border/40">
                    <Button
                      variant="outline"
                      onClick={handleTriggerReconnect}
                      className="h-8 text-xs border-amber-300 text-amber-700"
                    >
                      Simulate Drop
                    </Button>
                    <Button
                      onClick={handleLeaveMeeting}
                      className="bg-green-600 hover:bg-green-700 text-white text-xs h-8"
                    >
                      Finalize Onboarding Session
                    </Button>
                  </div>
                </div>
              )}

              {runtimeStatus?.state === "COMPLETED" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold bg-green-100 text-green-700 border border-green-200">
                      Induction Completed
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Onboarding session has been closed. You can now download the generated reports and logs.
                  </p>

                  {/* Live Attendance List Summary */}
                  {attendanceSummary && (
                    <div className="space-y-2 border border-border/60 rounded-xl p-3 bg-muted/10">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Invited: <strong>{attendanceSummary.total_invited}</strong></span>
                        <span>Attended: <strong>{attendanceSummary.joined}</strong></span>
                        <span>Absent: <strong>{attendanceSummary.absent}</strong></span>
                      </div>
                      <div className="max-h-[120px] overflow-y-auto space-y-1.5 pt-1.5 border-t border-border/40">
                        {attendanceSummary.attendees?.map((att: any, idx: number) => (
                          <div key={idx} className="flex justify-between text-[11px]">
                            <span className="font-medium text-foreground">{att.name}</span>
                            <span className={cn(
                              "font-bold text-[9px] px-1.5 rounded-full",
                              att.status === "PRESENT" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                            )}>
                              {att.status} ({att.duration_minutes}m)
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <Button variant="outline" size="sm" asChild className="text-xs h-8 gap-1.5">
                      <a href={`${BACKEND_BASE}/runtime/${id}/report`} target="_blank" rel="noopener noreferrer">
                        <Download className="h-3.5 w-3.5" /> Download Report
                      </a>
                    </Button>
                    <Button variant="outline" size="sm" asChild className="text-xs h-8 gap-1.5">
                      <a href={`${BACKEND_BASE}/runtime/${id}/transcript`} target="_blank" rel="noopener noreferrer">
                        <Download className="h-3.5 w-3.5" /> Download Transcript
                      </a>
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column - Side panel (Metadata, checklist, start meeting) */}
        <div className="space-y-6">
          {/* Metadata Card */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Session Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Status</span>
                <StatusBadge status={session.status} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground flex items-center gap-1.5">
                  <CalendarDays className="h-4 w-4" /> Date
                </span>
                <span className="font-medium">{new Date(session.date).toLocaleDateString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground flex items-center gap-1.5">
                  <Users className="h-4 w-4" /> Trainer
                </span>
                <span className="font-medium">{session.trainer}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Department</span>
                <span className="font-medium">{session.department}</span>
              </div>
            </CardContent>
          </Card>

          {/* Meeting checklist */}
          <SectionShell title="Induction Checklist" icon={ClipboardCheck}>
            <Card className="border-border/60">
              <CardContent className="p-4 space-y-2">
                {prep.map((step) => (
                  <div
                    key={step.label}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
                      step.done ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-5 w-5 items-center justify-center rounded-full border shrink-0",
                        step.done
                          ? "bg-green-100 text-green-700 border-green-200"
                          : "border-border bg-muted",
                      )}
                    >
                      {step.done && <Check className="h-3.5 w-3.5" />}
                    </span>
                    <span className={step.done ? "font-semibold" : ""}>{step.label}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </SectionShell>

          {/* Microsoft Teams Meeting Card */}
          <SectionShell title="Teams Orchestration" icon={Video}>
            <Card className="border-border/60">
              <CardContent className="p-4 space-y-4">
                {loadingMeeting ? (
                  <p className="text-xs text-muted-foreground animate-pulse">Loading meeting orchestration status...</p>
                ) : !meeting ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-muted-foreground uppercase">Status</span>
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground border border-border">
                        Not Created
                      </span>
                    </div>

                    <div className="space-y-3 pt-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Teams Meeting URL</Label>
                        <Input
                          placeholder="https://teams.microsoft.com/l/meetup-join/..."
                          value={formUrl}
                          onChange={(e) => setFormUrl(e.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Passcode (Optional)</Label>
                        <Input
                          placeholder="Passcode or Pin"
                          value={formPasscode}
                          onChange={(e) => setFormPasscode(e.target.value)}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Meeting Date</Label>
                          <Input
                            type="date"
                            value={formDate}
                            onChange={(e) => setFormDate(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Meeting Time</Label>
                          <Input
                            type="time"
                            value={formTime}
                            onChange={(e) => setFormTime(e.target.value)}
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Organizer Name</Label>
                        <Input
                          placeholder="HR Trainer Name"
                          value={formOrganizer}
                          onChange={(e) => setFormOrganizer(e.target.value)}
                        />
                      </div>
                    </div>

                    <Button
                      onClick={() => handlePrepareMeetingManual(formUrl, formPasscode, formDate, formTime, formOrganizer)}
                      disabled={scheduling}
                      className="w-full bg-primary hover:bg-primary/95 text-primary-foreground gap-1.5"
                      size="sm"
                    >
                      {scheduling ? "Saving Details..." : "Save & Prepare Meeting"}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-muted-foreground uppercase">Status</span>
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                        Meeting Ready
                      </span>
                    </div>

                    {/* Collapsible Edit/Details area */}
                    <details className="group border border-border/60 rounded-xl overflow-hidden bg-muted/10">
                      <summary className="text-xs font-semibold text-muted-foreground hover:text-foreground cursor-pointer flex items-center justify-between px-3 py-2.5 select-none bg-muted/20">
                        <span>Meeting Configuration</span>
                        <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
                      </summary>
                      <div className="p-3 space-y-3 border-t border-border/40">
                        <div className="space-y-2 text-xs">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Organizer</span>
                            <span className="font-semibold text-foreground truncate max-w-[180px]">{meeting.organizer_name}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Date / Time</span>
                            <span className="font-semibold text-foreground">{meeting.meeting_date} @ {meeting.meeting_time}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Teams URL</span>
                            <span className="font-semibold text-foreground truncate max-w-[180px]" title={meeting.teams_meeting_url}>{meeting.teams_meeting_url}</span>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 pt-1.5 border-t border-border/40">
                          <Button variant="outline" size="sm" asChild className="text-xs h-7">
                            <a href={meeting.teams_meeting_url} target="_blank" rel="noopener noreferrer">
                              View Meeting
                            </a>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              navigator.clipboard.writeText(meeting.teams_meeting_url);
                              toast.success("Teams link copied!");
                            }}
                            className="text-xs h-7"
                          >
                            Copy Link
                          </Button>
                        </div>
                      </div>
                    </details>

                    {/* Sprint 2: Readiness Summary Checkboxes */}
                    <div className="space-y-2 border-t border-border/40 pt-3">
                      <Label className="text-[10px] font-bold text-muted-foreground uppercase">Runtime Assets Readiness</Label>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-border/60 bg-muted/20">
                          <span className={cn(
                            "h-2 w-2 rounded-full",
                            readiness?.has_presentation ? "bg-green-500" : "bg-red-500"
                          )} />
                          <span>Presentation Deck</span>
                        </div>
                        <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-border/60 bg-muted/20">
                          <span className={cn(
                            "h-2 w-2 rounded-full",
                            readiness?.has_employees ? "bg-green-500" : "bg-red-500"
                          )} />
                          <span>Employees List</span>
                        </div>
                        {session?.creation_mode !== "HR" && (
                          <>
                            <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-border/60 bg-muted/20">
                              <span className={cn(
                                "h-2 w-2 rounded-full",
                                readiness?.has_script ? "bg-green-500" : "bg-red-500"
                              )} />
                              <span>AI Script</span>
                            </div>
                            <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-border/60 bg-muted/20">
                              <span className={cn(
                                "h-2 w-2 rounded-full",
                                readiness?.has_faq ? "bg-green-500" : "bg-red-500"
                              )} />
                              <span>Expected FAQs</span>
                            </div>
                          </>
                        )}
                        {session?.creation_mode === "HR" && (
                          <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-violet-500/30 bg-violet-500/5 col-span-2">
                            <span className={cn(
                              "h-2 w-2 rounded-full",
                              readiness?.has_audio ? "bg-green-500" : "bg-amber-500"
                            )} />
                            <span className="text-violet-700">HR Narration Package</span>
                          </div>
                        )}
                        <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-border/60 bg-muted/20 col-span-2 justify-center">
                          <span className={cn(
                            "h-2 w-2 rounded-full",
                            readiness?.has_meeting ? "bg-green-500" : "bg-red-500"
                          )} />
                          <span>Teams URL & Date/Time Configured</span>
                        </div>
                      </div>
                    </div>

                    {/* Progress Timeline */}
                    <div className="space-y-2 border-t border-b border-border/40 py-3">
                      <Label className="text-[10px] font-bold text-muted-foreground uppercase">Orchestration Progress</Label>
                      <div className="relative pl-4 border-l border-border/80 space-y-3.5 text-xs mt-1">
                        <div className="relative">
                          <span className={cn(
                            "absolute -left-[20.5px] top-0.5 flex h-3 w-3 items-center justify-center rounded-full text-white ring-4 ring-background",
                            readiness?.is_ready ? "bg-green-500" : "bg-amber-500"
                          )}>
                            <Check className="h-2 w-2" />
                          </span>
                          <span className="font-semibold text-foreground">
                            {readiness?.is_ready ? "Session Ready" : "Session Preparation Pending"}
                          </span>
                        </div>
                        <div className="relative">
                          <span className="absolute -left-[20.5px] top-0.5 flex h-3 w-3 items-center justify-center rounded-full bg-green-500 text-white ring-4 ring-background">
                            <Check className="h-2 w-2" />
                          </span>
                          <span className="font-semibold text-foreground">Meeting Created</span>
                        </div>
                        <div className="relative">
                          <span className={cn(
                            "absolute -left-[20.5px] top-0.5 flex h-3 w-3 items-center justify-center rounded-full ring-4 ring-background",
                            drafts.length > 0 ? "bg-green-500 text-white" : "bg-muted border border-border"
                          )}>
                            {drafts.length > 0 && <Check className="h-2 w-2" />}
                          </span>
                          <span className={cn(drafts.length > 0 ? "font-semibold text-foreground" : "text-muted-foreground")}>
                            Invitations Sent
                          </span>
                        </div>
                        <div className="relative">
                          <span className="absolute -left-[20.5px] top-0.5 flex h-3 w-3 items-center justify-center rounded-full bg-muted border border-border ring-4 ring-background"></span>
                          <span className="text-muted-foreground">AI Connected</span>
                        </div>
                        <div className="relative">
                          <span className="absolute -left-[20.5px] top-0.5 flex h-3 w-3 items-center justify-center rounded-full bg-muted border border-border ring-4 ring-background"></span>
                          <span className="text-muted-foreground">Waiting</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </SectionShell>

          {/* Start Meeting card deleted in favor of singular AI Meeting Control Console */}
        </div>
      </div>

      {/* Edit Session details dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Session Details</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Session Title</Label>
              <Input
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Department</Label>
                <Select value={editForm.department} onValueChange={(v) => setEditForm({ ...editForm, department: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DEPARTMENTS.map((d) => (
                      <SelectItem key={d} value={d}>{d}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Trainer</Label>
                <Input
                  value={editForm.trainer}
                  onChange={(e) => setEditForm({ ...editForm, trainer: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Date</Label>
              <Input
                type="date"
                value={editForm.date}
                onChange={(e) => setEditForm({ ...editForm, date: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Textarea
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveSession}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the session from the list. Saved presentations and employee batch files will remain intact.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive hover:bg-destructive/90 text-white">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SectionShell({
  title,
  children,
  icon: Icon,
}: {
  title: string;
  children: React.ReactNode;
  icon?: any;
}) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-1.5 px-1">
        {Icon && <Icon className="h-4.5 w-4.5 text-muted-foreground" />}
        <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function SessionNotFound() {
  return (
    <div className="p-8 text-center space-y-4 max-w-md mx-auto">
      <h2 className="text-xl font-bold">Session Not Found</h2>
      <p className="text-muted-foreground text-sm">
        The session you are looking for does not exist or has been deleted.
      </p>
      <Button asChild>
        <Link to="/sessions">Back to Sessions</Link>
      </Button>
    </div>
  );
}
