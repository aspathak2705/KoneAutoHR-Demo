import re
from app.core.exceptions import InvalidUploadException

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

def validate_employee_rows(employees: list[dict]):
    """
    Validates employee records for duplicates, email syntax, and empty names.
    """
    if not employees:
        raise InvalidUploadException("Employee Excel list contains no data rows.")

    seen_emails = set()
    for idx, emp in enumerate(employees):
        row_num = idx + 2  # Visual approximation of sheet row index

        name = emp.get("name")
        email = emp.get("email")

        if not name or not str(name).strip():
            raise InvalidUploadException(f"Missing employee name at row {row_num}.")

        if not email or not str(email).strip():
            raise InvalidUploadException(f"Missing email address for '{name}' at row {row_num}.")

        email_str = str(email).strip().lower()

        if not EMAIL_REGEX.match(email_str):
            raise InvalidUploadException(f"Invalid email format '{email}' at row {row_num}.")

        if email_str in seen_emails:
            raise InvalidUploadException(f"Duplicate email address '{email}' found at row {row_num}.")

        seen_emails.add(email_str)
