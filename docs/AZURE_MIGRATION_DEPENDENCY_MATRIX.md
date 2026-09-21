# KONE AutoHR — Azure Migration Dependency Matrix

**Date**: September 21, 2026  
**Status**: Initial Architecture Planning (Phase 0)  

This matrix details the migration plan for transitioning KONE AutoHR from a local-first desktop application to an Azure-centered enterprise architecture.

| Capability / Module | Current Implementation | Azure Target Architecture | Required Abstraction / Interface | Dependencies & Constraints | Risk Level | Target Phase |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **Web API Backend** | FastAPI on local Uvicorn process (`main.py`) | Azure App Service (Linux) | Environment Configuration Abstraction | Python 3.10+ runtime, Docker / App Service deployment | Low | Phase 1 |
| **Relational Database** | Local PostgreSQL (`127.0.0.1:5432/autohr`) | Azure Database for PostgreSQL Flexible Server | SQLAlchemy ORM & Alembic Migration Engine | PostgreSQL 14+, SSL connection, VNet/Firewall rules | Low | Phase 1 |
| **Asset Storage (.pptx, .xlsx)** | Encrypted Local Disk (`storage/uploads/`) | Azure Blob Storage | `StorageProvider` Interface (`app/storage/base.py`) | Azure SDK (`azure-storage-blob`), Container SAS tokens | Medium | Phase 2 |
| **Master Key Protection** | Windows DPAPI (`WindowsCredentialKeyProvider`) | Azure Key Vault | `KeyProvider` Protocol (`app/core/security/key_manager.py`) | Azure SDK (`azure-keyvault-keys`), Managed Identity | Medium | Phase 2 |
| **Authentication & Identity** | Static Bearer Token (`autohr_master_secret_token_2026`) | Microsoft Entra ID (OAuth 2.0 / OIDC) | `AuthService` / `TokenVerifier` Middleware | Entra ID App Registration, Tenant ID | Medium | Phase 2 |
| **Web Frontend** | React / TanStack Start Vite SPA (`frontend/`) | Azure Static Web Apps | API Base URL Environment Variable (`VITE_API_BASE_URL`) | Node.js build, HTTPS origin CORS alignment | Low | Phase 1 |
| **Teams & Edge Automation** | Local Playwright + Edge (`app/modules/induction/`) | Local Office Runner Agent | Task Queue / Webhook Execution Protocol | Physical Windows PC, Edge binary, Teams client | High | Phase 3 |
| **Audio Hardware Routing** | VB-Audio Virtual Cable ("CABLE Input") | Local Office Runner Agent | Audio Device Configuration Interface | Windows Multimedia Subsystem, VB-Cable driver | High | Phase 3 |
| **Speech Generation** | Sarvam Bulbul V3 Voice API (`https://api.sarvam.ai`) | Sarvam Voice API / Azure Speech Service | `VoiceService` Abstraction | API Key configuration in Key Vault | Low | Phase 1 |

---

## Migration Phase Summary

- **Phase 0 (Current)**: Repository Audit, Security Verification, and Azure Readiness Assessment. (No code changes).
- **Phase 1**: Cloud Backend Preparation (Environment dynamic configuration, `alembic.ini` dynamic URL, Storage/Key Provider interface cleanup, static token config decoupling).
- **Phase 2**: Azure Cloud Integration (Azure Blob Storage adapter, Azure Key Vault provider, Entra ID authentication).
- **Phase 3**: Hybrid Execution Architecture (Separation of Cloud Control Plane API and Local Office Runner Agent for Teams/Edge/Audio automation).
