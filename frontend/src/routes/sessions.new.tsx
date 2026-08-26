import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, ChevronRight, ChevronLeft, Upload, FileText, CheckCircle, Trash2, Edit2, Sparkles, Check, Play, User, Calendar, BookOpen, HelpCircle, Volume2 } from "lucide-react";
import { useState, useEffect } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getPresentations,
  getEmployeeLists,
  getConfiguration,
  uploadPresentation,
  uploadEmployeeList,
  getPresentationScript,
  regeneratePresentationScript,
  updatePresentationScript,
  getPresentationQuestions,
  regeneratePresentationQuestions,
  updatePresentationQuestions,
  getPresentationAssetsStatus,
  createSession,
  updateSession,
  triggerScriptGeneration,
  triggerAudioGeneration,
  triggerPackageGeneration,
  getSessionJobs,
  apiFetch,
  BACKEND_BASE,
  SavedPresentation,
  SavedEmployeeList,
  PresentationScript,
  PresentationQuestion
} from "@/lib/sessions-store";
import { SessionAccordion } from "@/components/review/SessionAccordion";

export const Route = createFileRoute("/sessions/new")({
  head: () => ({
    meta: [
      { title: "Create Session — AutoHR" },
      { name: "description", content: "Create a new induction session." },
    ],
  }),
  component: NewSessionPage,
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

const STEP_LABELS = [
  "Presentation",
  "Employee List",
  "Review AI Presentation",
  "Review Employee Questions",
  "Create Session"
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
      title: data.title || `Slide ${numVal}`,
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

function NewSessionPage() {
  const navigate = useNavigate();
  
  // Wizard state
  const [step, setStep] = useState(1);
  const [presentations, setPresentations] = useState<SavedPresentation[]>([]);
  const [employeeLists, setEmployeeLists] = useState<SavedEmployeeList[]>([]);
  
  // Selected IDs
  const [selectedPresId, setSelectedPresId] = useState<string>("");
  const [selectedEmpId, setSelectedEmpId] = useState<string>("");
  
  // Upload dialog states
  const [uploadingPres, setUploadingPres] = useState(false);
  const [newPresName, setNewPresName] = useState("");
  const [newPresFile, setNewPresFile] = useState<File | null>(null);

  const [uploadingEmp, setUploadingEmp] = useState(false);
  const [newEmpName, setNewEmpName] = useState("");
  const [newEmpFile, setNewEmpFile] = useState<File | null>(null);

  // Script and Question states
  const [script, setScript] = useState<PresentationScript | null>(null);
  const [sessionScript, setSessionScript] = useState<any>(null);
  const [questions, setQuestions] = useState<PresentationQuestion | null>(null);
  const [generatingScript, setGeneratingScript] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [sessionDraft, setSessionDraft] = useState<any>(null);
  const [generatingAudio, setGeneratingAudio] = useState(false);

  // HR Recorded Onboarding states
  const [creationMode, setCreationMode] = useState<"AI" | "HR">("AI");
  const [hrSlides, setHrSlides] = useState<number[]>([]);
  const [loadingHrSlides, setLoadingHrSlides] = useState(false);
  const [uploadingSlideIndex, setUploadingSlideIndex] = useState<number | null>(null);
  const [hrNotes, setHrNotes] = useState<Record<number, string>>({});
  const [hrAudios, setHrAudios] = useState<Record<number, { duration: number; uploaded: boolean }>>({});
  const [validatingHr, setValidatingHr] = useState(false);
  const [hrValidationErrors, setHrValidationErrors] = useState<string[]>([]);
  const [packagingHr, setPackagingHr] = useState(false);
  const [hrPackageCompiled, setHrPackageCompiled] = useState(false);

  // Job progress tracking
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
  const [generatingPackage, setGeneratingPackage] = useState(false);

  // Reuse indicators view status
  const [showScriptEditor, setShowScriptEditor] = useState(false);
  const [showQuestionsEditor, setShowQuestionsEditor] = useState(false);
  const [assetsStatus, setAssetsStatus] = useState<any>(null);

  // Editing states (Slide-by-slide)
  const [editWelcome, setEditWelcome] = useState("");
  const [editClosing, setEditClosing] = useState("");
  const [editNarrations, setEditNarrations] = useState<Record<string, string>>({});
  const [editFaqs, setEditFaqs] = useState<Array<{ question: string; answer: string }>>([]);

  // Session details state
  const [form, setForm] = useState({
    title: "",
    department: "",
    trainer: "",
    date: "",
    description: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // Load existing presentations and employee lists
  useEffect(() => {
    getPresentations().then(setPresentations).catch(console.error);
    getEmployeeLists().then(setEmployeeLists).catch(console.error);
    getConfiguration()
      .then((cfg) => {
        if (cfg?.ai_trainer_name) {
          setForm((prev) => ({ ...prev, trainer: cfg.ai_trainer_name }));
        }
      })
      .catch((err) => console.log("No config found:", err));
  }, []);

  // Polling loop for jobs
  useEffect(() => {
    if (!sessionDraft?.id) return;
    let interval: any;

    const pollJobs = () => {
      getSessionJobs(sessionDraft.id).then((jobs) => {
        const valJob = jobs.find((j: any) => j.job_type === "VALIDATION");
        const parseJob = jobs.find((j: any) => j.job_type === "PARSING");
        const scriptJob = jobs.find((j: any) => j.job_type === "SCRIPT");
        const audioJob = jobs.find((j: any) => j.job_type === "AUDIO");

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

        const packJob = jobs.find((j: any) => j.job_type === "PACKAGE");
        const verJob = jobs.find((j: any) => j.job_type === "VERIFICATION");

        if (packJob) {
          setPackJobProgress(Math.round(packJob.progress * 100));
          setPackJobStatus(packJob.status);
          if (packJob.status === "PROCESSING" || packJob.status === "PENDING") {
            setGeneratingPackage(true);
          } else {
            setGeneratingPackage(false);
          }
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
      }).catch(console.error);
    };

    pollJobs();
    interval = setInterval(pollJobs, 2500);
    return () => clearInterval(interval);
  }, [sessionDraft?.id]);

  // HR Recorded Mode Initialization & Handlers
  useEffect(() => {
    const selectedPres = presentations.find((p) => p.id === selectedPresId);
    const totalSlides = selectedPres ? selectedPres.slide_count : 0;
    
    if (selectedPresId && totalSlides > 0) {
      const slidesArray = Array.from({ length: totalSlides }, (_, i) => i + 1);
      setHrSlides(slidesArray);
      
      const initialNotes: Record<number, string> = {};
      const initialAudios: Record<number, { duration: number; uploaded: boolean }> = {};
      slidesArray.forEach((num) => {
        initialNotes[num] = "";
        initialAudios[num] = { duration: 0, uploaded: false };
      });
      setHrNotes(initialNotes);
      setHrAudios(initialAudios);
    } else {
      setHrSlides([]);
    }
  }, [selectedPresId, presentations]);

  const handleUploadSlideAudio = async (slideNumber: number, file: File) => {
    if (!sessionDraft?.id) {
      toast.error("Draft session not initialized. Please proceed from Step 2.");
      return;
    }
    setUploadingSlideIndex(slideNumber);
    
    const formData = new FormData();
    formData.append("session_id", sessionDraft.id);
    formData.append("slide_number", String(slideNumber));
    formData.append("audio_file", file);
    if (hrNotes[slideNumber]) {
      formData.append("notes", hrNotes[slideNumber]);
    }
    
    try {
      const response = await fetch(`${BACKEND_BASE}/hr-induction/upload-slide-audio`, {
        method: "POST",
        headers: {
          "Authorization": "Bearer autohr_master_secret_token_2026"
        },
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(await response.text());
      }
      
      const data = await response.json();
      setHrAudios((prev) => ({
        ...prev,
        [slideNumber]: { duration: data.duration_ms / 1000.0, uploaded: true }
      }));
      toast.success(`Slide ${slideNumber} narration uploaded successfully!`);
    } catch (err: any) {
      console.error(err);
      toast.error(`Failed to upload audio for Slide ${slideNumber}: ${err.message || "Unknown error"}`);
    } finally {
      setUploadingSlideIndex(null);
    }
  };

  const handleValidateHrMode = async () => {
    if (!sessionDraft?.id) return;
    setValidatingHr(true);
    setHrValidationErrors([]);
    try {
      const data = await apiFetch(`/hr-induction/validate?session_id=${sessionDraft.id}`, {
        method: "POST"
      });
      if (data.valid) {
        toast.success("All slide narrations validated successfully!");
      } else {
        setHrValidationErrors(data.errors || ["Validation failed"]);
        toast.error("Please resolve the validation errors before compiling.");
      }
      return data.valid;
    } catch (err: any) {
      toast.error(err.message || "Failed to run validation");
      return false;
    } finally {
      setValidatingHr(false);
    }
  };

  const handleBuildHrPackage = async () => {
    if (!sessionDraft?.id) return;
    setPackagingHr(true);
    try {
      await apiFetch(`/hr-induction/build-package?session_id=${sessionDraft.id}`, {
        method: "POST"
      });
      toast.success("HR Presentation Package compiled successfully!");
      setHrPackageCompiled(true);
      setStep(4); // Advance to Questions Step
    } catch (err: any) {
      toast.error(err.message || "Failed to compile package");
    } finally {
      setPackagingHr(false);
    }
  };

  // Fetch script when presentation changes or script generation completes
  useEffect(() => {
    setShowScriptEditor(false);
    if (selectedPresId) {
      getPresentationScript(selectedPresId).then((s) => {
        setScript(s);
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
    } else {
      setScript(null);
      setSessionScript(null);
    }
  }, [selectedPresId, scriptJobStatus]);

  // Fetch questions when presentation changes or script generation completes
  useEffect(() => {
    setShowQuestionsEditor(false);
    if (selectedPresId) {
      getPresentationQuestions(selectedPresId).then((q) => {
        setQuestions(q);
        if (q?.questions_content) {
          setEditFaqs(q.questions_content.map(f => ({ question: f.question, answer: f.answer })));
        }
      }).catch(console.error);
    } else {
      setQuestions(null);
    }
  }, [selectedPresId, scriptJobStatus]);

  // Fetch presentation assets status
  useEffect(() => {
    if (selectedPresId) {
      getPresentationAssetsStatus(selectedPresId, creationMode)
        .then(setAssetsStatus)
        .catch(console.error);
    } else {
      setAssetsStatus(null);
    }
  }, [selectedPresId, creationMode, scriptJobStatus, audioJobStatus]);

  const handleGoToStep3 = async () => {
    if (!selectedPresId || !selectedEmpId) return;
    setStep(3);
    if (!sessionDraft) {
      try {
        const title = form.title || presentations.find(p => p.id === selectedPresId)?.name || "New Induction Session";
        const d = await createSession({
          title: title,
          department: form.department || "Operations",
          trainer: form.trainer || "HR Trainer",
          scheduled_at: form.date ? new Date(form.date).toISOString() : new Date().toISOString(),
          presentation_id: selectedPresId,
          employee_list_id: selectedEmpId,
          status: "PENDING",
          creation_mode: creationMode
        } as any);
        setSessionDraft(d);
        setForm(prev => ({ ...prev, title: prev.title || d.name }));

        // For HR mode: backend extracted slides during session creation.
        // Re-fetch presentations so slide_count is updated, then set hrSlides.
        if (creationMode === "HR") {
          setLoadingHrSlides(true);
          try {
            const freshPresentations = await getPresentations();
            setPresentations(freshPresentations);
            const freshPres = freshPresentations.find((p: any) => p.id === selectedPresId);
            const totalSlides = freshPres?.slide_count || 0;
            if (totalSlides > 0) {
              const slidesArray = Array.from({ length: totalSlides }, (_, i) => i + 1);
              setHrSlides(slidesArray);
              const initialNotes: Record<number, string> = {};
              const initialAudios: Record<number, { duration: number; uploaded: boolean }> = {};
              slidesArray.forEach((num) => {
                initialNotes[num] = "";
                initialAudios[num] = { duration: 0, uploaded: false };
              });
              setHrNotes(initialNotes);
              setHrAudios(initialAudios);
            }
          } catch (e) {
            console.error("Failed to refresh presentations after HR session create:", e);
          } finally {
            setLoadingHrSlides(false);
          }
        }
      } catch (err: any) {
        console.error("Failed to create draft session:", err);
        toast.error("Failed to initialize session draft on backend");
      }
    }
  };

  const handleUploadPres = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPresFile || !newPresName.trim()) {
      toast.error("Please select a file and enter a name");
      return;
    }
    setUploadingPres(true);
    try {
      const pres = await uploadPresentation(newPresName, newPresFile);
      toast.success("Presentation uploaded successfully");
      setPresentations((prev) => [pres, ...prev]);
      setSelectedPresId(pres.id);
      setNewPresName("");
      setNewPresFile(null);
    } catch (err: any) {
      toast.error(err.message || "Failed to upload presentation");
    } finally {
      setUploadingPres(false);
    }
  };

  const handleUploadEmp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmpFile || !newEmpName.trim()) {
      toast.error("Please select a file and enter a name");
      return;
    }
    setUploadingEmp(true);
    try {
      const emp = await uploadEmployeeList(newEmpName, newEmpFile);
      toast.success("Employee list uploaded successfully");
      setEmployeeLists((prev) => [emp, ...prev]);
      setSelectedEmpId(emp.id);
      setNewEmpName("");
      setNewEmpFile(null);
    } catch (err: any) {
      toast.error(err.message || "Failed to upload employee list");
    } finally {
      setUploadingEmp(false);
    }
  };

  const handleGenerateScript = async () => {
    if (!selectedPresId || !selectedEmpId) return;
    if (sessionDraft?.id) {
      setGeneratingScript(true);
      try {
        await triggerScriptGeneration(sessionDraft.id);
        toast.success("AI script generation pipeline queued!");
      } catch {
        toast.error("Failed to start script pipeline");
        setGeneratingScript(false);
      }
    } else {
      setGeneratingScript(true);
      try {
        const s = await regeneratePresentationScript(selectedPresId, selectedEmpId);
        setScript(s);
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
        toast.success("AI script generated successfully!");
        setShowScriptEditor(true);
        
        const q = await getPresentationQuestions(selectedPresId);
        if (q) {
          setQuestions(q);
          setEditFaqs(q.questions_content.map(f => ({ question: f.question, answer: f.answer })));
        }
      } catch (err: any) {
        toast.error(err.message || "Failed to generate script");
      } finally {
        setGeneratingScript(false);
      }
    }
  };

  const handleGenerateAudio = async () => {
    if (!sessionDraft?.id) {
      toast.error("Please advance past Step 2 to establish a session context first.");
      return;
    }
    setGeneratingAudio(true);
    try {
      await triggerAudioGeneration(sessionDraft.id);
      toast.success("Speech audio generation pipeline queued!");
    } catch {
      toast.error("Failed to start audio pipeline");
      setGeneratingAudio(false);
    }
  };

  const handleGeneratePackage = async () => {
    if (!sessionDraft?.id) {
      toast.error("Please advance past Step 2 to establish a session context first.");
      return;
    }
    setGeneratingPackage(true);
    try {
      await triggerPackageGeneration(sessionDraft.id);
      toast.success("Packaging pipeline queued!");
    } catch {
      toast.error("Failed to start packaging pipeline");
      setGeneratingPackage(false);
    }
  };

  const handleGenerateQuestions = async () => {
    if (!selectedPresId || !selectedEmpId) return;
    setGeneratingQuestions(true);
    try {
      const q = await regeneratePresentationQuestions(selectedPresId, selectedEmpId);
      setQuestions(q);
      setEditFaqs(q.questions_content.map(f => ({ question: f.question, answer: f.answer })));
      toast.success("Employee questions generated successfully!");
      setShowQuestionsEditor(true);
    } catch (err: any) {
      toast.error(err.message || "Failed to generate questions");
    } finally {
      setGeneratingQuestions(false);
    }
  };

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

  const handleSaveScriptEdits = async () => {
    if (!script || !sessionScript) return;
    try {
      await updatePresentationScript(script.id, sessionScript);
      toast.success("Script updates saved successfully");
    } catch (err: any) {
      toast.error("Failed to save script edits");
    }
  };

  const handleSaveQuestionsEdits = async () => {
    if (!questions) return;
    try {
      await updatePresentationQuestions(questions.id, editFaqs);
      toast.success("Questions updates saved successfully");
    } catch (err: any) {
      toast.error("Failed to save questions edits");
    }
  };

  const submitSession = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!form.title.trim()) next.title = "Title is required";
    if (!form.department) next.department = "Department is required";
    if (!form.trainer.trim()) next.trainer = "Trainer is required";
    if (!form.date) next.date = "Date is required";
    if (Object.keys(next).length) {
      setErrors(next);
      return;
    }
    setSubmitting(true);
    try {
      let session;
      if (sessionDraft?.id) {
        await updateSession(sessionDraft.id, {
          title: form.title,
          department: form.department,
          trainer: form.trainer,
          date: form.date,
          description: form.description,
          status: "READY"
        });
        session = { id: sessionDraft.id };
      } else {
        session = await createSession({
          ...form,
          presentation_id: selectedPresId,
          employee_list_id: selectedEmpId,
        } as any);
      }
      toast.success("Induction session created!");
      navigate({ to: "/sessions/$id", params: { id: session.id } });
    } catch (err) {
      console.error(err);
      toast.error("Failed to save session on backend");
    } finally {
      setSubmitting(false);
    }
  };

  const set = <K extends keyof typeof form>(key: K, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: "" }));
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground">
            <Link to="/sessions">
              <ArrowLeft className="h-4 w-4 mr-1" /> Back to sessions
            </Link>
          </Button>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Create New Induction</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Step {step} of 5: {STEP_LABELS[step - 1]}
          </p>
        </div>
        
        {/* Step Indicator */}
        <div className="flex items-center gap-1.5 bg-muted/60 p-1.5 rounded-lg border border-border">
          {[1, 2, 3, 4, 5].map((num) => (
            <div
              key={num}
              className={`h-7 w-7 rounded-md flex items-center justify-center text-xs font-semibold transition-all ${
                step === num
                  ? "bg-primary text-primary-foreground shadow"
                  : step > num
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "bg-transparent text-muted-foreground"
              }`}
              title={STEP_LABELS[num - 1]}
            >
              {step > num ? <Check className="h-3.5 w-3.5" /> : num}
            </div>
          ))}
        </div>
      </div>

      {/* STEP 1: SELECT PRESENTATION */}
      {step === 1 && (
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-xl flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-primary" /> Step 1: Presentation Setup
            </CardTitle>
            <CardDescription>
              Choose a PowerPoint presentation slide deck from your saved library or upload a new training deck.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Creation Mode Selector */}
            <div className="space-y-2">
              <Label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Creation Mode</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setCreationMode("AI")}
                  className={`flex flex-col items-start gap-1.5 p-4 rounded-xl border text-left transition-all ${
                    creationMode === "AI"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border/60 bg-card hover:border-muted-foreground/30"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className={`h-4 w-4 ${creationMode === "AI" ? "text-primary" : "text-muted-foreground"}`} />
                    <span className="font-semibold text-sm">AI Generated</span>
                    {creationMode === "AI" && <Check className="h-3.5 w-3.5 text-primary ml-auto" />}
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    AI writes narration scripts and generates voice audio from your slide deck automatically.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setCreationMode("HR")}
                  className={`flex flex-col items-start gap-1.5 p-4 rounded-xl border text-left transition-all ${
                    creationMode === "HR"
                      ? "border-violet-500 bg-violet-500/5 ring-1 ring-violet-500"
                      : "border-border/60 bg-card hover:border-muted-foreground/30"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Volume2 className={`h-4 w-4 ${creationMode === "HR" ? "text-violet-500" : "text-muted-foreground"}`} />
                    <span className="font-semibold text-sm">HR Recorded</span>
                    {creationMode === "HR" && <Check className="h-3.5 w-3.5 text-violet-500 ml-auto" />}
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    HR team records narration for each slide manually. Upload WAV/MP3 audio per slide.
                  </p>
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {presentations.map((pres) => (
                <div
                  key={pres.id}
                  onClick={() => setSelectedPresId(pres.id)}
                  className={`p-4 border rounded-xl cursor-pointer transition-all flex flex-col justify-between hover:shadow-md ${
                    selectedPresId === pres.id
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border/60 bg-card hover:border-muted-foreground/30"
                  }`}
                >
                  <div>
                    <h3 className="font-semibold text-card-foreground">{pres.name}</h3>
                    <p className="text-xs text-muted-foreground mt-1 truncate">{pres.original_filename}</p>
                  </div>
                  
                  {selectedPresId === pres.id ? (
                    <div className="mt-4 pt-3 border-t border-border/40 grid grid-cols-2 gap-y-2 gap-x-4 text-xs text-muted-foreground">
                      <div>Uploaded: <span className="font-semibold text-foreground">{new Date(pres.uploaded_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span></div>
                      <div>Sessions Count: <span className="font-semibold text-foreground">{pres.session_count} runs</span></div>
                      <div>Slides: <span className="font-semibold text-foreground">{pres.slide_count || (script ? Object.keys(script.script_content.slide_narrations || {}).length : 0)} slides</span></div>
                      {creationMode === "AI" && <div>Presentation Script: <span className={`font-semibold ${script ? "text-green-600" : "text-amber-600"}`}>{script ? "✓ Ready" : "Not Prepared"}</span></div>}
                      {creationMode === "AI" && <div>Employee Questions: <span className={`font-semibold ${questions ? "text-green-600" : "text-amber-600"}`}>{questions ? "✓ Ready" : "Not Prepared"}</span></div>}
                      {creationMode === "HR" && <div className="col-span-2">Mode: <span className="font-semibold text-violet-600">HR Recorded — Upload slide narrations next</span></div>}
                    </div>
                  ) : (
                    <div className="mt-4 pt-3 border-t border-border/40 flex justify-between items-center text-xs text-muted-foreground">
                      <span>Used in {pres.session_count} sessions</span>
                      <span>Uploaded {new Date(pres.uploaded_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="border-t border-border pt-6">
              <h3 className="text-sm font-semibold mb-3">Upload New Presentation</h3>
              <form onSubmit={handleUploadPres} className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="Presentation Name (e.g. Safety Training)"
                    value={newPresName}
                    onChange={(e) => setNewPresName(e.target.value)}
                  />
                </div>
                <div className="flex-1 flex gap-2">
                  <Input
                    type="file"
                    accept=".pptx"
                    onChange={(e) => setNewPresFile(e.target.files?.[0] || null)}
                    className="cursor-pointer"
                  />
                  <Button type="submit" disabled={uploadingPres}>
                    <Upload className="h-4 w-4 mr-2" /> Upload
                  </Button>
                </div>
              </form>
            </div>

            <div className="flex justify-end pt-4 border-t border-border">
              <Button
                onClick={() => setStep(2)}
                disabled={!selectedPresId}
                className="gap-2"
              >
                Next Step <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STEP 2: SELECT EMPLOYEE LIST */}
      {step === 2 && (
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-xl flex items-center gap-2">
              <User className="h-5 w-5 text-primary" /> Step 2: Employee List Setup
            </CardTitle>
            <CardDescription>
              Select an attendee Excel register sheet or upload a new new-hire batch list.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {employeeLists.map((emp) => (
                <div
                  key={emp.id}
                  onClick={() => setSelectedEmpId(emp.id)}
                  className={`p-4 border rounded-xl cursor-pointer transition-all flex flex-col justify-between hover:shadow-md ${
                    selectedEmpId === emp.id
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border/60 bg-card hover:border-muted-foreground/30"
                  }`}
                >
                  <div>
                    <h3 className="font-semibold text-card-foreground">{emp.name}</h3>
                    <p className="text-xs text-muted-foreground mt-1 truncate">{emp.original_filename}</p>
                  </div>
                  
                  {selectedEmpId === emp.id ? (
                    <div className="mt-4 pt-3 border-t border-border/40 grid grid-cols-2 gap-y-2 gap-x-4 text-xs text-muted-foreground">
                      <div>Uploaded: <span className="font-semibold text-foreground">{new Date(emp.uploaded_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span></div>
                      <div>Employees: <span className="font-semibold text-foreground">{emp.employee_count} Attendees</span></div>
                      <div>Last Used: <span className="font-semibold text-foreground">{new Date(emp.last_used).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span></div>
                    </div>
                  ) : (
                    <div className="mt-4 pt-3 border-t border-border/40 flex justify-between items-center text-xs text-muted-foreground">
                      <span>{emp.employee_count} Employees</span>
                      <span>Uploaded {new Date(emp.uploaded_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="border-t border-border pt-6">
              <h3 className="text-sm font-semibold mb-3">Upload New Employee List</h3>
              <form onSubmit={handleUploadEmp} className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="Batch Name (e.g. July 2026 Batch)"
                    value={newEmpName}
                    onChange={(e) => setNewEmpName(e.target.value)}
                  />
                </div>
                <div className="flex-1 flex gap-2">
                  <Input
                    type="file"
                    accept=".xlsx"
                    onChange={(e) => setNewEmpFile(e.target.files?.[0] || null)}
                    className="cursor-pointer"
                  />
                  <Button type="submit" disabled={uploadingEmp}>
                    <Upload className="h-4 w-4 mr-2" /> Upload
                  </Button>
                </div>
              </form>
            </div>

            <div className="flex justify-between pt-4 border-t border-border">
              <Button variant="outline" onClick={() => setStep(1)} className="gap-2">
                <ChevronLeft className="h-4 w-4" /> Back
              </Button>
              <Button
                onClick={handleGoToStep3}
                disabled={!selectedEmpId}
                className="gap-2"
              >
                Next Step <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STEP 3: AI PRESENTATION REVIEW or HR NARRATION UPLOAD */}
      {step === 3 && (
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-xl flex items-center justify-between">
              <span className="flex items-center gap-2">
                {creationMode === "HR" ? (
                  <><Volume2 className="h-5 w-5 text-violet-500" /> Step 3: Upload Slide Narrations</>
                ) : (
                  <><FileText className="h-5 w-5 text-primary" /> Step 3: Review AI Presentation</>
                )}
              </span>
              {creationMode === "HR" && (
                <span className="text-[10px] font-mono bg-violet-500/10 text-violet-600 border border-violet-500/20 px-2 py-0.5 rounded-full">
                  HR Recorded Mode
                </span>
              )}
            </CardTitle>
            <CardDescription>
              {creationMode === "HR"
                ? "Record narration audio for each slide, add notes, and upload them one by one. All slides must have audio before compiling."
                : "Review slide narration scripts. You can edit them line by line directly on screen."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">

            {/* ===== HR RECORDED MODE ===== */}
            {creationMode === "HR" ? (
              <div className="space-y-5">
                {/* Narration Reuse Panel */}
                <div className="p-4 rounded-xl border border-border/60 bg-muted/10 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-muted-foreground uppercase text-[10px] tracking-wider">Narration Audio Status</span>
                    <Badge variant={assetsStatus?.narration_exists ? "default" : "destructive"} className="text-[9px]">
                      {assetsStatus?.narration_exists ? "Generated" : "Missing"}
                    </Badge>
                  </div>
                  {assetsStatus?.narration_exists ? (
                    <div className="text-violet-700 bg-violet-500/5 border border-violet-500/20 p-2.5 rounded-lg leading-normal">
                      <strong>✓ Pre-existing Narration Detected:</strong> An HR recorded narration file (`narration.wav`) is already generated for this presentation. You can proceed directly to build the package.
                    </div>
                  ) : (
                    <div className="text-amber-700 bg-amber-500/5 border border-amber-500/20 p-2.5 rounded-lg leading-normal">
                      <strong>Notice:</strong> No Narration file is generated for this presentation yet. Please upload audio for each slide below, then validate and click "Build Package".
                    </div>
                  )}
                </div>

                {/* Progress Summary */}
                <div className="flex items-center justify-between p-3 bg-muted/40 rounded-xl border border-border/40">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">Uploaded:</span>
                    <span className="font-semibold">
                      {Object.values(hrAudios).filter((a) => a.uploaded).length} / {hrSlides.length} slides
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {hrValidationErrors.length > 0 && (
                      <span className="text-xs text-red-500 font-medium">{hrValidationErrors.length} errors</span>
                    )}
                    {Object.values(hrAudios).filter((a) => a.uploaded).length === hrSlides.length && hrSlides.length > 0 && (
                      <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                        <CheckCircle className="h-3.5 w-3.5" /> All narrations ready
                      </span>
                    )}
                  </div>
                </div>

                {/* Slides */}
                {loadingHrSlides ? (
                  <div className="p-8 border border-dashed border-border rounded-xl text-center space-y-3">
                    <div className="h-8 w-8 mx-auto border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm text-muted-foreground">Extracting slides from presentation...</p>
                  </div>
                ) : hrSlides.length === 0 ? (
                  <div className="p-8 border border-dashed border-border rounded-xl text-center space-y-3">
                    <Volume2 className="h-10 w-10 text-muted-foreground/50 mx-auto" />
                    <p className="text-sm text-muted-foreground">
                      No slides detected. Ensure the presentation was uploaded and processed successfully.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
                    {hrSlides.map((slideNum) => {
                      const audioState = hrAudios[slideNum];
                      const isUploading = uploadingSlideIndex === slideNum;
                      const isUploaded = audioState?.uploaded;
                      const thumbnailUrl = sessionDraft?.id
                        ? `${BACKEND_BASE}/hr-induction/slides/${sessionDraft.id}/${slideNum}.png`
                        : null;

                      return (
                        <div
                          key={slideNum}
                          className={`rounded-xl border transition-all ${
                            isUploaded
                              ? "border-green-500/30 bg-green-500/3"
                              : "border-border/60 bg-card"
                          }`}
                        >
                          <div className="flex gap-4 p-4">
                            {/* Slide Thumbnail */}
                            <div className="flex-shrink-0 w-28 h-18 rounded-lg overflow-hidden border border-border/40 bg-muted/30 flex items-center justify-center text-xs text-muted-foreground">
                              {thumbnailUrl ? (
                                <img
                                  src={thumbnailUrl}
                                  alt={`Slide ${slideNum}`}
                                  className="w-full h-full object-cover"
                                  onError={(e) => {
                                    (e.target as HTMLImageElement).style.display = "none";
                                  }}
                                />
                              ) : (
                                <span className="text-[10px] text-center px-1">Slide {slideNum}</span>
                              )}
                            </div>

                            {/* Content */}
                            <div className="flex-1 space-y-3 min-w-0">
                              <div className="flex items-center justify-between">
                                <h4 className="font-semibold text-sm">
                                  Slide {slideNum}
                                  {isUploaded && (
                                    <span className="ml-2 text-[10px] text-green-600 font-medium">
                                      ✓ {audioState.duration.toFixed(1)}s
                                    </span>
                                  )}
                                </h4>
                                {isUploaded && (
                                  <span className="text-[10px] bg-green-500/10 text-green-600 border border-green-500/20 px-2 py-0.5 rounded-full font-medium">
                                    Narration Ready
                                  </span>
                                )}
                              </div>

                              {/* Notes */}
                              <div>
                                <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                                  Slide Notes
                                </Label>
                                <Textarea
                                  value={hrNotes[slideNum] || ""}
                                  onChange={(e) => setHrNotes((prev) => ({ ...prev, [slideNum]: e.target.value }))}
                                  placeholder="What does HR intend to say for this slide? (for future reference)"
                                  rows={2}
                                  className="mt-1 resize-none text-sm"
                                />
                              </div>

                              {/* Audio Upload */}
                              <div className="flex items-center gap-2">
                                <label
                                  className={`flex items-center gap-2 cursor-pointer px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                                    isUploading
                                      ? "opacity-50 pointer-events-none border-border/40 text-muted-foreground"
                                      : isUploaded
                                      ? "border-green-500/30 text-green-700 bg-green-500/5 hover:bg-green-500/10"
                                      : "border-violet-500/30 text-violet-700 bg-violet-500/5 hover:bg-violet-500/10"
                                  }`}
                                >
                                  <Upload className="h-3.5 w-3.5" />
                                  {isUploading ? "Uploading..." : isUploaded ? "Re-upload Audio" : "Upload Narration (WAV/MP3)"}
                                  <input
                                    type="file"
                                    accept=".wav,.mp3"
                                    className="hidden"
                                    onChange={async (e) => {
                                      const f = e.target.files?.[0];
                                      if (f) await handleUploadSlideAudio(slideNum, f);
                                      e.target.value = "";
                                    }}
                                    disabled={isUploading}
                                  />
                                </label>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Validation Errors */}
                {hrValidationErrors.length > 0 && (
                  <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-xl space-y-1">
                    <p className="text-xs font-semibold text-red-600">Validation Errors</p>
                    {hrValidationErrors.map((err, i) => (
                      <p key={i} className="text-xs text-red-500">• {err}</p>
                    ))}
                  </div>
                )}

                {/* HR Actions */}
                <div className="flex justify-between pt-4 border-t border-border">
                  <Button variant="outline" onClick={() => setStep(2)} className="gap-2">
                    <ChevronLeft className="h-4 w-4" /> Back
                  </Button>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      onClick={handleValidateHrMode}
                      disabled={validatingHr || hrSlides.length === 0}
                      className="gap-2 text-amber-600 border-amber-600/30 hover:bg-amber-600 hover:text-white"
                    >
                      <CheckCircle className="h-4 w-4" />
                      {validatingHr ? "Validating..." : "Validate All"}
                    </Button>
                    <Button
                      onClick={handleBuildHrPackage}
                      disabled={packagingHr || validatingHr || hrSlides.length === 0 || hrPackageCompiled}
                      className="gap-2 bg-violet-600 hover:bg-violet-700 text-white"
                    >
                      <Sparkles className="h-4 w-4" />
                      {packagingHr ? "Compiling..." : hrPackageCompiled ? "✓ Package Built" : "Build Package"}
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              /* ===== AI MODE (original content below) ===== */
              <></>
            )}

            {/* ===== AI MODE CONTENT ===== */}
            {creationMode === "AI" && (
              <>
                {/* Narration Reuse Panel */}
                <div className="p-4 rounded-xl border border-border/60 bg-muted/10 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-muted-foreground uppercase text-[10px] tracking-wider">Narration Audio Status</span>
                    <Badge variant={assetsStatus?.narration_exists ? "default" : "destructive"} className="text-[9px]">
                      {assetsStatus?.narration_exists ? "Generated" : "Missing"}
                    </Badge>
                  </div>
                  {assetsStatus?.narration_exists ? (
                    <div className="text-green-700 bg-green-500/5 border border-green-500/20 p-2.5 rounded-lg leading-normal">
                      <strong>✓ Pre-existing Narration Detected:</strong> An AI narration file (`narration.wav`) is already generated for this presentation. You can proceed directly to the next step to continue with the existing narration file.
                    </div>
                  ) : (
                    <div className="text-amber-700 bg-amber-500/5 border border-amber-500/20 p-2.5 rounded-lg leading-normal">
                      <strong>Notice:</strong> No Narration file is generated for this presentation yet. Please scroll down to "Advanced Settings" to generate the TTS Audio and compile the package.
                    </div>
                  )}
                </div>

                {!script ? (
                  <div className="p-8 border border-dashed border-border rounded-xl text-center space-y-4">
                    <FileText className="h-10 w-10 text-muted-foreground/60 mx-auto" />
                    <div>
                      <h3 className="font-semibold text-lg">No Script Prepared</h3>
                      <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                        There is no active trainer script for this presentation. Expand Advanced Settings below to generate one.
                      </p>
                    </div>
                  </div>
                ) : !showScriptEditor ? (
                  <div className="p-6 border border-green-100 bg-green-50/10 rounded-xl space-y-4 text-center">
                    <CheckCircle className="h-8 w-8 text-green-600 mx-auto" />
                    <div>
                      <h3 className="font-bold text-base text-foreground">Presentation Script Ready</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        An AI presentation script is already generated and verified for this presentation.
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        Last Updated: {new Date(script.generated_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                      </p>
                    </div>
                    <Button onClick={() => setShowScriptEditor(true)} variant="outline" size="sm">
                      View / Edit Content
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-5 max-h-[500px] overflow-y-auto pr-2">
                    {sessionScript && (
                      <SessionAccordion
                        sessionScript={sessionScript}
                        onOpeningChange={handleOpeningChange}
                        onSlideChange={handleSlideChange}
                        onClosingChange={handleClosingChange}
                      />
                    )}
                    <div className="flex justify-end">
                      <Button onClick={handleSaveScriptEdits} variant="secondary">
                        Save Changes
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Advanced Settings section (AI only) */}
            {creationMode === "AI" && (
              <div className="mt-6 border-t border-border pt-4">
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
                          disabled={generatingAudio || !script}
                          className="text-blue-600 hover:text-white border-blue-600/30 hover:bg-blue-600 gap-1.5 shrink-0"
                        >
                          <Volume2 className="h-4 w-4" /> {generatingAudio ? "Synthesizing..." : "Generate TTS Audio"}
                        </Button>
                        {audioJobStatus === "COMPLETED" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleGeneratePackage}
                            disabled={generatingPackage || packJobStatus === "PROCESSING" || packJobStatus === "PENDING"}
                            className="text-emerald-600 hover:text-white border-emerald-600/30 hover:bg-emerald-600 gap-1.5 shrink-0"
                          >
                            <Sparkles className="h-4 w-4" /> {generatingPackage ? "Packaging..." : "Generate Package"}
                          </Button>
                        )}
                        {audioJobProgress !== null && audioJobStatus !== "COMPLETED" && (
                          <div className="flex-1 flex items-center gap-2">
                            <Progress value={audioJobProgress} className="h-2 flex-1" />
                            <span className="text-[10px] font-mono text-muted-foreground">{audioJobProgress}%</span>
                          </div>
                        )}
                        {packJobProgress !== null && packJobStatus !== "COMPLETED" && (
                          <div className="flex-1 flex items-center gap-2">
                            <Progress value={packJobProgress} className="h-2 flex-1" />
                            <span className="text-[10px] font-mono text-muted-foreground">{packJobProgress}%</span>
                          </div>
                        )}
                      </div>

                      {(audioJobStatus || verJobStatus || packJobStatus) && (
                        <div className="mt-2 text-xs space-y-1.5 bg-muted/40 p-2.5 rounded-lg border border-border/40">
                          <p className="font-bold text-[10px] uppercase text-muted-foreground">Deployment Pipelines</p>
                          <div className="flex justify-between items-center text-[11px]">
                            <span className="text-muted-foreground">1. TTS Audio Generation:</span>
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
            )}

            {/* AI mode footer navigation */}
            {creationMode === "AI" && (
              <div className="flex justify-between pt-4 border-t border-border">
                <Button variant="outline" onClick={() => setStep(2)} className="gap-2">
                  <ChevronLeft className="h-4 w-4" /> Back
                </Button>
                <Button
                  onClick={() => setStep(4)}
                  disabled={!script || packJobStatus !== "COMPLETED"}
                  className="gap-2"
                >
                  Next Step <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* STEP 4: REVIEW EMPLOYEE QUESTIONS */}
      {step === 4 && (
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-xl flex items-center justify-between">
              <span className="flex items-center gap-2">
                <HelpCircle className="h-5 w-5 text-primary" /> Step 4: Review Employee Questions
              </span>
            </CardTitle>
            <CardDescription>
              Verify questions employees might ask during safety/operations induction. Customize the default answers.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {!questions ? (
              <div className="p-8 border border-dashed border-border rounded-xl text-center space-y-4">
                <HelpCircle className="h-10 w-10 text-muted-foreground/60 mx-auto" />
                <div>
                  <h3 className="font-semibold text-lg">No Questions Prepared</h3>
                  <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                    There are no saved expected questions for this presentation. Expand Options below to generate defaults.
                  </p>
                </div>
              </div>
            ) : !showQuestionsEditor ? (
              <div className="p-6 border border-green-100 bg-green-50/10 rounded-xl space-y-4 text-center">
                <CheckCircle className="h-8 w-8 text-green-600 mx-auto" />
                <div>
                  <h3 className="font-bold text-base text-foreground">Employee Questions Ready</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    Expected employee FAQs are prepared for this training deck.
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Last Updated: {new Date(questions.generated_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <Button onClick={() => setShowQuestionsEditor(true)} variant="outline" size="sm">
                  View / Edit Content
                </Button>
              </div>
            ) : (
              <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
                {editFaqs.map((faq, idx) => (
                  <div key={idx} className="p-4 border border-border/60 rounded-xl space-y-3 bg-card">
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

                <div className="flex justify-end">
                  <Button onClick={handleSaveQuestionsEdits} variant="secondary">
                    Save Changes
                  </Button>
                </div>
              </div>
            )}

            {/* More Options section */}
            <div className="mt-6 border-t border-border pt-4">
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

            <div className="flex justify-between pt-4 border-t border-border">
              <Button variant="outline" onClick={() => setStep(3)} className="gap-2">
                <ChevronLeft className="h-4 w-4" /> Back
              </Button>
              <Button
                onClick={() => setStep(5)}
                disabled={!questions}
                className="gap-2"
              >
                Next Step <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STEP 5: CREATE SESSION */}
      {step === 5 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Details Form */}
          <Card className="md:col-span-2 border-border/60">
            <CardHeader>
              <CardTitle className="text-xl">Step 5: Create Session</CardTitle>
              <CardDescription>Configure scheduling and trainer details to finalize session creation.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submitSession} className="space-y-6">
                <Field label="Session Title" error={errors.title} required>
                  <Input
                    value={form.title}
                    onChange={(e) => set("title", e.target.value)}
                    placeholder="e.g. July 2026 Batch Onboarding"
                  />
                </Field>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="Department" error={errors.department} required>
                    <Select value={form.department} onValueChange={(v) => set("department", v)}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select department" />
                      </SelectTrigger>
                      <SelectContent>
                        {DEPARTMENTS.map((d) => (
                          <SelectItem key={d} value={d}>{d}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>

                  <Field label="Trainer" error={errors.trainer} required>
                    <Input
                      value={form.trainer}
                      onChange={(e) => set("trainer", e.target.value)}
                      placeholder="Trainer full name"
                    />
                    {!form.trainer && (
                      <p className="text-xs text-amber-600 mt-1.5 flex items-center gap-1">
                        <span>⚠️ Trainer profile not configured. Go to the</span>
                        <Link to="/profile" className="underline font-semibold hover:text-amber-800">
                          Profile page
                        </Link>
                        <span>to set your default AI persona.</span>
                      </p>
                    )}
                  </Field>
                </div>

                <Field label="Session Date" error={errors.date} required>
                  <Input
                    type="date"
                    value={form.date}
                    onChange={(e) => set("date", e.target.value)}
                    className="max-w-xs"
                  />
                </Field>

                <Field label="Description" hint="Provide agenda or notes for the session.">
                  <Textarea
                    value={form.description}
                    onChange={(e) => set("description", e.target.value)}
                    rows={3}
                    placeholder="Agenda, objectives, or notes for the trainer."
                  />
                </Field>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
                  <Button type="button" variant="outline" onClick={() => setStep(4)}>
                    Back
                  </Button>
                  <Button type="submit" disabled={submitting}>
                    {submitting ? "Finalizing..." : "Create Session"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Linked Resources Summary panel */}
          <div className="space-y-6">
            <Card className="border-border/60">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold">Linked Resources</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                {/* Presentation summary */}
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground uppercase font-bold">Selected Presentation</span>
                  <div className="p-3 border border-border/60 bg-muted/10 rounded-xl flex items-center gap-2.5">
                    <BookOpen className="h-4 w-4 text-primary shrink-0" />
                    <div className="truncate">
                      <p className="font-semibold text-xs truncate">
                        {presentations.find(p => p.id === selectedPresId)?.name || "Presentation"}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {presentations.find(p => p.id === selectedPresId)?.original_filename}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Employee list summary */}
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground uppercase font-bold">Selected Employee List</span>
                  <div className="p-3 border border-border/60 bg-muted/10 rounded-xl flex items-center gap-2.5">
                    <User className="h-4 w-4 text-primary shrink-0" />
                    <div className="truncate">
                      <p className="font-semibold text-xs truncate">
                        {employeeLists.find(e => e.id === selectedEmpId)?.name || "Employee List"}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {employeeLists.find(e => e.id === selectedEmpId)?.employee_count} Employees
                      </p>
                    </div>
                  </div>
                </div>

                {/* Script details */}
                {creationMode !== "HR" && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground uppercase font-bold">AI Narrations Script</span>
                    <div className="p-2 border border-border/40 bg-muted/5 rounded-lg flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Status</span>
                      <span className="font-semibold text-green-600 flex items-center gap-1">
                        <CheckCircle className="h-3.5 w-3.5" /> Ready
                      </span>
                    </div>
                  </div>
                )}

                {/* Questions details */}
                {creationMode !== "HR" && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground uppercase font-bold">Employee FAQ Questions</span>
                    <div className="p-2 border border-border/40 bg-muted/5 rounded-lg flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Status</span>
                      <span className="font-semibold text-green-600 flex items-center gap-1">
                        <CheckCircle className="h-3.5 w-3.5" /> Ready
                      </span>
                    </div>
                  </div>
                )}

                {/* HR Narration status */}
                {creationMode === "HR" && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground uppercase font-bold">HR Recorded Narration</span>
                    <div className="p-2 border border-border/40 bg-muted/5 rounded-lg flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Status</span>
                      <span className="font-semibold text-violet-600 flex items-center gap-1">
                        <CheckCircle className="h-3.5 w-3.5" /> Package Compiled
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  children,
  error,
  hint,
  required,
}: {
  label: string;
  children: React.ReactNode;
  error?: string;
  hint?: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label className="flex items-center gap-1 text-sm font-semibold">
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
