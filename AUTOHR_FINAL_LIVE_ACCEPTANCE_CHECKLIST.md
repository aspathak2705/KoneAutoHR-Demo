# KONE AutoHR — Final Live Induction Acceptance Checklist

**Version:** 0.1-RC (Release Candidate)  
**Target User:** HR Training Coordinator / QA Test Engineer  
**Target Environment:** Windows 10/11 Enterprise, Microsoft Edge, VB-Audio Cable  
**Purpose:** Controlled Step-by-Step Execution Checklist for One Real Microsoft Teams Induction Session

---

## 1. Pre-Flight Infrastructure & Environment Setup

| # | Item | Verification Step | Status / Sign-Off |
| :--- | :--- | :--- | :--- |
| **1.1** | **PostgreSQL Database** | Verify PostgreSQL service is active on host/port defined in `backend/.env`. | `[ ] PASS / [ ] PENDING` |
| **1.2** | **VB-Audio Virtual Cable** | Ensure "CABLE Input" and "CABLE Output" appear in Windows Sound Settings (`mmsys.cpl`). Ensure exclusive mode is unchecked. | `[ ] PASS / [ ] PENDING` |
| **1.3** | **Microsoft Teams Account** | Open Microsoft Edge using the persistent profile (`backend/app/services/meeting_bot_service.py`), log in to corporate Microsoft Teams account, and ensure session cookie is cached. | `[ ] PASS / [ ] PENDING` |
| **1.4** | **Sarvam Bulbul V3 API** | Verify valid `SARVAM_API_KEY` is present in `backend/.env` for AI narration mode. | `[ ] PASS / [ ] PENDING` |
| **1.5** | **Backend Launch** | Run: `$env:PYTHONPATH="backend"; uvicorn main:app --host 127.0.0.1 --port 8000`. Confirm clean startup without `[FATAL STARTUP ERROR]`. | `[ ] PASS / [ ] PENDING` |
| **1.6** | **Frontend Launch** | In `frontend/`, run: `pnpm run dev`. Navigate to `http://localhost:3000`. Verify Dashboard loads cleanly. | `[ ] PASS / [ ] PENDING` |

---

## 2. Session Creation & Content Preparation

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | **New Session Creation** | Navigate to `/sessions/new`. Enter Title, valid Teams Join URL, and Scheduled Time. | Form accepts input; Teams URL passes validation. | `[ ] PASS` |
| **2.2** | **File Ingestion** | Upload official KONE Induction `.pptx` and employee roster `.xlsx` / `.csv`. | Upload cards show detected slide count and attendee row count. | `[ ] PASS` |
| **2.3** | **Submit & Prepare** | Click **"Create & Prepare Session"**. | Backend executes `PreparationOrchestrator`. Session status transitions to `CREATED` ➔ `PREPARING` ➔ `READY`. | `[ ] PASS` |
| **2.4** | **Asset Manifest Validation** | Navigate to Session Overview (`/sessions/$id`). Check Slide Deck preview. | High-res slide thumbnails render in correct numerical order. `manifest.json` verified on disk. | `[ ] PASS` |
| **2.5** | **Narration Mode Selection** | In Step 3 (Configuration), select **"AI Voice Narration"** and click **"Compile Audio"**. | Progress banner displays "Compiling slide audio narration...". Next button disabled during compilation with clear tooltip (QA-003). | `[ ] PASS` |
| **2.6** | **Audio Packaging Completion** | Wait for Sarvam Bulbul V3 compilation to finish. | "Compile Audio" status shows green completed check. "Next" button enables automatically. Audio samples playable. | `[ ] PASS` |

---

## 3. Pre-Meeting Audio Bridge & Routing Verification

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | **Virtual Audio Bridge Guidance** | Locate "Teams Virtual Audio Bridge" guidance card on `/sessions/$id`. | Card shows clear instructions: AutoHR ➔ `CABLE Input`, Teams Mic ➔ `CABLE Output` (QA-010). | `[ ] PASS` |
| **3.2** | **Audio Device Detection** | Inspect device status on card. | Status shows VB-CABLE Input detected via `sounddevice` API. | `[ ] PASS` |
| **3.3** | **Test Chime Playback** | Open Microsoft Teams Settings ➔ Audio Devices (Microphone set to `CABLE Output`). In AutoHR, click **"Test Audio Bridge Chime"**. | AutoHR sends 440 Hz chime. Microsoft Teams microphone volume meter registers active deflection. | `[ ] PASS` |
| **3.4** | **Meeting Details Safety Edit** | (Optional) Click "Edit Meeting Details" to update scheduled time or organizer. | Updates apply cleanly without invalidating pre-compiled slide assets (QA-002). | `[ ] PASS` |

---

