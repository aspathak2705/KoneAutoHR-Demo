# Local PostgreSQL Setup Guide for KONE AutoHR

This guide explains how to install, configure, and initialize Local PostgreSQL for the KONE AutoHR application on a local desktop machine.

---

## 1. Prerequisites

- **OS**: Windows 10/11 or Windows Server
- **PostgreSQL Version**: 14+ (Recommended: PostgreSQL 18 or 16)
- **Python**: 3.10+

---

## 2. PostgreSQL Installation & Configuration

### A. Download & Install
1. Download the official PostgreSQL installer for Windows from [postgresql.org](https://www.postgresql.org/download/windows/).
2. Run the installer and select the default components (PostgreSQL Server, command-line tools).
3. Set the superuser (`postgres`) password during installation (e.g. `autohr_password`).

### B. Network & Client Authentication Configuration
Ensure PostgreSQL listens on local loopback (`127.0.0.1`).
- File location: `C:\Program Files\PostgreSQL\<version>\data\pg_hba.conf`
- Required entry:
  ```text
  # IPv4 local connections:
  host    all             all             127.0.0.1/32            scram-sha-256
  ```

---

## 3. Database & User Creation

Open PowerShell and execute `psql` (or run SQL commands in pgAdmin):

```sql
-- Connect to postgres database
-- 1. Create dedicated application user
CREATE USER autohr_user WITH PASSWORD 'autohr_password';

-- 2. Create autohr database owned by autohr_user
CREATE DATABASE autohr OWNER autohr_user;

-- 3. Grant full privileges on database
GRANT ALL PRIVILEGES ON DATABASE autohr TO autohr_user;
```

---

## 4. Backend Environment Configuration

Update `backend/.env` to point `DATABASE_URL` to local PostgreSQL:

```env
DATABASE_URL=postgresql://autohr_user:autohr_password@127.0.0.1:5432/autohr
```

> [!NOTE]
> Always use `127.0.0.1` instead of `localhost` to avoid IPv4/IPv6 resolution latency.

---

## 5. Schema Initialization (Alembic Migrations)

Run database migrations from the `backend/` directory:

```powershell
cd backend
alembic upgrade head
```

Verify that schema is at head:
```powershell
alembic current
```

---

## 6. Verification & Troubleshooting

### A. Run Verification Tool
```powershell
python scripts/verify_local_database.py
```
Expected output:
```text
DATABASE_URL: postgresql://autohr_user:***@127.0.0.1:5432/autohr
Host: 127.0.0.1 (LOCAL)
Database: autohr
Connection Status: PASSED
```

### B. Common Troubleshooting
- **`OperationalError: connection to server at "127.0.0.1", port 5432 failed`**:
  Ensure the PostgreSQL service is running (`Get-Service -Name *postgres*`).
- **`FATAL: password authentication failed for user "autohr_user"`**:
  Verify credentials in `.env` match the password set in `CREATE USER`.
- **`FATAL: database "autohr" does not exist`**:
  Run step 3 to create the `autohr` database.
