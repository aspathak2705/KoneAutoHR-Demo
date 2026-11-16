# KONE AutoHR — Final End-to-End Workflow Acceptance Guide

**Release Candidate:** v0.1-RC  
**Target User:** HR Induction Administrators & Training Coordinators  
**Scope:** Complete Induction Lifecycle (Preparation → Pre-Flight → Live Meeting Execution → Compliance Reporting)

---

## 1. Workflow Architecture Overview

The KONE AutoHR platform provides an automated, AI-assisted employee induction system integrated with Microsoft Teams. The end-to-end workflow consists of five core operational phases:

```
[Phase 1: Setup] ──> [Phase 2: Preparation] ──> [Phase 3: Pre-Flight] ──> [Phase 4: Live Execution] ──> [Phase 5: Reporting]
- Create Session      - Extract Slides           - Audio Bridge Check      - Bot Joins Teams          - Live Attendance
- Upload PPTX         - Generate Scripts         - Voice Configuration     - Screen Detection         - Ambiguity Check
- Upload Attendees    - AI Speech Compilation    - Meeting Link Update     - Slide Narration Sync     - PDF/DOCX Reports
```

---

## 2. Step-by-Step Workflow Walkthrough

### Phase 1: Session Creation & Ingestion

#### 1.1 Navigate to Create Induction
- **UI Route:** `/sessions/new` (accessible via sidebar "Create Induction" or Dashboard primary action).
- **Form Fields:**
  - **Session Title:** e.g., "KONE New Hire Induction - November 2026 Batch".
  - **Meeting Link:** Microsoft Teams join URL (`https://teams.microsoft.com/l/meetup-join/...`).
  - **Scheduled Start Time:** Date & time picker.
  - **Presentation Deck (.pptx):** Official KONE induction slide deck.
  - **Attendee List (.xlsx / .csv):** Employee list containing `Name`, `Email`, and `Department`.

#### 1.2 Validation & Submission
- **System Safeguards:**
  - Validates Teams URL format before allowing submission.
  - Requires PPTX file presence.
  - Displays instant file parsing feedback (slide count detected, attendee rows validated).
- **Action:** Click **"Create & Prepare Session"**.
- **Result:** Session record created in database with initial status `CREATED`.

---

### Phase 2: Content Intelligence & Runtime Preparation

#### 2.1 Asset Processing Pipeline
- **Backend Service:** `PreparationOrchestrator` (`backend/app/modules/induction/services/preparation_orchestrator.py`).
- **Automated Steps:**
  1. **Slide Extraction:** Converts PPTX slides into high-resolution PNG images stored in `static/sessions/{id}/slides/`.
  2. **Manifest Generation:** Creates `manifest.json` indexing slide order, text content, bullet points, and visual fingerprints.
  3. **Script Generation:** Synthesizes structured induction narration scripts for each slide.
  4. **Q&A Indexing:** Pre-computes common candidate questions and contextual answers.

#### 2.2 Voice & Audio Configuration (Step 3)
- **UI Route:** `/sessions/$id` (Configuration Tab).
- **Narration Mode Selection:**
  - **Option A: HR Live Narration:** HR speaks during the call; bot advances slides automatically based on slide visual tracking.
  - **Option B: AI Voice Narration:** AI bot speaks through Microsoft Teams using Sarvam Bulbul V3 TTS.
- **AI Voice Controls:**
  - Select voice profile (e.g., KONE Brand Voice, Bulbul V3 Indian English).
  - Preview voice sample with responsive playback controls (`Play / Pause / Stop`).
  - Click **"Compile Audio"**.
- **Safeguards (QA-003 & QA-004):**
  - Shows clear loading spinner and status banner: *"Compiling slide audio narration with Sarvam TTS... Please wait."*
  - "Next" and "Proceed" buttons are disabled during compilation with clear tooltip explanation.
  - In HR Narration mode, labels clearly reflect *"Live HR Voice Selected - Audio Compilation Not Required"* without artificial disabled locks.

---

### Phase 3: Pre-Flight Checks & Meeting Setup

#### 3.1 Meeting Details Editing (QA-002)
- HR can modify the Microsoft Teams link, date, or time prior to bot launch directly from the Session Details card without invalidating pre-compiled presentation assets.

#### 3.2 Teams Virtual Audio Bridge Verification (QA-010)
- **Component:** "Teams Virtual Audio Bridge" guidance card.
- **Routing Setup:**
  - AutoHR Output Device ➔ `CABLE Input (VB-Audio Virtual Cable)`
  - Teams Microphone ➔ `CABLE Output (VB-Audio Virtual Cable)`
- **One-Click Diagnostic:**
  - Click **"Test Audio Bridge Chime"**.
  - AutoHR sends a 440 Hz test tone through the virtual cable. If properly routed, Teams microphone volume meter registers active signal.
  - *Note:* This test verifies device routing locally. Audible verification by human participants requires an active call.

---

### Phase 4: Live Meeting Execution

