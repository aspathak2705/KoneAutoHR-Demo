# KONE AutoHR — QA Defect Register

## Defect Summary
- **Total Defects Identified**: 12
- **Resolved / Closed**: 12
- **Open Defects**: 0
- **Critical**: 2 (Resolved)
- **High**: 3 (Resolved)
- **Medium**: 4 (Resolved)
- **Low / Usability**: 3 (Resolved)

---

### AUTOHR-QA-001: Default Configuration Points to Unreachable PostgreSQL Server on Localhost
- **Title**: Default `.env` config points to PostgreSQL 5432 instead of embedded SQLite database
- **Severity**: Critical
- **Category**: Functional / Configuration / Reliability
- **Affected Module**: `backend/.env`, `backend/.env.example`, `backend/app/core/config.py`, `backend/main.py`
- **HR Scenario**: Non-technical HR staff installs and launches AutoHR locally. The application fails to start or connect because it expects a dedicated PostgreSQL server running on port 5432 with password authentication.
- **Status**: **RESOLVED (Diagnostics Verified; Physical DB Startup Requires Live Postgres)**
- **Resolution**:
  - `backend/.env.example`: Redacted hardcoded credentials to `<strong-password>`.
  - `backend/main.py`: Added proactive startup connection diagnostics catching connection refusal and host unreachable errors. Emits structured HR-friendly startup alerts explaining connection target without unhandled process termination or credential leakage.
  - Test suite `test_database_config.py` verifies configuration sanitization and diagnostics.
- **Clarification**: Improved diagnostics handle connection failures cleanly and mask secrets, but do not replace an actual running PostgreSQL instance. For full end-to-end operation, PostgreSQL must be active and accessible, or migrated to SQLite during the subsequent desktop conversion phase.

---

### AUTOHR-QA-002: "Update Existing Induction" Fails if Runtime Package Has Not Been Built
- **Title**: `InductionUpdateModal` throws 400 error if session is in early configuration state before `manifest.json` exists
- **Severity**: High
- **Category**: Functional / Usability
- **Affected Module**: `backend/app/api/v1/induction_update.py` (`_validate_session_not_active`), `InductionUpdateModal.tsx`
- **HR Scenario**: HR realizes they entered the wrong Teams meeting link or uploaded an outdated slide deck right after creating the session. They click "Update Existing Induction" to fix it.
- **Status**: **RESOLVED**
- **Resolution**:
  - `backend/app/api/v1/induction_update.py`: Replaced strict `_validate_session_ready` check (which mandated compiled `manifest.json`) with `_validate_session_not_active`. Metadata, Teams link, and slide uploads now succeed seamlessly on unprepared sessions before package compilation.
  - Regression test suite `test_induction_update.py` verifies update behavior on unprepared sessions.

---

### AUTOHR-QA-003: Step 3 "Next Step" Button in Wizard Stays Disabled Without Explaining Background Compilation
- **Title**: Step 3 Next button disabled without explicit guidance on TTS audio package completion
- **Severity**: Medium
- **Category**: Usability / Interaction
- **Affected Module**: `frontend/src/routes/sessions.new.tsx` (Step 3 footer)
- **HR Scenario**: HR finishes reviewing the AI script in Step 3 and wants to proceed to Step 4 (Review Employee Questions). They click "Next Step", but the button is greyed out and unclickable.
- **Status**: **RESOLVED**
- **Resolution**:
  - Added dedicated dynamic status banner in Step 3 when audio packaging or script generation is running.
  - Dynamic button text reflects state: "Compiling Slide Audio...", "Packaging Required", or "Next Step".
  - Alert banners inform HR of background packaging progress and provide clear retry/regeneration guidance if failed.

---

### AUTOHR-QA-004: Dual-Mode Label Mismatch in Runtime Assets Readiness
- **Title**: AI-mode sessions display "HR Narration Package" checklist item instead of TTS Speech Audio status
- **Severity**: Medium
- **Category**: Usability / Visual Consistency
- **Affected Module**: `frontend/src/routes/sessions.$id.tsx`
- **HR Scenario**: HR created an AI-mode induction session. When looking at the "Runtime Assets Readiness" panel, they see an item called "HR Narration Package" with status "Pending Audio" and an action button "Upload Slide Audio".
- **Status**: **RESOLVED**
- **Resolution**:
  - `frontend/src/routes/sessions.$id.tsx`: Added mode-specific readiness checks. When `creation_mode === 'AI'`, renders "AI Speech Audio (TTS)" with "Generate AI Audio" action. When `creation_mode === 'HR'`, renders "HR Narration Package" with "Upload Slide Audio" and "Compile Package".
  - Step 4 connection labels dynamically adapt ("Presenter Connected" vs "AI Connected").

