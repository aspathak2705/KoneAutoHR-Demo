# KONE AutoHR — Phase 0: Azure Readiness & Repository Audit Report

**Audit Date**: September 21, 2026  
**Target Application**: KONE AutoHR (FastAPI + React/TanStack Start + PostgreSQL + Local Windows Automation)  
**Auditor**: Senior Cloud Architect & Security Reviewer  

---

## 1. Executive Summary

A comprehensive repository audit of the KONE AutoHR codebase was conducted to evaluate its current local-first Windows implementation and prepare for a future Azure-centered architecture.

### Current Architecture Overview
KONE AutoHR is a local-first desktop application designed for automated HR employee induction. It uses a **FastAPI** backend, a **React (TanStack Start / Vite)** frontend, a **local PostgreSQL** database (`127.0.0.1:5432/autohr`), local file storage with AES-256-GCM envelope encryption and Windows DPAPI master key protection, and local process orchestration (Playwright + Microsoft Edge, PowerPoint, VB-Audio Virtual Cable, and Sarvam TTS API).

### Key Audit Findings
1. **Cloud Readinss Distinction**: The FastAPI API endpoints, PostgreSQL database models, asset deduplication logic, and security envelope encryption are cleanly structured and cloud-compatible with standard configuration abstractions.
2. **Local Automation Coupling**: Process execution (`app/modules/induction`, `app/api/v1/runtime.py`, Playwright Edge control, VB-Audio routing) is **fundamentally coupled to the local Windows execution host** and cannot run inside Azure App Service or containerized serverless cloud environments without dedicated local runner agents.
3. **Configuration & Hardcoding**: Backend configuration uses `pydantic-settings` reading from `.env`. Current code relies on hardcoded local bearer tokens (`autohr_master_secret_token_2026`), static localhost URLs (`127.0.0.1:5432`, `http://localhost:5173`), and local file system paths (`storage/`).
4. **Security Controls**: File assets (.pptx, .xlsx) are encrypted on disk via AES-256-GCM with DEKs wrapped by a Windows DPAPI Master Key. Database metadata (employee names, email addresses, meeting links) is currently stored unencrypted in PostgreSQL.
5. **Zero Redundancy & Deduplication**: Plaintext SHA-256 content hashing deduplication and reference-aware cleanup (`CleanupService`) are working cleanly and verified by automated tests.

---

## 2. Repository Structure Discovery Summary

| Area | Actual Path | Purpose | Audit Notes |
| :--- | :--- | :--- | :--- |
| **Backend Entry Point** | `backend/main.py` | Application startup & router registration | Lifespan validates DB, DPAPI key provider, storage writeability, Sarvam API key, Edge binary, runs Alembic migrations, and starts background scheduler worker. |
| **Configuration** | `backend/app/core/config.py` | Pydantic Settings & `.env` parsing | Reads `.env`. Default fallbacks point to `127.0.0.1:5432` PostgreSQL and local `storage/` paths. Uses custom `check_env_fallbacks` validator. |
| **Database & Models** | `backend/app/db/database.py`, `backend/app/models/` | SQLAlchemy Engine & DB Models | Uses SQLAlchemy 2.0 (`DeclarativeBase`), `psycopg2-binary`/`psycopg`. Connection pool configured with `pool_pre_ping=True`. Models define sessions, uploads, presentations, employee lists, meetings, runtimes. |
| **Migrations** | `backend/migrations/` | Alembic Database Schema Migrations | 4 migration files (`52d87f218d53` through `e8f901a23b45`). Programmatically executed on startup (`command.upgrade(alembic_cfg, "head")`). |
| **Storage & Deduplication**| `backend/app/storage/` | Asset management & cleanup | `LocalStorageProvider` handles file save, SHA-256 calculation, and AES-256-GCM encrypted save. Implements `StorageProvider` abstract base class. `CleanupService` manages reference counts. |
| **Security & Encryption** | `backend/app/core/security/` | Key management & envelope encryption | `EncryptionService` (AES-256-GCM DEKs), `KeyManager` with `WindowsCredentialKeyProvider` (DPAPI) and `DevelopmentKeyProvider` fallbacks. `SecureStorage` handles temporary plaintext decryption in `storage/runtime_temp/`. |
| **Runtime Automation** | `backend/app/modules/induction/`, `backend/app/api/v1/runtime.py` | Playwright, Edge, Teams, Audio | Launches Microsoft Edge via Playwright using `asyncio.WindowsProactorEventLoopPolicy`. Interacts with PowerPoint COM/native applications, Sarvam TTS API, and VB-Audio Virtual Cable ("CABLE Input"). |
| **Frontend** | `frontend/` | React 19 / TanStack Start UI | Vite-based SPA/SSG framework. Uses `apiFetch` with hardcoded bearer token (`autohr_master_secret_token_2026`) and `VITE_API_BASE_URL`. Stores metadata in `localStorage`. |
| **Documentation** | `docs/` | Architectural guides | Contains `LOCAL_POSTGRESQL_SETUP.md` and `SECURITY_AND_KEY_MANAGEMENT.md`. |
| **Verification Scripts** | `backend/scripts/` | Testing & verification tools | Contains `verify_local_database.py`, `verify_secure_e2e_lifecycle.py`, `storage_audit.py`, `initialize_security.py`, `migrate_assets_to_encryption.py`. |

