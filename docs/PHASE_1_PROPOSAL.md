# KONE AutoHR — Phase 1 Proposal: Cloud Backend Decoupling & Provider Abstractions

**Proposed Date**: September 2026  
**Status**: Proposal Pending Review & Explicit Approval  

---

## 1. Objective

The objective of Phase 1 is to perform non-breaking refactoring and configuration decoupling to prepare the FastAPI backend and database layer for Azure App Service deployment while maintaining 100% backward compatibility with the local-first Windows execution environment.

---

## 2. Target Files for Modification (Phase 1 Scope)

### Files to Modify:
1. `backend/app/core/config.py`:
   - Refactor `Settings` class to read `DATABASE_URL` dynamically from environment variables without overriding host env with file fallbacks unconditionally.
   - Add explicit settings for `KEY_PROVIDER` (defaulting to `"windows_dpapi"`) and `STORAGE_PROVIDER` (defaulting to `"local"`).
2. `backend/alembic.ini` & `backend/migrations/env.py`:
   - Update `env.py` to pull the database URL directly from `app.core.config.settings.AUTOHR_DATABASE_URL` instead of relying on a hardcoded string in `alembic.ini`.
3. `backend/app/core/dependencies.py`:
   - Decouple static bearer token check `autohr_master_secret_token_2026` by reading from `settings.AUTH_TOKEN` with local dev fallback.
4. `backend/app/storage/base.py` & `backend/app/storage/local_storage.py`:
   - Formalize async storage contract methods for blob compatibility.
5. `backend/app/core/security/key_manager.py`:
   - Add stub `AzureKeyVaultProvider` class skeleton that raises `NotImplementedError` if invoked without Azure credentials, preserving `WindowsCredentialKeyProvider` as default.

### Files That MUST NOT Change:
- `backend/app/modules/induction/*` (All Playwright Edge and Teams automation logic).
- `backend/app/core/security/encryption_service.py` (AES-256-GCM envelope encryption algorithm).
- `backend/app/storage/cleanup_service.py` (Zero redundancy reference counting cleanup).
- `backend/migrations/versions/*` (Existing Alembic schema migration chain).
- `frontend/*` (React TanStack Start UI).

---

## 3. Implementation Steps

1. **Environment Configuration Decoupling**:
   - Ensure `config.py` correctly respects standard `os.environ` overrides over local `.env` files when deployed in containerized or cloud environments.
2. **Dynamic Alembic Migration URL Resolution**:
   - Edit `migrations/env.py` so running `alembic upgrade head` in CI/CD or Azure App Service automatically connects to the configured `DATABASE_URL` without editing `alembic.ini`.
3. **KeyProvider & StorageProvider Registration Clean-up**:
   - Standardize factory patterns in `key_manager.py` and `local_storage.py` to allow dynamic instantiation based on configuration flags (`STORAGE_PROVIDER=azure_blob`, `KEY_PROVIDER=azure_keyvault`).
4. **Health Endpoint Enhancement**:
   - Update `/api/v1/health` response schema to expose active storage provider and key provider metadata for cloud readiness monitoring.

---

## 4. Testing & Rollback Strategy

### Automated Verification Plan:
1. Execute `pytest tests/` to confirm encryption service and storage deduplication tests pass.
2. Execute `python -m scripts.verify_secure_e2e_lifecycle` to ensure zero breaking changes to the encrypted asset lifecycle.
3. Execute `python -m scripts.storage_audit --verify-encryption` to confirm zero data corruption or orphan files.

### Rollback Strategy:
- All changes are additive/refactoring in nature with zero database schema alterations.
- Rollback can be performed via standard `git checkout main`.

---

## 5. Acceptance Criteria

- [ ] All 9 existing `pytest` tests pass cleanly.
- [ ] E2E secure lifecycle test executes successfully.
- [ ] Database connection URL in Alembic resolves dynamically from environment variables.
- [ ] No hardcoded database credentials remain in `alembic.ini`.
- [ ] Application startup validation passes on local Windows host.
- [ ] Zero Azure connections or cloud resources created.