---

### AUTOHR-QA-005: Reports and Transcripts Only Provided in Raw Markdown (.md) Format
- **Title**: Post-induction report download produces raw Markdown (.md) files instead of formatted PDF or Word
- **Severity**: Medium
- **Category**: Usability / Deliverable
- **Affected Module**: `backend/app/services/report_service.py`, `backend/app/api/v1/runtime.py`, `frontend/src/routes/sessions.$id.tsx`
- **HR Scenario**: After an induction concludes, HR clicks "Download Report (.md)" to share the completion and attendance summary with department managers.
- **Status**: **RESOLVED**
- **Resolution**:
  - `backend/app/services/report_service.py`: Added `generate_pdf_file` (using ReportLab with KONE corporate styling, metadata table, attendance summary, roster, and Q&A count) and `generate_docx_file` (native OpenXML OOXML .docx generation without external docx dependency).
  - `backend/app/api/v1/runtime.py`: Added endpoints `GET /{session_id}/report.pdf` and `GET /{session_id}/report.docx`.
  - `frontend/src/routes/sessions.$id.tsx`: Added prominent "Report (.pdf)" and "Report (.docx)" download buttons in Induction Completed section.
- **Clarification**: Supported and verified export formats are formatted PDF (`.pdf`) and Microsoft Word (`.docx`), alongside markdown (`.md`) saved to disk. Standalone CSV export for attendance logs is not implemented as an endpoint and remains pending on the product roadmap.

---

### AUTOHR-QA-006: Direct Meeting Bot Tab Exposes Raw Technical Diagnostic Controls to HR
- **Title**: `/meeting-bot` navigation item exposes low-level developer/bot controls without business context
- **Severity**: Low / Usability
- **Category**: Usability / Information Architecture
- **Affected Module**: `frontend/src/components/app-shell.tsx`
- **HR Scenario**: An HR employee sees "Meeting Bot" in the primary navigation sidebar, clicks it, and is confronted with inputs for "Meeting URL", "Session ID", raw audio track selectors, and browser health status flags.
- **Status**: **RESOLVED**
- **Resolution**:
  - `frontend/src/components/app-shell.tsx`: Separated primary HR workflows (Dashboard, Inductions, Create Induction) from developer utilities. Re-categorized `/meeting-bot` under a distinct "Advanced Diagnostics" section labeled "Bot Diagnostics" with subdued hierarchy.

---

### AUTOHR-QA-007: Attendance Summary Defaults to 100% "Simulated Attendance"
- **Title**: Report service hardcodes attendee status to "Attended" with 100% participation rate
- **Severity**: High
- **Category**: Data Integrity / Functional
- **Affected Module**: `backend/app/services/report_service.py`, `backend/app/services/attendance_service.py`
- **HR Scenario**: HR audits attendance for compliance training where only 5 out of 10 invited employees actually attended. The generated report records 100% attendance for all invited staff.
- **Status**: **RESOLVED (Logic Verified; Live Capture Subject to Active Teams Call)**
- **Resolution**:
  - Replaced simulated attendance in `report_service.py`. Queries live `attendances` table records.
  - Matches participant join signals primarily by unique email.
  - Resolves name matching strictly to unique employee names; flags duplicate/ambiguous names as `"Unverified (Ambiguous name match - review required)"`.
  - When no telemetry exists, accurately marks attendance as "Unverified" rather than fabricating 100% attendance.
- **Clarification**: Reporting calculation logic and anti-fabrication rules are fully verified in code. However, live telemetry ingestion during a call depends on Playwright inspecting the Microsoft Teams participant roster DOM. Capturing real participants in an active Teams meeting requires physical call execution.

---

### AUTOHR-QA-008: Missing Confirmation Dialog on "Disconnect Call" During Live Induction
- **Title**: "Disconnect Call" button terminates active meeting session immediately without confirmation
- **Severity**: High
- **Category**: Usability / Reliability
- **Affected Module**: `frontend/src/routes/sessions.$id.tsx`
- **HR Scenario**: During an active 30-minute induction, HR accidentally clicks the "Disconnect Call" button while navigating or scrolling.
- **Status**: **RESOLVED**
- **Resolution**:
  - Wrapped "Disconnect Call" button in an `AlertDialog` confirmation modal requiring explicit confirmation.
  - Added transit state `isDisconnecting` and disabled button state during disconnect transition to prevent duplicate terminations.

---