### Important Found Files
- `backend/requirements.txt`: FastAPI, SQLAlchemy, Alembic, psycopg2-binary, Playwright, sounddevice, soundfile, python-pptx, openpyxl, cryptography.
- `frontend/package.json`: React 19, `@tanstack/react-start`, `@tanstack/react-router`, Tailwind CSS v4, Vite.
- `.gitignore`: Ignore `.env`, `storage/`, `autohr.db`, `node_modules/`, `__pycache__/`.

---

## 3. Application Architecture Mapping

```mermaid
flowchart TD
    subgraph Frontend ["React / TanStack Start Frontend"]
        UI["Web UI Components (Browser)"]
    end

    subgraph Backend ["FastAPI Core Backend (Cloud / Local Host)"]
        API["FastAPI REST Endpoints (/api/v1)"]
        Auth["Bearer Token Auth (verify_token)"]
        Config["Pydantic Settings (config.py)"]
        Dedupe["SHA-256 Content Deduplication"]
        Cleanup["CleanupService (Ref Counting)"]
        Enc["EncryptionService (AES-256-GCM)"]
    end

    subgraph Data ["Data Layer"]
        DB[(Local PostgreSQL 127.0.0.1:5432)]
        Keys["DPAPI Master Key Store (storage/keys)"]
        Storage["Encrypted Local Disk (storage/uploads)"]
    end

    subgraph LocalRuntime ["Local Execution Host (Windows PC Only)"]
        Edge["Microsoft Edge (Playwright)"]
        Teams["Microsoft Teams Meeting Joiner"]
        PPT["PowerPoint / Slide Processing"]
        Audio["VB-Audio Virtual Cable"]
        Sarvam["Sarvam Bulbul V3 TTS API"]
    end

    UI -->|HTTP / JSON + Bearer Token| API
    API --> Auth
    API --> Config
    API --> Dedupe
    API --> DB
    Dedupe --> Enc
    Enc --> Keys
    Enc --> Storage
    Cleanup --> DB
    Cleanup --> Storage
    API -->|Async Tasks / Scheduler| LocalRuntime
    LocalRuntime --> Edge
    LocalRuntime --> Teams
    LocalRuntime --> PPT
    LocalRuntime --> Audio
    LocalRuntime --> Sarvam
```

---

## 4. Configuration Audit