## 4. Microsoft Teams Live Join & Admission

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | **Launch Meeting Bot** | Click **"Launch Bot & Join Teams"**. | AutoHR launches Playwright instance with persistent Edge profile and navigates to Teams meeting URL. | `[ ] PASS` |
| **4.2** | **Lobby Detection** | If meeting lobby is active, observe session status. | Status card displays `State: IN_LOBBY` with prompt: *"Bot is waiting in the Microsoft Teams lobby. Please admit the bot."* | `[ ] PASS` |
| **4.3** | **Meeting Admission** | Meeting host clicks "Admit" in Microsoft Teams. | Bot enters meeting room. Status transitions from `IN_LOBBY` ➔ `CONNECTED`. | `[ ] PASS` |
| **4.4** | **Roster Initialization** | Check Meeting Status card participant counter. | Bot detects connected participants in call roster via `ParticipantMonitor`. | `[ ] PASS` |

---

## 5. Presentation Detection & Start Induction Readiness

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **5.1** | **Presenter Screen Share** | Presenter in Teams shares PowerPoint slideshow in "Window" or "Screen" mode. | AutoHR `PresentationObserver` detects screen share video stream. | `[ ] PASS` |
| **5.2** | **Slide OCR Fingerprinting** | Observe Presentation Status indicator. | Status reflects `Detected - Slide 1 (Title)`. | `[ ] PASS` |
| **5.3** | **Readiness Rule Evaluation** | Check "Start Induction" button state (QA-011). | Button enables cleanly: Teams connected (green), assets ready (green), audio ready (green). | `[ ] PASS` |
| **5.4** | **Manual Override Soft Gate** | *Contingency:* If screen share OCR is delayed, observe Start Induction button. | Button enables with warning badge: *"Presentation unconfirmed - manual override available"*. Clicking prompts confirmation modal. | `[ ] PASS` |

---

## 6. Live Induction Narration & Synchronization

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **6.1** | **Authorize Start Induction** | Click **"Start Induction"**. | Session status transitions to `IN_PROGRESS`. Real-time activity timer begins. | `[ ] PASS` |
| **6.2** | **Slide 1 Speech Dispatch** | Listen to Microsoft Teams call audio. | Bot plays slide 1 synthesized narration through VB-Cable into meeting. Remote attendees hear voice clearly. | `[ ] PASS` |
| **6.3** | **Presenter Slide Advance** | Presenter advances PowerPoint to Slide 2. | `PresentationObserver` detects visual transition to Slide 2 fingerprint within 2-4 seconds. | `[ ] PASS` |
| **6.4** | **Synchronized Audio Queue** | Observe audio playback upon slide change. | Slide 1 audio ceases (if still playing); Slide 2 narration commences immediately. Duplicate triggers prevented. | `[ ] PASS` |
| **6.5** | **Participant Attendance Poll** | Keep attendees connected in call during presentation. | Background telemetry polls roster every 15s, recording join timestamps and dwell duration in `attendances` table. | `[ ] PASS` |

---

## 7. Safe Termination & Call Disconnect

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **7.1** | **Disconnect Call Action** | At conclusion of induction, click **"Disconnect Call"**. | Confirmation modal appears: *"Are you sure you want to disconnect the AutoHR bot?"* (QA-008). | `[ ] PASS` |
| **7.2** | **Transit Locking** | Confirm disconnect in modal. | Button transitions to `isDisconnecting = true` (disabled, spinner). Playwright gracefully departs call. | `[ ] PASS` |
| **7.3** | **Session Completion** | Observe final session status. | Status updates to `COMPLETED`. Navigation advances to Post-Induction Report tab. | `[ ] PASS` |

---

## 8. Compliance Reporting & Data Integrity

| # | Item | Execution Step | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **8.1** | **Evidence-Based Attendance** | Review Attendance Metrics on Report tab. | Roster matches actual attendees. No artificial 100% attendance (QA-007). Unjoined attendees marked `Absent`. | `[ ] PASS` |
| **8.2** | **Identity Resolution Check** | Verify attendees matched by email. Verify unambiguous names matched. | Attendees matched accurately. Ambiguous names flagged as `"Unverified (Ambiguous name match - review required)"`. | `[ ] PASS` |
| **8.3** | **Download PDF Report** | Click **"Report (.pdf)"** button. | Generates and downloads styled KONE corporate PDF report (`/runtime/{id}/report.pdf`) with complete tables (QA-005). | `[ ] PASS` |
| **8.4** | **Download Word Report** | Click **"Report (.docx)"** button. | Generates and downloads standard OOXML `.docx` report with formatted metadata and attendance list (QA-005). | `[ ] PASS` |
| **8.5** | **Disk Artifact Verification** | Inspect `static/sessions/{id}/reports/`. | Verify `induction_report.md` and `induction_transcript.md` exist on disk. | `[ ] PASS` |

---

## 9. Sign-Off & Acceptance Record

- **Test Executor:** ___________________________  
- **HR Lead / Sponsor:** ___________________________  
- **Execution Date:** ___________________________  
- **Meeting ID / Link:** ___________________________  
- **Final Result:** `[ ] ACCEPTED / [ ] REJECTED (Reason Attached)`
