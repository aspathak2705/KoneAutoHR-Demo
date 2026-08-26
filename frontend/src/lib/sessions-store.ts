import { useSyncExternalStore } from "react";

export type SessionStatus =
  | "PENDING"
  | "UPLOADED"
  | "VALIDATING"
  | "PARSING"
  | "GENERATING_SCRIPT"
  | "GENERATING_AUDIO"
  | "REGISTERING_ASSETS"
  | "VERIFYING"
  | "READY"
  | "FAILED";

export interface SavedPresentation {
  id: string;
  name: string;
  original_filename: string;
  storage_path: string;
  uploaded_by?: string;
  uploaded_at: string;
  last_used: string;
  session_count: number;
  slide_count: number;
}

export interface SavedEmployeeList {
  id: string;
  name: string;
  original_filename: string;
  storage_path: string;
  uploaded_at: string;
  employee_count: number;
  last_used: string;
}

export interface PresentationScript {
  id: string;
  presentation_id: string;
  script_content: {
    welcome_flow?: any;
    slide_narrations?: Record<string, any>;
    closing_script?: any;
    opening?: any;
    slides?: any[];
    closing?: any;
  };
  generated_at: string;
  llm_model: string;
  editable: boolean;
  status: string;
}

export interface PresentationQuestion {
  id: string;
  presentation_id: string;
  questions_content: Array<{
    question: string;
    answer: string;
    confidence?: number;
    references?: number[];
  }>;
  generated_at: string;
  editable: boolean;
  status: string;
}

export interface InductionSession {
  id: string;
  title: string;
  department: string;
  trainer: string;
  date: string; // ISO date
  description?: string;
  status: SessionStatus;
  presentationFile?: string | null;
  employeesFile?: string | null;
  meetingLink?: string;
  createdAt: string;
  presentation_id?: string | null;
  employee_list_id?: string | null;
  presentation?: SavedPresentation | null;
  employee_list?: SavedEmployeeList | null;
  creation_mode?: "AI" | "HR" | null;
}

export const STATUS_LABEL: Record<SessionStatus, string> = {
  PENDING: "Pending",
  UPLOADED: "Uploaded",
  VALIDATING: "Validating assets...",
  PARSING: "Parsing deck...",
  GENERATING_SCRIPT: "Generating AI script...",
  GENERATING_AUDIO: "Generating speech audio...",
  REGISTERING_ASSETS: "Registering assets...",
  VERIFYING: "Verifying package integrity...",
  READY: "Ready for launch",
  FAILED: "Failed",
};

const STORAGE_KEY = "autohr.sessions.v1";
const listeners = new Set<() => void>();
let cachedSessions: InductionSession[] | null = null;

function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (+c ^ (Math.random() * 16 >> +c / 4)).toString(16)
  );
}

function readStorage(): InductionSession[] {
  if (typeof window === "undefined") return [];
  if (cachedSessions !== null) return cachedSessions;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      cachedSessions = [];
      return cachedSessions;
    }
    const parsed = JSON.parse(raw) as InductionSession[];
    if (!Array.isArray(parsed)) {
      cachedSessions = [];
      return cachedSessions;
    }
    cachedSessions = parsed;
    return cachedSessions;
  } catch {
    cachedSessions = [];
    return cachedSessions;
  }
}

function writeStorage(next: InductionSession[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  cachedSessions = next;
  listeners.forEach((l) => l());
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key === STORAGE_KEY) {
      cachedSessions = null;
      listeners.forEach((l) => l());
    }
  });
}

