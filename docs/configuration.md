# Configuration Documentation

All configurations are driven by environment variables loaded through Pydantic Settings.

## Parameters
- `AUTOHR_DATABASE_URL`: Database connection path (e.g. `sqlite:///./autohr.db`).
- `UPLOAD_DIR`: Output folder path for file uploads.
- `LOG_LEVEL`: Logger verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- `LOG_FORMAT`: `text` or `json` structured layout output.
- `ALLOWED_ORIGINS`: Comma-separated list of CORS origins.
- `MAX_UPLOAD_SIZE`: Maximum allowable size of file uploads in bytes.
- `ENCRYPTION_KEY`: Secret string key used for credential Fernet AES encryption.