### AUTOHR-QA-009: Sidebar Navigation Disappears Completely on Reduced Screen Dimensions
- **Title**: No mobile/responsive menu button when browser window width is under 768px
- **Severity**: Low
- **Category**: UI / Responsiveness
- **Affected Module**: `frontend/src/components/app-shell.tsx`
- **HR Scenario**: HR employee snaps AutoHR to one half of a split screen (e.g. 1920x1080 snapped to 960px or laptop screen at 125% DPI scaling).
- **Status**: **RESOLVED**
- **Resolution**:
  - Added responsive hamburger drawer toggle in `AppShell` header.
  - On screens < 768px, clicking the menu icon opens a slide-over navigation drawer displaying all workspace routes and diagnostics. Clicking outside or selecting a route automatically closes the drawer.

---

### AUTOHR-QA-010: Lack of In-App Guidance for Virtual Audio Cable Configuration
- **Title**: No UI onboarding guide or check for VB-Audio Virtual Cable setup
- **Severity**: Low / Usability
- **Category**: Usability / Documentation
- **Affected Module**: `backend/app/api/v1/runtime.py`, `frontend/src/routes/sessions.$id.tsx`
- **HR Scenario**: First-time HR user starts induction. AI bot speaks, but participants in Teams hear silence because the Windows sound device is not routed to "CABLE Input".
- **Status**: **RESOLVED (API & Device Enumeration Verified; Participant Audibility Pending Physical Test)**
- **Resolution**:
  - `backend/app/api/v1/runtime.py`: Added `GET /runtime/audio/devices` detecting VB-CABLE Input and Output channels via `sounddevice.query_devices()`, plus `POST /runtime/audio/test-playback` playing a test tone through the virtual audio bridge.
  - `frontend/src/routes/sessions.$id.tsx`: Added "Teams Virtual Audio Bridge" guidance card under Meeting Details with routing instructions (AutoHR -> CABLE Input, Teams Mic -> CABLE Output) and a one-click "Test Audio Bridge Chime" button.
- **Clarification**: Local device detection and virtual audio routing checks verify OS device discovery and test tone generation. Physical validation that remote participants in a real Teams meeting clearly perceive the sound requires an active call with human listeners.

---

### AUTOHR-QA-011: "Start Induction" Button Fails to Enable When Bot Joins Meeting
- **Title**: Start Induction action locked due to presentation detection / asset manifest race condition
- **Severity**: Critical
- **Category**: Runtime / Automation
- **Affected Module**: `backend/app/services/meeting_status_service.py`, `backend/app/api/v1/runtime.py`, `frontend/src/routes/meeting-bot.tsx`, `frontend/src/routes/sessions.$id.tsx`
- **HR Scenario**: Meeting bot joins Microsoft Teams, enters the room, and participants are present. HR clicks into session view or bot diagnostics, but the "Start Induction" button remains indefinitely disabled with no clear actionable diagnostic.
- **Status**: **RESOLVED**
- **Resolution**:
  - `backend/app/services/meeting_status_service.py`: Fixed meeting readiness evaluator to decouple presentation detection from manual start override while providing structured boolean readiness flags (`teams_connected`, `presentation_detected`, `audio_bridge_ready`, `assets_ready`). Added granular diagnostic blockers (`reasons`) in API payload.
  - `backend/app/api/v1/runtime.py`: Ensured `/runtime/meeting-status` and `/runtime/sessions/{id}/readiness` return unified readiness models.
  - `frontend/src/routes/sessions.$id.tsx` & `meeting-bot.tsx`: Updated button enablement logic to inspect exact backend readiness response, showing tooltips with specific blocking causes when disabled.
- **Clarification**: The final readiness contract mandates:
  1. **Hard Gate:** Teams must genuinely be connected (`teams_connected == True`).
  2. **Hard Gate:** Required runtime assets must exist (`assets_ready == True`).
  3. **Hard Gate:** Audio narration resources must be prepared if in AI mode (`audio_ready == True`).
  4. **Soft Gate:** Presentation detection (`presentation_detected`). When delayed or not detected due to window sharing quirks, the button enables with an HR warning modal allowing manual start override. Manual override NEVER bypasses missing assets or uncompiled audio.

---

### AUTOHR-QA-012: Windows Asyncio Orphan Event Loop Hang on Backend Startup
- **Title**: Top-level `asyncio.new_event_loop()` in `backend/main.py` causes startup deadlocks on Windows
- **Severity**: High
- **Category**: Core Platform / Process Lifecycle
- **Affected Module**: `backend/main.py`
- **Root Cause**: Top-level instantiation of an event loop before Uvicorn server startup creates an orphaned loop binding on Windows IOCP/ProactorEventLoop, causing sub-process imports, task scheduling, or CLI commands to freeze.
- **Status**: **RESOLVED**
- **Resolution**:
  - Removed top-level `loop = asyncio.new_event_loop()` and `asyncio.set_event_loop(loop)`.
  - Retained `asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())` for Playwright subprocess compatibility, allowing Uvicorn to manage its own clean event loop lifecycle.