#### 4.1 Launching Meeting Bot
- **Action:** Click **"Launch Bot & Join Teams"**.
- **Backend Flow:**
  - Playwright launches persistent Microsoft Edge profile (`backend/app/services/meeting_bot_service.py`).
  - Bot navigates to Teams meeting URL, utilizes saved session credentials, configures mic/camera states to muted, and enters meeting lobby.
- **UI Transition:**
  - Session status updates from `READY` to `JOINING` ➔ `CONNECTED`.

#### 4.2 Presentation Screen Detection
- **Backend Flow:**
  - Presenter shares screen in Teams.
  - Bot monitors Microsoft Teams stage for active screen sharing (`PresentationObserver`).
  - Compares presenter screen frames against pre-extracted slide fingerprints in `manifest.json`.
- **UI Feedback:**
  - Meeting Status card displays:
    - Teams Connection: `Connected` (Green check)
    - Presentation Active: `Detected - Slide 1 (Title)` (Green check)
    - Audio Bridge: `Ready` (Green check)

#### 4.3 Starting Induction (QA-011)
- **Readiness Logic:**
  - **Hard Gate 1 (Teams Connected):** Bot must be actively inside the call.
  - **Hard Gate 2 (Assets Ready):** Slide assets and `manifest.json` must be compiled on disk.
  - **Hard Gate 3 (Audio Ready):** For AI mode, TTS speech files must exist.
  - **Soft Gate (Presentation Detected):** If screen sharing is delayed or unconfirmed by OCR, button enables with an HR warning modal allowing manual start override.
- **Action:** Click **"Start Induction"**.
- **Execution Flow:**
  - Status updates to `IN_PROGRESS`.
  - Bot plays slide 1 audio narration through VB-Cable into the Teams meeting.
  - Bot monitors presenter slide changes and automatically queues corresponding slide narration.

#### 4.4 Real-Time Attendance Telemetry (QA-007)
- During induction, the bot monitors the Teams participant roster every 15 seconds.
- Join timestamps, leave timestamps, and total active minutes are persisted to the `attendances` table.

#### 4.5 Safe Disconnect & Termination (QA-008)
- If HR needs to end the session early or when presentation finishes:
  - Click **"Disconnect Call"**.
  - Confirmation dialog prompts: *"Are you sure you want to disconnect the AutoHR bot from this meeting? Active narration will cease immediately."*
  - Upon confirmation, button locks (`isDisconnecting = true`), Playwright gracefully leaves the call, releases audio streams, and transitions status to `COMPLETED`.

---

### Phase 5: Post-Induction Reporting & Compliance

#### 5.1 Evidence-Based Attendance Summary (QA-007)
- **UI Route:** `/sessions/$id` (Report Tab) & `/analytics`.
- **Audit Verification:**
  - Real database records queried; zero fabricated 100% participation.
  - Matches attendees by corporate email address.
  - Unique name fallback: Matches unambiguous employee names.
  - Ambiguity Guard: Flags duplicate/ambiguous participant names as `"Unverified (Ambiguous name match - review required)"`.
- **Metrics Calculated:**
  - Total Invited vs Total Present.
  - Average Attention / Dwell Time (% of session attended).
  - Individual completion compliance status (`Completed`, `Partial`, `Absent`, `Unverified`).

#### 5.2 Exporting Compliance Reports (QA-005)
- **Supported Formats:**
  - **Report (.pdf):** Downloadable formatted PDF compiled via ReportLab.
  - **Report (.docx):** Downloadable Microsoft Word document compiled via OpenXML.
  - *Note:* Standalone CSV log export is pending future roadmap delivery; participant tables are fully embedded in the PDF and DOCX reports.

---

## 3. Acceptance Verification Summary

| Stage | Test Verification | Software Status | Physical Status |
| :--- | :--- | :--- | :--- |
| **Setup** | Session creation with PPTX & Excel | **PASSED** (Validated) | **PASSED** (Local file parsing) |
| **Preparation** | Asset extraction & script synthesis | **PASSED** (Validated) | **PASSED** (Local disk storage) |
| **Audio Config** | AI TTS compilation & voice sample test | **PASSED** (Validated) | **PASSED** (Sarvam Bulbul V3) |
| **Pre-Flight** | Virtual audio cable detection | **PASSED** (API check) | **PENDING** (Remote listener audibility) |
| **Join Call** | Playwright Teams join | **PASSED** (Bot lifecycle) | **PENDING** (Active Teams room admission) |
| **Start Induction** | Readiness evaluation contract | **PASSED** (Hard/soft gates) | **PENDING** (Live meeting start) |
| **Execution** | Narration playback & slide tracking | **PASSED** (Controller sync) | **PENDING** (Live call narration) |
| **Termination** | Disconnect call confirmation | **PASSED** (Modal locking) | **PENDING** (Live session end) |
| **Reporting** | PDF and DOCX export generation | **PASSED** (ReportLab & OOXML) | **PASSED** (Disk & download endpoints) |