function seed(): InductionSession[] {
  const now = new Date();
  const iso = (offsetDays: number) =>
    new Date(now.getTime() + offsetDays * 86400000).toISOString().slice(0, 10);
  const initial: InductionSession[] = [
    {
      id: generateUUID(),
      title: "New Hire Orientation — Engineering",
      department: "Engineering",
      trainer: "Anna Virtanen",
      date: iso(3),
      status: "READY",
      presentationFile: "engineering-orientation.pptx",
      employeesFile: "engineering-batch-jan.xlsx",
      meetingLink: "https://teams.microsoft.com/l/meetup-join/abc",
      description: "Standard onboarding for new engineering hires.",
      createdAt: new Date(now.getTime() - 2 * 86400000).toISOString(),
    },
    {
      id: generateUUID(),
      title: "Safety & Compliance Induction",
      department: "Operations",
      trainer: "Mikael Koskinen",
      date: iso(1),
      status: "COMPLETED",
      presentationFile: "safety-first.pptx",
      employeesFile: "operations-staff-list.xlsx",
      meetingLink: "https://teams.microsoft.com/l/meetup-join/xyz",
      description: "Mandatory safety walkthrough for all field operations staff.",
      createdAt: new Date(now.getTime() - 5 * 86400000).toISOString(),
    },
  ];
  return initial;
}

const API = import.meta.env.VITE_API_BASE_URL;
if (!API) {
  throw new Error("CRITICAL: VITE_API_BASE_URL environment variable is missing.");
}
export const BACKEND_BASE = (API as string).replace(/\/$/, "") + "/api/v1";

