# Security Hardening Documentation

## Key Security Controls
1. **Fernet Encryption**: Critical configuration tokens and credentials are encrypted using Fernet (AES-128 in CBC mode with HMAC-SHA256).
2. **Dynamic CORS Configuration**: Explicit origin whitelist validation.
3. **Upload Validator**: Size constraints limit payload memory allocation; extensions and MIME types are whitelisted to prevent remote code executions; filename path-traversal patterns are stripped.
4. **Structured Error Handling**: Middleware intercepts internal server stacktraces and responds with unified JSON errors, preventing database schema leakage to API clients.
