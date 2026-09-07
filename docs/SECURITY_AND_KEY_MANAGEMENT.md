# KONE AutoHR Security & Key Management Guide

This document defines the Local-First Security & Encryption Architecture for KONE AutoHR (Phases 4 & 5).

---

## 1. Security Architecture Overview

KONE AutoHR implements a **Local-First, Secure-by-Design, Zero-Redundancy** architecture. Data is stored locally on the office PC or desktop environment, protected by **Envelope Encryption** using **AES-256-GCM**.

```text
┌───────────────────────────────────────────────────────────┐
│              Windows OS (DPAPI Key Protection)            │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│         Master Key (256-bit AES, DPAPI Blob)              │
└─────────────────────────────┬─────────────────────────────┘
                              │ Wraps / Unwraps
                              ▼
┌───────────────────────────────────────────────────────────┐
│     Data Encryption Key (DEK per asset / Envelope)       │
└─────────────────────────────┬─────────────────────────────┘
                              │ Encrypts / Decrypts
                              ▼
┌───────────────────────────────────────────────────────────┐
│    AES-256-GCM Encrypted Local Asset Storage (.pptx, .xlsx)│
└───────────────────────────────────────────────────────────┘
```

---

## 2. Key Hierarchy & Envelope Encryption

1. **Master Key**:
   - 256-bit random key generated during security initialization.
   - Protected by **Windows DPAPI** (`win32crypt.CryptProtectData`) under the active Windows user security context.
   - Saved in `storage/keys/master.dpapi`.
2. **Data Encryption Keys (DEKs)**:
   - Generated per-asset via `AESGCM.generate_key(bit_length=256)`.
   - DEKs are encrypted (wrapped) using the Master Key via AES-GCM before database storage (`wrapped_dek`).
   - Raw plaintext DEKs are **never stored on disk or database**.

---

## 3. SHA-256 Deduplication vs. AES-256-GCM Encryption

To preserve the **Zero-Redundancy** principle:
1. **Hashing (SHA-256)**: Calculated on the **original plaintext content** during upload. Used for identity indexing and instant duplicate detection.
2. **Encryption (AES-256-GCM)**: Performed **after** checking for duplicate asset existence.
3. If an identical file is uploaded twice:
   - SHA-256 matches the existing DB entry.
   - The system reuses the existing encrypted physical file.
   - No second encrypted physical copy is created.

---

## 4. Transparent Encrypted Storage Access & Temp Cleanup

When processing PPT slide extraction, narration, or Excel parsing:
1. `secure_storage.open_decrypted_file(entity)` unwraps the asset DEK via the Master Key.
2. Decrypts the payload into an isolated temporary working directory under `storage/runtime_temp/<uuid>/`.
3. Plaintext file is available strictly for the context block duration and **deleted immediately upon context exit**.
4. Application startup automatically cleans up any stale temporary files resulting from abnormal process termination.

---

## 5. Migration & Maintenance Tooling

- **Security Initialization**:
  ```powershell
  python scripts/initialize_security.py
  ```
- **Secure Storage Audit & Decryption Integrity Check**:
  ```powershell
  python scripts/storage_audit.py --verify-encryption
  ```
- **Legacy Plaintext Asset Migration**:
  ```powershell
  # Dry run
  python scripts/migrate_assets_to_encryption.py
  # Execution
  python scripts/migrate_assets_to_encryption.py --execute
  ```
- **E2E Secure Lifecycle Test**:
  ```powershell
  python scripts/verify_secure_e2e_lifecycle.py
  ```

---

## 6. Threat Model & Boundaries

### What it Protects Against:
- Unauthenticated file copying off the Windows machine (encrypted ciphertext unusable without DPAPI master key).
- Casual filesystem browsing of uploaded HR PPTs, Excel sheets, and audio files.
- Unauthorized access to database backup files containing sensitive metadata.
- Tampered encrypted files (AES-256-GCM tag verification throws `InvalidTag`).

### What it DOES NOT Protect Against:
- A fully compromised active Windows user session (malware running as the active Windows user can call DPAPI).
- Memory scraping while an asset is actively being decrypted in memory.