export async function apiFetch(path: string, options?: RequestInit) {
  const url = `${BACKEND_BASE}${path}`;
  const headers = new Headers(options?.headers || {});
  headers.set("Authorization", "Bearer autohr_master_secret_token_2026");
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    let message = errorText || `HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      message = parsed.detail || message;
    } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

let isFetching = false;

export async function syncFromBackend() {
  if (isFetching) return;
  isFetching = true;
  try {
    const backendSessions = await apiFetch("/sessions");
    const nextSessions: InductionSession[] = [];

    for (const s of backendSessions) {
      try {
        const localMeta = JSON.parse(window.localStorage.getItem(`meta_${s.id}`) || "{}");
        const detail = await apiFetch(`/sessions/${s.id}`);
        const uploads = detail.uploads || [];
        const jobs = detail.presentation_jobs || [];

        let status: SessionStatus = s.status as SessionStatus;

        const jobTypes = ["validation", "parsing", "script", "audio", "package", "verification"];
        jobTypes.forEach((t) => {
          const job = jobs.find((j: any) => j.job_type.toLowerCase() === t);
          if (job) {
            const progress = Math.round(job.progress * 100);
            window.localStorage.setItem(`progress_${t}_${s.id}`, JSON.stringify({ progress, status: job.status, error: job.error_message }));
          } else {
            window.localStorage.removeItem(`progress_${t}_${s.id}`);
          }
        });

        if (status === "READY") {
          try {
            const preview = await apiFetch(`/induction/${s.id}/preview`);
            window.localStorage.setItem(`package_${s.id}`, JSON.stringify(preview));
          } catch (err) {
            console.error(`Failed to fetch preview for session ${s.id}:`, err);
          }
        }

        const presFile = detail.presentation ? detail.presentation.original_filename : (uploads.find((u: any) => u.upload_type === "PRESENTATION")?.original_filename || null);
        const empFile = detail.employee_list ? detail.employee_list.original_filename : (uploads.find((u: any) => u.upload_type === "EMPLOYEE_LIST")?.original_filename || null);

        nextSessions.push({
          id: s.id,
          title: s.name,
          date: s.scheduled_at ? s.scheduled_at.slice(0, 10) : "",
          status: status,
          presentationFile: presFile,
          employeesFile: empFile,
          department: localMeta.department || "General",
          trainer: localMeta.trainer || "HR Trainer",
          description: localMeta.description || "",
          createdAt: s.created_at || new Date().toISOString(),
          presentation_id: detail.presentation_id,
          employee_list_id: detail.employee_list_id,
          presentation: detail.presentation,
          employee_list: detail.employee_list,
          creation_mode: s.creation_mode || "AI",
        });
      } catch (err) {
        console.error(`Failed to fetch details for session ${s.id}:`, err);
      }
    }

    cachedSessions = nextSessions;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSessions));
    listeners.forEach((l) => l());
  } catch (err) {
    console.error("Failed to sync sessions from backend:", err);
  } finally {
    isFetching = false;
  }
}

function getSnapshot(): InductionSession[] {
  return readStorage();
}
const serverSnapshot: InductionSession[] = [];

function subscribe(cb: () => void) {
  listeners.add(cb);
  syncFromBackend();
  return () => listeners.delete(cb);
}

export function useSessions(): InductionSession[] {
  return useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);
}

export function useSession(id: string | undefined): InductionSession | undefined {
  const all = useSessions();
  return all.find((s) => s.id === id);
}

export async function createSession(
  input: Omit<InductionSession, "id" | "status" | "createdAt" | "presentationFile" | "employeesFile">,
): Promise<InductionSession> {
  const created = await apiFetch("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.title,
      scheduled_at: input.date ? new Date(input.date).toISOString() : null,
      presentation_id: (input as any).presentation_id || null,
      employee_list_id: (input as any).employee_list_id || null,
      creation_mode: (input as any).creation_mode || "AI"
    }),
  });

  const id = created.id;

  const localMeta = {
    department: input.department,
    trainer: input.trainer,
    description: input.description || "",
  };
  window.localStorage.setItem(`meta_${id}`, JSON.stringify(localMeta));

  const newSession: InductionSession = {
    id: id,
    title: created.name,
    date: created.scheduled_at ? created.scheduled_at.slice(0, 10) : "",
    status: created.status,
    presentationFile: null,
    employeesFile: null,
    department: localMeta.department,
    trainer: localMeta.trainer,
    description: localMeta.description,
    createdAt: created.created_at || new Date().toISOString(),
    presentation_id: (input as any).presentation_id || null,
    employee_list_id: (input as any).employee_list_id || null,
    creation_mode: created.creation_mode || "AI",
  };

  const all = readStorage();
  writeStorage([newSession, ...all]);

  syncFromBackend();
  return newSession;
}

export async function updateSession(id: string, patch: Partial<InductionSession>) {
  const existingMeta = JSON.parse(window.localStorage.getItem(`meta_${id}`) || "{}");
  const nextMeta = {
    department: patch.department !== undefined ? patch.department : existingMeta.department,
    trainer: patch.trainer !== undefined ? patch.trainer : existingMeta.trainer,
    description: patch.description !== undefined ? patch.description : existingMeta.description,
  };
  window.localStorage.setItem(`meta_${id}`, JSON.stringify(nextMeta));

  let backendStatus = undefined;
  if (patch.status) {
    if (patch.status === "CREATED") backendStatus = "PENDING";
    else if (patch.status === "READY") backendStatus = "READY";
    else if (patch.status === "COMPLETED") backendStatus = "COMPLETED";
    else if (patch.status === "FAILED") backendStatus = "FAILED";
  }

  if (patch.title !== undefined || patch.date !== undefined || backendStatus !== undefined) {
    await apiFetch(`/sessions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: patch.title,
        scheduled_at: patch.date ? new Date(patch.date).toISOString() : undefined,
        status: backendStatus,
      }),
    });
  }

  if (cachedSessions) {
    cachedSessions = cachedSessions.map((s) => (s.id === id ? { ...s, ...patch } : s));
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cachedSessions));
    listeners.forEach((l) => l());
  }

  await syncFromBackend();
}

export async function deleteSession(id: string) {
  await apiFetch(`/sessions/${id}`, {
    method: "DELETE",
  });

  window.localStorage.removeItem(`meta_${id}`);
  window.localStorage.removeItem(`package_${id}`);
  window.localStorage.removeItem(`progress_${id}`);

  await syncFromBackend();
}

/* ---------- Derived / mock induction content (Phase 1 demo) ---------- */

export interface EmployeeRow {
  id?: string;
  name: string;
  email?: string;
  department: string;
  role: string;
}

export interface ScriptStep {
  kind: "welcome" | "agenda" | "slide" | "closing";
  title: string;
  narration: string;
}

export interface FAQ {
  q: string;
  a: string;
}

export interface InductionContent {
  slides: number;
  videos: number;
  employees: EmployeeRow[];
  departments: string[];
  estimatedMinutes: number;
  progress: number;
  progressLabel: string;
  script: ScriptStep[];
  faqs: FAQ[];
}



