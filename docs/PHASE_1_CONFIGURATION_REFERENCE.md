# KONE AutoHR — Phase 1 Configuration Reference

**Date**: September 21, 2026  
**Target Audience**: Developers, DevOps Engineers, System Administrators  

---

## 1. Supported Environment Variables

| Variable | Description | Default (Development) | Production Requirement | Sensitive? |
| :--- | :--- | :--- | :--- | :---: |
| `APP_ENV` | Application environment (`development` / `production`) | `development` | Mandatory set to `production` | No |
| `AUTH_TOKEN` | Bearer secret token for API authentication | `autohr_dev_secret_token_local` | **Mandatory** explicit secret | **Yes** |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://autohr_user:autohr_KONE2026@127.0.0.1:5432/autohr` | **Mandatory** Azure/Prod DB URL | **Yes** |
| `KEY_PROVIDER` | Active key provider (`windows_dpapi` / `azure_keyvault` / `development`) | `windows_dpapi` | `windows_dpapi` or `azure_keyvault` | No |
| `STORAGE_PROVIDER` | Active storage provider (`local` / `azure_blob`) | `local` | `local` or `azure_blob` | No |
| `AUTOHR_STORAGE_PATH` | Local storage root directory path | `storage` | Path to persistent storage | No |
| `SARVAM_API_KEY` | Sarvam Bulbul V3 TTS API Key | Configured in `.env` | **Mandatory** API Key | **Yes** |
| `LLM_API_KEY` | OpenRouter / LLM API Key | Configured in `.env` | **Mandatory** API Key | **Yes** |

---

## 2. Safe Configuration Examples

### Local Development (`.env`):
```env
APP_ENV=development
DATABASE_URL=postgresql://autohr_user:autohr_KONE2026@127.0.0.1:5432/autohr
AUTH_TOKEN=autohr_dev_secret_token_local
KEY_PROVIDER=windows_dpapi
STORAGE_PROVIDER=local
AUTOHR_STORAGE_PATH=storage
SARVAM_API_KEY=<your-sarvam-key>
```

### Production / Azure Environment Variables:
```env
APP_ENV=production
DATABASE_URL=postgresql://<db_user>:<db_password>@<azure_pg_host>:5432/autohr?sslmode=require
AUTH_TOKEN=<random-256-bit-secure-token>
KEY_PROVIDER=windows_dpapi
STORAGE_PROVIDER=local
AUTOHR_STORAGE_PATH=/home/site/wwwroot/storage
SARVAM_API_KEY=<production-sarvam-key>
```

---

## 3. Configuration Validation & Failures

- **Missing `AUTH_TOKEN` in Production**:
  - Application startup immediately halts with:
    `ValueError: Security Violation: AUTH_TOKEN must be configured in production environment.`
- **Missing `SARVAM_API_KEY`**:
  - Startup lifespan validation halts with:
    `Startup Validation Failure: SARVAM_API_KEY is not configured.`
- **Unreachable Database Host**:
  - Startup lifespan validation halts with:
    `Startup Validation Failure: Database connection failed.`
