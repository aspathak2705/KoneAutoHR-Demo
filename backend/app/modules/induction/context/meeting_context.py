import datetime

def build_meeting_context(session) -> dict:
    """
    Compiles session variables to produce meeting details (greeting scripts, session type context).
    """
    scheduled_at = session.scheduled_at
    time_of_day = "day"
    greeting = "Hello"

    if scheduled_at:
        # Check if scheduled_at is string or datetime object
        if isinstance(scheduled_at, str):
            try:
                dt = datetime.datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
                hour = dt.hour
            except ValueError:
                hour = 9  # Fallback morning
        else:
            hour = scheduled_at.hour

        if 5 <= hour < 12:
            time_of_day = "morning"
            greeting = "Good morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
            greeting = "Good afternoon"
        else:
            time_of_day = "evening"
            greeting = "Good evening"

    from app.db.database import SessionLocal
    from app.modules.configuration.configuration_service import configuration_service

    with SessionLocal() as db:
        config = configuration_service.get_active_config(db)

    if not config:
        raise ValueError("Organization profile is not configured yet. Please complete the Profile page before preparing AI content.")

    company_name = config.company_name
    company_domain = config.company_domain
    department = getattr(session, "department", "General") or "General"
    language = getattr(session, "language", "English") or "English"
    session_type = getattr(session, "session_type", "General") or "General"

    return {
        "greeting": greeting,
        "time_of_day": time_of_day,
        "company_name": company_name,
        "company_domain": company_domain,
        "department": department,
        "language": language,
        "session_type": session_type,
        "objective": f"Introduce new hires to {company_name} policies, culture, and guidelines.",
        "ai_officer_name": config.ai_officer_name,
        "ai_trainer_name": config.ai_trainer_name,
        "ai_role_description": config.ai_role_description,
        "vocal_tone": config.vocal_tone,
        "communication_style": config.communication_style,
    }