| Configuration Variable | Current Source | Sensitive? | Local-Only? | Azure Migration Consideration |
| :--- | :--- | :---: | :---: | :--- |
| `DATABASE_URL` | `.env` / `config.py` | **Yes** | No | Point to Azure Database for PostgreSQL Flexible Server connection string. |
| `AUTOHR_STORAGE_PATH` | `.env` / `config.py` | No | Partially | Abstract `LocalStorageProvider` to `AzureBlobStorageProvider`. |
| `KEY_PROVIDER` | `.env` / `config.py` | **Yes** | **Yes (DPAPI)** | Introduce `AzureKeyVaultProvider` implementation of `KeyProvider` protocol. |
| `SARVAM_API_KEY` | `.env` | **Yes** | No | Store in Azure Key Vault / App Service Environment Variables. |
| `LLM_API_KEY` | `.env` | **Yes** | No | Store in Azure Key Vault / App Service Environment Variables. |
| `AUDIO_OUTPUT_DEVICE` | `.env` (`CABLE Input`) | No | **Yes** | Local execution runner concern only; invalid on Cloud App Service. |
| `AUDIO_MONITOR_DEVICE` | `.env` (`Realtek Speakers`)| No | **Yes** | Local execution runner concern only. |
| `EDGE_CHANNEL` | `.env` (`msedge`) | No | **Yes** | Local execution runner concern only. |
| `ALLOWED_ORIGINS` | `.env` | No | No | Configure to match Azure Static Web Apps / App Service domain. |
| `API_BASE_URL` | `.env` / Frontend env | No | No | Update frontend `VITE_API_BASE_URL` to Azure App Service HTTPS URL. |
| `Bearer Secret Token` | Hardcoded in `dependencies.py` & `sessions-store.ts` | **Yes** | No | Replace static bearer string with Entra ID JWT validation or OAuth2. |

---

## 5. Database & Migration Audit

- **ORMs & Drivers**: SQLAlchemy 2.0 using `psycopg2-binary` and `psycopg`.
- **Database Engine**: PostgreSQL running locally at `127.0.0.1:5432/autohr`.
- **Connection Health**: `pool_pre_ping=True` and `pool_recycle=300` configured in `app/db/database.py`. Verified via `verify_local_database.py`.
- **Migrations**: Programmatically executed on startup using Alembic (`alembic upgrade head`). Schema current revision: `e8f901a23b45` (`add_encryption_metadata_columns`).
- **PostgreSQL Compatibility with Azure**:
  - Code uses standard ANSI SQL via SQLAlchemy ORM.
  - No custom non-standard PostgreSQL extensions required.
  - Direct compatibility with Azure Database for PostgreSQL Flexible Server.
- **Assumptions / Hardcoding**: `alembic.ini` hardcodes default connection string `postgresql://autohr_user:autohr_password@127.0.0.1:5432/autohr`. In Azure deployment, Alembic configuration should read dynamically from environment variables (`settings.AUTOHR_DATABASE_URL`).

---

## 6. Storage & Asset Lifecycle Audit

- **Core Lifecycle**: File Upload -> SHA-256 Hash -> Deduplication Check -> AES-256-GCM Payload Encryption -> Encrypted File Storage -> DB Metadata Save -> Temporary Decryption Context Manager -> Usage -> Context Exit Cleanup -> Unreference DB Cleanup -> Physical Storage Delete.
- **Zero Redundancy Principle**: Fully preserved. Content hashing occurs on original plaintext stream prior to encryption. Identical uploaded files increment reference count without creating duplicate physical files.
- **Local Filesystem Dependencies**:
  - `LocalStorageProvider` writes to relative disk paths (`storage/uploads/`).
  - Runtime automation relies on physical filesystem path passing to Playwright / PowerPoint.
- **Cloud Storage Readiness**: `LocalStorageProvider` implements `StorageProvider` interface (`app/storage/base.py`). Creating an `AzureBlobStorageProvider` implementation for `StorageProvider` is straightforward in future phases.

---

## 7. Security & Key-Management Audit

- **Implemented Controls**:
  - Data payload encryption via AES-256-GCM.
  - Envelope encryption wrapping per-asset Data Encryption Keys (DEKs) using a 256-bit Master Key.
  - Master Key protected on Windows via `win32crypt.CryptProtectData` (Windows DPAPI) in `WindowsCredentialKeyProvider`.
  - Development fallback `DevelopmentKeyProvider` available when DPAPI module is absent.
  - `SecureStorage` context manager unwraps DEKs and creates temporary plaintext files in `storage/runtime_temp/` that auto-wipe on exit.
- **DPAPI Dependencies**: Master Key DPAPI binary is tied to local Windows machine user credentials (`storage/keys/master.dpapi`).
- **Data at Rest Scope**: Persistent asset files (.pptx, .xlsx, .mp3) are AES-encrypted. PostgreSQL table columns (employee profiles, session metadata, meeting links) remain plaintext. Full database encryption relies on host BitLocker / Azure Transparent Data Encryption (TDE).
- **Hardcoded Secret Finding**:
  - `app/core/dependencies.py`: Static token check `if token != "autohr_master_secret_token_2026":`
  - `frontend/src/lib/sessions-store.ts`: Hardcoded header `Authorization: Bearer autohr_master_secret_token_2026`.