/**
 * Deterministic mock content derived from the session id so numbers stay
 * stable between renders. Replaced by real backend data in Phase 2.
 */
export function getInductionContent(session: InductionSession): InductionContent {
  const hasPres = !!session.presentationFile;
  const hasEmp = !!session.employeesFile;

  // Try to load cached package from backend (v1.9)
  if (typeof window !== "undefined") {
    const rawPkg = window.localStorage.getItem(`package_${session.id}`);
    const rawProgress = window.localStorage.getItem(`progress_${session.id}`);

    if (rawPkg) {
      try {
        const pkg = JSON.parse(rawPkg);

        // Map backend package fields
        const employees: EmployeeRow[] = (pkg.employee_profiles || []).map((e: any, idx: number) => ({
          id: e.id || e.employee_id || String(idx + 1),
          name: e.name,
          email: e.email,
          department: e.department,
          role: e.designation || e.role,
        }));

        const departments = Array.from(new Set(employees.map((e) => e.department)));
        const slides = (pkg.slide_knowledge || []).length;
        const videos = (pkg.slide_knowledge || []).reduce((acc: number, s: any) => acc + (s.videos || []).length, 0);
        const estimatedMinutes = pkg.session_metadata?.meeting_duration || Math.max(15, Math.round(slides * 0.8 + videos * 3));

        const script: ScriptStep[] = [];
        if (pkg.welcome_flow) {
          script.push({
            kind: "welcome",
            title: "Welcome",
            narration: pkg.welcome_flow.greeting,
          });
          script.push({
            kind: "agenda",
            title: "Agenda",
            narration: `Today's agenda covers: ${pkg.welcome_flow.agenda.join(", ")}. ${pkg.welcome_flow.ice_breaker}`,
          });
        }

        if (pkg.slide_narrations && pkg.slide_knowledge) {
          pkg.slide_knowledge.forEach((sk: any) => {
            const sn = pkg.slide_narrations[String(sk.slide_number)] || pkg.slide_narrations[sk.slide_number];
            if (sn) {
              script.push({
                kind: "slide",
                title: `Slide ${sk.slide_number} — ${sk.title}`,
                narration: sn.narration,
              });
            }
          });
        }

        if (pkg.closing_script) {
          script.push({
            kind: "closing",
            title: "Closing",
            narration: `${pkg.closing_script.summary} ${pkg.closing_script.congratulations} ${pkg.closing_script.next_steps}`,
          });
        }

        const faqs: FAQ[] = (pkg.faq || []).map((f: any) => ({
          q: f.question,
          a: f.answer,
        }));

        return {
          slides,
          videos,
          employees,
          departments,
          estimatedMinutes,
          progress: 100,
          progressLabel: "Presentation ready",
          script,
          faqs,
        };
      } catch (err) {
        console.error("Failed to parse cached package:", err);
      }
    }

    if (rawProgress) {
      try {
        const prog = JSON.parse(rawProgress);
        return {
          slides: 0,
          videos: 0,
          employees: [],
          departments: [],
          estimatedMinutes: 0,
          progress: prog.progress,
          progressLabel: prog.progressLabel,
          script: [],
          faqs: [],
        };
      } catch {}
    }
  }

  // Return empty data instead of mock placeholders (v2.0)
  const employees: EmployeeRow[] = [];
  const departments: string[] = [];
  const slides = 0;
  const videos = 0;
  const estimatedMinutes = 0;

  let progress = 0;
  let progressLabel = "Waiting for documents";
  if (hasPres && !hasEmp) {
    progress = 30;
    progressLabel = "Preparing presentation…";
  } else if (!hasPres && hasEmp) {
    progress = 20;
    progressLabel = "Waiting for presentation";
  } else if (hasPres && hasEmp) {
    if (session.status === "COMPLETED") {
      progress = 100;
      progressLabel = "Induction completed";
    } else if (session.status === "READY") {
      progress = 100;
      progressLabel = "Presentation ready";
    } else {
      progress = 78;
      progressLabel = "Preparing AI induction…";
    }
  }

  const script: ScriptStep[] = [];
  const faqs: FAQ[] = [];

  return {
    slides,
    videos,
    employees,
    departments,
    estimatedMinutes,
    progress,
    progressLabel,
    script,
    faqs,
  };
}

