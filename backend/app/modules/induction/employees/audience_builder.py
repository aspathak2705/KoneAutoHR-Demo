def build_audience_summary(profiles: list[dict]) -> dict:
    """
    Computes statistical and context metadata about the audience.
    Analyzes departments and designations to assess technical ratio.
    """
    total = len(profiles)

    # 1. Departments represented
    departments = sorted(list(set(p["department"] for p in profiles if p["department"])))

    # 2. Audience Type
    if len(departments) == 1:
        audience_type = f"Single Department ({departments[0]})"
    elif len(departments) > 1:
        audience_type = "Mixed"
    else:
        audience_type = "General"

    # 3. Technical level heuristic
    tech_keywords = {"engineer", "developer", "programmer", "architect", "analyst", "data", "tech", "it", "administrator", "support"}
    tech_count = 0
    for p in profiles:
        designation = p["designation"].lower()
        if any(kw in designation for kw in tech_keywords):
            tech_count += 1

    if total == 0:
        technical_level = "Unknown"
    elif (tech_count / total) >= 0.6:
        technical_level = "Technical"
    elif (tech_count / total) <= 0.2:
        technical_level = "Non-Technical"
    else:
        technical_level = "Mixed"

    return {
        "total_employees": total,
        "audience_type": audience_type,
        "departments_represented": departments,
        "new_hires_count": total,
        "technical_level": technical_level
    }