---

## 8. Runtime & Local Execution Audit

| Runtime Component | Cloud Compatible? | Local Execution Required? | Reason / Code Evidence |
| :--- | :---: | :---: | :--- |
| **FastAPI Web API** | **YES** | No | Standard ASGI web application. Standard HTTP REST endpoints. |
| **Database Access** | **YES** | No | Standard PostgreSQL TCP connectivity. |
| **Playwright / Microsoft Edge** | **NO** | **YES** | `main.py` explicitly sets `WindowsProactorEventLoopPolicy` and checks for `msedge.exe`. Edge joins Teams meetings locally. |
| **PowerPoint Processing** | **NO** | **YES** | Interacts with local Windows presentation files and rendering engine. |
| **VB-Audio Virtual Cable** | **NO** | **YES** | `config.py` hardcodes `CABLE Input` Windows audio multimedia device for streaming TTS audio into Teams. |
| **Sarvam TTS Audio API** | **YES** | No | Remote REST API (`https://api.sarvam.ai`). |

> [!IMPORTANT]
> **Key Architecture Insight**: Azure App Service **cannot** host Playwright Edge automation or VB-Audio Virtual Cable routing. In a future Azure architecture, FastAPI API and Database can migrate to Azure, while runtime automation must be delegated to a **Local Office Runner Agent** running on an authorized Windows machine.

---

## 9. Authentication & Authorization Audit

- **Current Mechanism**: Single static hardcoded bearer token (`autohr_master_secret_token_2026`).
- **Role/Permissions**: No RBAC or multi-user access control currently enforced in backend API routes.
- **Entra ID Migration Consideration**: Backend requires an abstraction layer (`AuthService` / `TokenVerifier`) to validate Microsoft Entra ID OAuth2 JWT tokens without breaking existing local bearer authentication during transition.

---

## 10. Dependency & Deployment Audit

- **Python Dependencies**: Standard cross-platform packages (`fastapi`, `sqlalchemy`, `alembic`, `httpx`, `cryptography`) combined with Windows-specific packages (`pywin32` / `win32crypt`, `sounddevice`).
- **Node.js / Frontend Dependencies**: Vite + TanStack Start. Completely cloud-ready for static hosting (Azure Static Web Apps or NGINX container).
- **Docker Support**: Currently absent (no `Dockerfile` or `docker-compose.yml` present in repository).

---

## 11. Testing & Verification Audit

- **Automated Tests Executed**:
  - `pytest tests/`: **9 passed in 1.12s** (`test_encryption_service.py` 6 passed, `test_storage_deduplication.py` 3 passed).
  - `python -m scripts.verify_secure_e2e_lifecycle`: **PASSED** (Full E2E DPAPI -> Encrypted Upload -> Transparent Access -> Deduplication -> Cleanup -> Audit).
  - `python -m scripts.storage_audit --verify-encryption`: **PASSED** (0 missing files, 0 orphan files, decryption integrity check PASSED).
- **Test Dependencies**: Tests run locally against Windows DPAPI and local SQLite/PostgreSQL.

---

## 12. Azure Readiness Classification

### Category A — Can Remain Unchanged Initially
- Database Models & SQLAlchemy ORM (`app/models/`).
- Plaintext SHA-256 Deduplication Logic (`app/storage/local_storage.py`).
- Reference-Aware Cleanup Service (`app/storage/cleanup_service.py`).
- AES-256-GCM Envelope Encryption Core (`app/core/security/encryption_service.py`).
- Sarvam TTS Integration Service (`app/services/voice_service.py`).

### Category B — Requires Configuration Changes
- `config.py` Pydantic Settings (Replace local fallbacks with Azure Environment Variable configuration).
- `alembic.ini` (Load connection string dynamically from environment variable).
- Frontend `VITE_API_BASE_URL` (Point to Azure App Service HTTPS URL).

