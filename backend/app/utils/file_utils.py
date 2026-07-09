import os
import re

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes file name to retain only alphanumeric characters, underscores, dashes, and dots.
    """
    name, ext = os.path.splitext(filename)
    sanitized_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
    sanitized_ext = re.sub(r"[^a-zA-Z0-9\.]", "", ext)
    if not sanitized_name:
        sanitized_name = "file"
    return f"{sanitized_name}{sanitized_ext}"
