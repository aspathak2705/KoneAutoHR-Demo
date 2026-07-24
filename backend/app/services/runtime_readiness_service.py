from typing import Dict, Any, Optional
import json
from pathlib import Path
from app.services.storage_service import storage_service

class RuntimeReadinessService:
    """
    Phase 3 — Runtime Readiness Engine
    Pure validation service that accepts a RuntimeContext dictionary and produces
    the authoritative, unified readiness report for backend endpoints and frontend UI widgets.
    """

    def evaluate_readiness(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates readiness against RuntimeContext without making UI/API assumptions or throwing exceptions.
        Includes descriptive reason fields to aid debugging.
        """
        session_id = context.get("session_id")
        if not context.get("session_exists", False):
            return {
                "overall_ready": False,
                "session_id": session_id,
                "presentation": {"ready": False, "reason": "Session record does not exist", "asset_id": None},
                "employees": {"ready": False, "reason": "Session record does not exist", "asset_id": None},
                "script": {"ready": False, "reason": "Session record does not exist"},
                "questions": {"ready": False, "reason": "Session record does not exist"},
                "audio": {"ready": False, "reason": "Session record does not exist"},
                "meeting": {"ready": False, "reason": "Session record does not exist", "configured": False, "teams_url": None},
                "missing_components": ["session"]
            }

        pres_asset = context.get("presentation_asset")
        emp_asset = context.get("employee_list_asset")
        script = context.get("presentation_script")
        questions = context.get("presentation_questions")
        meeting = context.get("meeting")

        # Presentation Readiness & Reason
        pres_ready = pres_asset is not None
        pres_reason = None if pres_ready else "No presentation asset linked"

        # Employee List Readiness & Reason
        emp_ready = emp_asset is not None
        emp_reason = None if emp_ready else "No employee list linked"

        # Script Readiness & Reason
        script_ready = pres_ready and script is not None and bool(getattr(script, "script_content", None))
        if script_ready:
            script_reason = None
        elif not pres_ready:
            script_reason = "No presentation asset linked"
        else:
            script_reason = "No presentation script generated for linked presentation asset"

        # Questions Readiness & Reason
        questions_ready = pres_ready and questions is not None and bool(getattr(questions, "questions_content", None))
        if questions_ready:
            questions_reason = None
        elif not pres_ready:
            questions_reason = "No presentation asset linked"
        else:
            questions_reason = "No expected questions/FAQs generated for linked presentation asset"

        # Package & Audio pre-generation Readiness - manifest.json single entry point
        package_dir = storage_service.get_session_dir(session_id)
        manifest_path = package_dir / "manifest.json"
        audio_ready = False
        audio_reason = "Speech audio files not generated yet"
        
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                
                # Check manifest contains required artifact paths
                has_script_ref = manifest.get("session_script") == "session_script.json"
                has_metadata_ref = manifest.get("runtime_metadata") == "runtime_metadata.json"
                has_audio_ref = manifest.get("audio_manifest") == "audio_manifest.json"
                
                # Verify audio files index is loaded
                audio_files = list(manifest.get("checksums", {}).keys())
                if len(audio_files) > 0 and has_script_ref and has_metadata_ref and has_audio_ref:
                    audio_ready = True
                    audio_reason = None
                else:
                    audio_reason = "Package manifest missing artifact references or audio files index"
            except Exception as e:
                audio_reason = f"Corrupted package manifest: {e}"
        else:
            audio_reason = "Presentation package manifest not built yet"

        # Meeting Readiness & Reason
        meeting_configured = meeting is not None and bool(getattr(meeting, "teams_url", None))
        meeting_ready = meeting_configured and bool(getattr(meeting, "date", None)) and bool(getattr(meeting, "time", None))

        if meeting_ready:
            meeting_reason = None
        elif not meeting:
            meeting_reason = "Meeting not configured"
        elif not getattr(meeting, "teams_url", None):
            meeting_reason = "Meeting URL missing"
        else:
            meeting_reason = "Meeting date or time missing"

        missing = []
        if not pres_ready:
            missing.append("presentation")
        if not emp_ready:
            missing.append("employees")
        if not script_ready:
            missing.append("script")
        if not questions_ready:
            missing.append("questions")
        if not audio_ready:
            missing.append("audio")
        if not meeting_ready:
            missing.append("meeting")

        overall_ready = pres_ready and emp_ready and script_ready and questions_ready and audio_ready and meeting_ready

        return {
            "overall_ready": overall_ready,
            "session_id": session_id,
            # Flat flags for backward compatibility
            "has_presentation": pres_ready,
            "has_employees": emp_ready,
            "has_script": script_ready,
            "has_faq": questions_ready,
            "has_audio": audio_ready,
            "has_meeting": meeting_ready,
            "is_ready": overall_ready,
            # Enriched reports
            "presentation": {
                "ready": pres_ready,
                "reason": pres_reason,
                "asset_id": pres_asset.id if pres_asset else None,
                "name": getattr(pres_asset, "name", None) if pres_asset else None
            },
            "employees": {
                "ready": emp_ready,
                "reason": emp_reason,
                "asset_id": emp_asset.id if emp_asset else None,
                "name": getattr(emp_asset, "name", None) if emp_asset else None
            },
            "script": {
                "ready": script_ready,
                "reason": script_reason
            },
            "questions": {
                "ready": questions_ready,
                "reason": questions_reason
            },
            "audio": {
                "ready": audio_ready,
                "reason": audio_reason
            },
            "meeting": {
                "ready": meeting_ready,
                "reason": meeting_reason,
                "configured": meeting_configured,
                "teams_url": getattr(meeting, "teams_url", None) if meeting else None
            },
            "missing_components": missing
        }

runtime_readiness_service = RuntimeReadinessService()
