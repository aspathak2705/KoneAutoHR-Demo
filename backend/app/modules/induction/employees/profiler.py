def profile_employees(employees: list[dict]) -> list[dict]:
    """
    Normalizes and constructs standard Employee Profile dictionaries.
    """
    profiles = []
    for emp in employees:
        profiles.append({
            "name": emp["name"].strip(),
            "email": emp["email"].strip().lower(),
            "department": (emp.get("department") or "General").strip(),
            "designation": (emp.get("designation") or "Staff").strip(),
            "location": (emp.get("location") or "Headquarters").strip()
        })
    return profiles
