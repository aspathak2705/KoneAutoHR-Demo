from typing import Dict, Any

class SessionSerializer:
    """
    Phase 4 — Session Serializer
    Serializes and deserializes the Session Script payload to guarantee exact compatibility with frontend types.
    """
    def serialize(self, script_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guarantees that opening, slides, and closing sections are populated.
        Fills missing fields with safe default structures.
        """
        # If the input doesn't follow the new schema, try to map from the old model
        opening = script_content.get("opening", {})
        if not opening:
            welcome = script_content.get("welcome_flow", {})
            opening = {
                "greeting": "Hello and welcome to KONE onboarding session.",
                "presenter_intro": welcome.get("intro", "I am your AI HR Trainer, here to guide you today."),
                "employee_welcome": "A warm welcome to all our new joiners.",
                "audio_check": "Before we begin, can everyone hear me clearly?",
                "ice_breaker": "Please post your name and department in the chat window.",
                "session_rules": welcome.get("rules", "Please stay muted during slides and use chat for questions."),
                "agenda": "Today we will cover company values, safety policies, and key onboarding steps."
            }

        slides = script_content.get("slides", [])
        if not slides:
            # Reconstruct from old slide_narrations if present
            slide_narrations = script_content.get("slide_narrations", {})
            if isinstance(slide_narrations, dict):
                for idx_str, narration in slide_narrations.items():
                    try:
                        num = int(idx_str)
                    except ValueError:
                        num = 1
                    slides.append({
                        "slide_number": num,
                        "title": f"Slide {num}",
                        "objective": f"Explain slide {num} topics.",
                        "transition_in": f"Let's move onto slide {num}.",
                        "narration": narration,
                        "understanding_check": "Does anyone have any questions on this slide?",
                        "transition_out": f"That completes slide {num}.",
                        "video_prompt": None,
                        "quiz_question": None
                    })
            else:
                slides = [{
                    "slide_number": 1,
                    "title": "Welcome to KONE",
                    "objective": "Introduce KONE values.",
                    "transition_in": "Welcome everyone.",
                    "narration": "KONE is built on innovation and safety. Today we cover safety first.",
                    "understanding_check": "Are there any questions?",
                    "transition_out": "Moving on.",
                    "video_prompt": None,
                    "quiz_question": None
                }]

        closing = script_content.get("closing", {})
        if not closing:
            closing = {
                "summary": script_content.get("closing_script", "That summarizes KONE's values, safety rules, and your direct next steps."),
                "next_steps": "Please complete your mandatory training portal items by the end of this week.",
                "farewell": "Thank you all for your time! Welcome to the KONE family, and have a great day!"
            }

        return {
            "opening": opening,
            "slides": slides,
            "closing": closing
        }

session_serializer = SessionSerializer()