export interface PrepStep {
  label: string;
  done: boolean;
}

export function getPreparationSteps(session: InductionSession): PrepStep[] {
  const hasPres = !!session.presentationFile;
  const hasEmp = !!session.employeesFile;
  const ready = session.status === "READY" || session.status === "COMPLETED";
  const validating = session.status === "VALIDATING";
  const parsing = session.status === "PARSING";
  const genScript = session.status === "GENERATING_SCRIPT";
  const genAudio = session.status === "GENERATING_AUDIO" || session.status === "REGISTERING_ASSETS" || session.status === "VERIFYING";

  if (session.creation_mode === "HR") {
    return [
      { label: "Assets Uploaded", done: hasPres && hasEmp },
      { label: "Pipeline Validation", done: ready || parsing || validating },
      { label: "Presentation Parsed (Slides)", done: ready || parsing },
      { label: "HR Recorded Slide Narrations Uploaded", done: ready },
      { label: "Narration Audio Validated", done: ready },
      { label: "HR Presentation Package Compiled", done: ready },
    ];
  }

  return [
    { label: "Assets Uploaded", done: hasPres && hasEmp },
    { label: "Pipeline Validation", done: ready || genScript || genAudio || parsing || validating },
    { label: "Presentation Parsed (Slides, Notes, Media)", done: ready || genScript || genAudio || parsing },
    { label: "AI Script Generated", done: ready || genAudio },
    { label: "TTS Speech Pre-Generated", done: ready },
    { label: "Integrity Verified (Ready to Launch)", done: ready },
  ];
}

export async function getPresentations(): Promise<SavedPresentation[]> {
  return (await apiFetch("/presentations")) as SavedPresentation[];
}

export async function getEmployeeLists(): Promise<SavedEmployeeList[]> {
  return (await apiFetch("/employee-lists")) as SavedEmployeeList[];
}

export async function deletePresentation(id: string): Promise<void> {
  await apiFetch(`/presentations/${id}`, { method: "DELETE" });
}

export async function deleteEmployeeList(id: string): Promise<void> {
  await apiFetch(`/employee-lists/${id}`, { method: "DELETE" });
}

export async function getPresentationAssetsStatus(id: string, mode: string = "AI"): Promise<any> {
  return await apiFetch(`/presentations/${id}/assets-status?mode=${mode}`);
}

export async function getPresentationScript(presentationId: string): Promise<PresentationScript | null> {
  try {
    return (await apiFetch(`/presentation-script/${presentationId}`)) as PresentationScript;
  } catch {
    return null;
  }
}

export async function updatePresentationScript(id: string, scriptContent: any): Promise<PresentationScript> {
  return (await apiFetch(`/presentation-script/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_content: scriptContent }),
  })) as PresentationScript;
}

export async function regeneratePresentationScript(presentationId: string, employeeListId: string): Promise<PresentationScript> {
  return (await apiFetch(`/presentation-script/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presentation_id: presentationId, employee_list_id: employeeListId }),
  })) as PresentationScript;
}

export async function getPresentationQuestions(presentationId: string): Promise<PresentationQuestion | null> {
  try {
    return (await apiFetch(`/presentation-questions/${presentationId}`)) as PresentationQuestion;
  } catch {
    return null;
  }
}

export async function updatePresentationQuestions(id: string, questionsContent: any[]): Promise<PresentationQuestion> {
  return (await apiFetch(`/presentation-questions/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ questions_content: questionsContent }),
  })) as PresentationQuestion;
}

export async function regeneratePresentationQuestions(presentationId: string, employeeListId: string): Promise<PresentationQuestion> {
  return (await apiFetch(`/presentation-questions/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presentation_id: presentationId, employee_list_id: employeeListId }),
  })) as PresentationQuestion;
}

