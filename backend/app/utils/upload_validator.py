import os
import re
import hashlib
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import ValidationException
from app.core.constants import UploadType

class UploadValidator:
    """
    Module 0.3 — Upload Validator
    Enforces upload constraints for file size, extension, MIME verification, filename sanitization, and duplicate checksums.
    """
    EXTENSION_WHITELIST = {
        UploadType.PRESENTATION: [".ppt", ".pptx"],
        UploadType.EMPLOYEE_LIST: [".xls", ".xlsx"],
    }
    
    MIME_WHITELIST = {
        UploadType.PRESENTATION: [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/octet-stream"
        ],
        UploadType.EMPLOYEE_LIST: [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream"
        ]
    }

    async def validate(self, file: UploadFile, upload_type: UploadType) -> str:
        # 1. Filename Sanitization
        raw_name = file.filename or "uploaded_file"
        # Strip path traversal characters
        sanitized = os.path.basename(raw_name)
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", sanitized)
        
        # 2. Extension Check
        ext = os.path.splitext(sanitized)[1].lower()
        allowed_exts = self.EXTENSION_WHITELIST.get(upload_type, [])
        if ext not in allowed_exts:
            raise ValidationException(f"Forbidden extension {ext}. Allowed: {allowed_exts}")

        # 3. MIME Verification
        mime = file.content_type
        allowed_mimes = self.MIME_WHITELIST.get(upload_type, [])
        if mime and mime not in allowed_mimes:
            raise ValidationException(f"Forbidden MIME type {mime}.")

        # 4. Size Check
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0) # Reset stream position
        if size > settings.MAX_UPLOAD_SIZE:
            raise ValidationException(f"File size {size} bytes exceeds maximum allowed limit ({settings.MAX_UPLOAD_SIZE} bytes).")

        return sanitized

    def calculate_checksum(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

upload_validator = UploadValidator()