### Category C — Requires Provider Abstraction
- Storage Provider: Add `AzureBlobStorageProvider` alongside existing `LocalStorageProvider`.
- Key Provider: Add `AzureKeyVaultProvider` alongside existing `WindowsCredentialKeyProvider`.
- Authentication Provider: Abstract bearer token check to support Entra ID JWT verification.

### Category D — Local Execution Dependent (Must Stay on Local Windows Host / Runner Agent)
- Playwright Microsoft Edge Automation (`app/modules/induction/`).
- VB-Audio Virtual Cable Audio Routing (`CABLE Input`).
- PowerPoint Local Application Automation.

### Category E — Requires KONE IT / Security Decision
- Microsoft Entra ID Tenant Registration & Client ID provisioning.
- Azure Database for PostgreSQL Flexible Server firewall & private endpoint policy.
- Azure Key Vault access policies for master key management.
- Local Runner Agent security token & communication model.

---

## 13. Azure Migration Dependency Matrix

| Capability | Current Implementation | Azure Target | Required Abstraction | Dependencies | Risk | Target Phase |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **API Backend** | FastAPI on local `uvicorn` | Azure App Service (Linux) | Environment Configuration | Python dependencies | Low | Phase 1 |
| **Database** | Local PostgreSQL (`127.0.0.1`) | Azure DB for PostgreSQL Flexible | Connection String Config | Firewall / VNet | Low | Phase 1 |
| **Asset Storage** | Encrypted Local Disk (`storage/`) | Azure Blob Storage | `StorageProvider` Interface | Azure SDK (`azure-storage-blob`) | Medium | Phase 2 |
| **Key Protection** | Windows DPAPI | Azure Key Vault | `KeyProvider` Interface | Azure SDK (`azure-keyvault-keys`) | Medium | Phase 2 |
| **Authentication** | Static Bearer Token | Microsoft Entra ID (OAuth2/OIDC) | `AuthService` Interface | Microsoft Entra App Registration | Medium | Phase 2 |
| **Runtime Automation** | Local Playwright + Edge + Audio | Local Office Runner Agent | Task Queue / Webhook Orchestrator | Windows Host PC | High | Phase 3 |

---

## 14. Recommended Phase 1 Scope

Based on repository audit findings, Phase 1 should focus strictly on **Cloud Backend Decoupling & Provider Abstractions** without breaking the working local application:

1. **Environment & Configuration Hardening**:
   - Update `config.py` and `alembic.ini` to read environment variables dynamically without hardcoded localhost defaults.
   - Replace static bearer token check with configurable `AUTH_TOKEN` environment variable fallback.
2. **Storage Provider Interface Refactoring**:
   - Ensure all API services interact strictly through the `StorageProvider` abstract base class (`app/storage/base.py`).
   - Add stub `AzureBlobStorageProvider` for future Blob Storage enablement.
3. **KeyProvider Interface Refactoring**:
   - Cleanly formalize `KeyManager` provider resolution to support loading `AzureKeyVaultProvider` when configured via environment variable `KEY_PROVIDER=azure_keyvault`.
4. **Health & Readiness Endpoints**:
   - Enhance `/api/v1/health` to report active storage provider, database host, and key provider status.

---

## 15. Deferred Work (Explicitly Out of Scope for Phase 1)

- Do **NOT** connect to live Azure resources or add Azure credentials yet.
- Do **NOT** replace Windows DPAPI provider for local desktop execution.
- Do **NOT** modify existing Teams meeting or Playwright Edge automation.
- Do **NOT** redesign database schema or create unnecessary Alembic migrations.
- Do **NOT** build a local runner agent service.

---

## 16. Audit Verification Log

- **Files Inspected**: 45 backend/frontend files across `app/`, `config/`, `storage/`, `security/`, `modules/`, `migrations/`, `frontend/src/`.
- **Files Modified**: `0` (Strict read-only non-destructive audit).
- **Files Created**: `1` (`docs/PHASE_0_AZURE_READINESS_AUDIT.md`).
- **Database Schema Changes**: `No`.
- **Azure Connections Made**: `No`.
- **Tests Executed**:
  - `python -m pytest tests/` (9 passed)
  - `python -m scripts.verify_secure_e2e_lifecycle` (PASSED)
  - `python -m scripts.storage_audit --verify-encryption` (PASSED)