export async function uploadPresentation(name: string, file: File): Promise<SavedPresentation> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("file", file);

  const res = await fetch(`${BACKEND_BASE}/presentations`, {
    method: "POST",
    headers: {
      "Authorization": "Bearer autohr_master_secret_token_2026"
    },
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Upload failed with status ${res.status}`);
  }
  return (await res.json()) as SavedPresentation;
}

export async function uploadEmployeeList(name: string, file: File): Promise<SavedEmployeeList> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("file", file);

  const res = await fetch(`${BACKEND_BASE}/employee-lists`, {
    method: "POST",
    headers: {
      "Authorization": "Bearer autohr_master_secret_token_2026"
    },
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Upload failed with status ${res.status}`);
  }
  return (await res.json()) as SavedEmployeeList;
}

export interface OrganizationConfig {
  id?: string;
  company_name: string;
  company_domain: string;
  ai_officer_name: string;
  ai_trainer_name: string;
  ai_role_description: string;
  vocal_tone: string;
  communication_style: string;
  created_at?: string;
  updated_at?: string;
}

export interface AgentConfiguration {
  id: string;
  provider: string;
  email: string | null;
  tenant: string | null;
  profile_path: string | null;
  is_connected: boolean;
  created_at: string;
  updated_at: string;
}

export async function getAgentConfig(): Promise<AgentConfiguration> {
  return (await apiFetch("/agent/config")) as AgentConfiguration;
}

export async function updateAgentConfig(config: Partial<AgentConfiguration>): Promise<AgentConfiguration> {
  return (await apiFetch("/agent/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })) as AgentConfiguration;
}

export async function connectAgentMicrosoft(): Promise<AgentConfiguration> {
  return (await apiFetch("/agent/connect", {
    method: "POST"
  })) as AgentConfiguration;
}

export async function disconnectAgentMicrosoft(): Promise<AgentConfiguration> {
  return (await apiFetch("/agent/disconnect", {
    method: "POST"
  })) as AgentConfiguration;
}

export async function getConfiguration(): Promise<OrganizationConfig> {
  return (await apiFetch("/configuration")) as OrganizationConfig;
}

export async function saveConfiguration(config: OrganizationConfig): Promise<OrganizationConfig> {
  return (await apiFetch("/configuration", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })) as OrganizationConfig;
}



export async function getAnalyticsDashboard(): Promise<any> {
  return await apiFetch("/analytics/dashboard");
}

export async function getAnalyticsRuns(): Promise<any[]> {
  return (await apiFetch("/analytics/runs")) as any[];
}

export interface MeetingDetails {
  id: string;
  session_id: string;
  teams_meeting_url: string;
  meeting_passcode?: string | null;
  organizer_name: string;
  meeting_date: string;
  meeting_time: string;
  meeting_status: string;
  created_at: string;
}

export interface InvitationDraft {
  id: string;
  session_id: string;
  recipient_name: string;
  recipient_email: string;
  subject: string;
  body: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ReadinessStatus {
  session_id: string;
  has_presentation: boolean;
  has_employees: boolean;
  has_script: boolean;
  has_faq: boolean;
  has_meeting: boolean;
  is_ready: boolean;
}

export async function getMeetingForSession(sessionId: string): Promise<MeetingDetails | null> {
  try {
    const res: any = await apiFetch(`/meetings/session/${sessionId}`);
    if (!res || res.configured === false) {
      return null;
    }
    return res as MeetingDetails;
  } catch {
    return null;
  }
}

export async function saveMeeting(meeting: {
  session_id: string;
  teams_meeting_url: string;
  meeting_passcode?: string | null;
  organizer_name: string;
  meeting_date: string;
  meeting_time: string;
}): Promise<MeetingDetails> {
  return (await apiFetch(`/meetings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(meeting),
  })) as MeetingDetails;
}

export async function generateInvitationDrafts(sessionId: string, employeeIds?: string[]): Promise<InvitationDraft[]> {
  return (await apiFetch(`/meetings/session/${sessionId}/generate-drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_ids: employeeIds || null })
  })) as InvitationDraft[];
}

export async function getInvitationDrafts(sessionId: string): Promise<InvitationDraft[]> {
  try {
    return (await apiFetch(`/meetings/session/${sessionId}/drafts`)) as InvitationDraft[];
  } catch {
    return [];
  }
}

export async function updateInvitationDraft(draftId: string, subject: string, body: string): Promise<InvitationDraft> {
  return (await apiFetch(`/meetings/drafts/${draftId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject, body }),
  })) as InvitationDraft;
}

export async function validateSessionReadiness(sessionId: string): Promise<ReadinessStatus> {
  return (await apiFetch(`/runtime/readiness/${sessionId}`)) as ReadinessStatus;
}

export interface RuntimeStatus {
  session_id: string;
  state: string;
  current_slide: number;
  last_heartbeat?: string | null;
  last_error?: string | null;
  presentation_ready: boolean;
  employees_ready: boolean;
  meeting_ready: boolean;
  ai_ready: boolean;
}

export async function startMeetingRuntime(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/start`, { method: "POST" });
}

export async function stopMeetingRuntime(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/stop`, { method: "POST" });
}

export async function advanceMeetingSlide(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/next`, { method: "POST" });
}

export async function backtrackMeetingSlide(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/prev`, { method: "POST" });
}

export async function getMeetingRuntimeStatus(sessionId: string): Promise<RuntimeStatus> {
  return (await apiFetch(`/runtime/${sessionId}`)) as RuntimeStatus;
}

export async function askQuestion(sessionId: string, speakerName: string, questionText: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ speaker_name: speakerName, question_text: questionText }),
  });
}

export async function getConversationHistory(sessionId: string): Promise<any[]> {
  try {
    return (await apiFetch(`/runtime/${sessionId}/conversation`)) as any[];
  } catch {
    return [];
  }
}

export async function prepareMeetingRuntime(id: string) {
  return apiFetch(`/runtime/${id}/prepare`, {
    method: "POST",
  });
}

export async function startInductionRuntime(id: string) {
  return apiFetch(`/runtime/${id}/start-induction`, {
    method: "POST",
  });
}

export async function joinPreparedMeeting(id: string) {
  return apiFetch(`/runtime/${id}/join-meeting`, {
    method: "POST",
  });
}

export async function startRuntimeSpeech(sessionId: string, narration: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ narration_text: narration }),
  });
}

export async function stopRuntimeSpeech(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/stop-speaking`, { method: "POST" });
}

export async function getAttendanceReport(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/attendance`);
}

export async function getTranscriptData(sessionId: string): Promise<any[]> {
  try {
    return (await apiFetch(`/runtime/${sessionId}/transcript-data`)) as any[];
  } catch {
    return [];
  }
}

export async function simulateReconnect(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/reconnect`, { method: "POST" });
}

export async function triggerScriptGeneration(sessionId: string): Promise<any> {
  return await apiFetch(`/sessions/${sessionId}/generate-script`, { method: "POST" });
}

export async function triggerAudioGeneration(sessionId: string): Promise<any> {
  return await apiFetch(`/sessions/${sessionId}/generate-audio`, { method: "POST" });
}

export async function triggerPackageGeneration(sessionId: string): Promise<any> {
  return await apiFetch(`/sessions/${sessionId}/generate-package`, { method: "POST" });
}

export async function getSessionJobs(sessionId: string): Promise<any[]> {
  return await apiFetch(`/sessions/${sessionId}/jobs`);
}

export async function getRuntimeSummary(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/summary`);
}

export async function getRuntimeAudioList(sessionId: string): Promise<string[]> {
  return (await apiFetch(`/runtime/${sessionId}/audio`)) as string[];
}

export async function playRuntimeAudioTrack(sessionId: string, track: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/audio/play`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track }),
  });
}

export async function stopRuntimeAudioTrack(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/audio/stop`, {
    method: "POST"
  });
}

export async function pauseInductionSession(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/presentation/pause`, {
    method: "POST"
  });
}

export async function resumeInductionSession(sessionId: string): Promise<any> {
  return await apiFetch(`/runtime/${sessionId}/presentation/resume`, {
    method: "POST"
  });
}
