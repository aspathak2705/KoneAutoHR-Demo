import json
import datetime
from pathlib import Path

class VerificationPipeline:
    def execute(
        self,
        session_id: str,
        session_dir: Path,
        slides_data: list,
        employee_profiles: list,
        presenter_profile: dict,
        script_data: dict,
        audio_manifest: dict
    ) -> dict:
        """
        Performs thorough validation checks on the prepared assets, scripts, audios, and metadata.
        Outputs validation_report.json.
        """
        report_path = session_dir / "validation_report.json"
        
        errors = []
        checks = {}

        # 1. Slides parsed
        slides_valid = len(slides_data) > 0
        checks["slides_parsed"] = slides_valid
        if not slides_valid:
            errors.append("No presentation slides parsed.")

        # 2. Employee sheet valid
        employees_valid = len(employee_profiles) > 0
        checks["employees_valid"] = employees_valid
        if not employees_valid:
            errors.append("No employee profiles parsed.")

        # 3. Presenter profile loaded
        presenter_valid = presenter_profile and bool(presenter_profile.get("ai_trainer_name"))
        checks["presenter_profile_loaded"] = presenter_valid
        if not presenter_valid:
            errors.append("AI Presenter profile not loaded.")

        # 4. Script complete
        script_complete = script_data and "welcome_flow" in script_data and "slide_narrations" in script_data and "closing_script" in script_data
        checks["script_complete"] = script_complete
        if not script_complete:
            errors.append("AI presentation script structure is incomplete.")

        # 5. Every slide mapped to script
        slides_mapped = True
        if slides_valid and script_complete:
            slide_nums = [s["slide_number"] for s in slides_data]
            narrations = script_data.get("slide_narrations", {})
            for num in slide_nums:
                if str(num) not in narrations and num not in narrations:
                    slides_mapped = False
                    errors.append(f"Missing narration script for Slide {num}.")
        checks["every_slide_mapped"] = slides_mapped

        # 6. Every audio generated and hashes match
        audios_valid = True
        audio_tracks = audio_manifest.get("tracks", []) if audio_manifest else []
        
        # Check if new deterministic unified narration format is used
        is_unified = (len(audio_tracks) == 1 and audio_tracks[0].get("filename") == "narration.wav")
        
        if is_unified:
            # Validate the single narration track
            track = audio_tracks[0]
            file_path = session_dir / "audio" / track["filename"]
            if not file_path.exists():
                audios_valid = False
                errors.append(f"Physical narration audio file missing: {track['filename']}")
        else:
            expected_audio_labels = []
            welcome_flow = script_data.get("welcome_flow", {}) if isinstance(script_data, dict) else {}
            if isinstance(welcome_flow, dict):
                if welcome_flow.get("greeting"):
                    expected_audio_labels.append("greeting")
                if welcome_flow.get("summary"):
                    expected_audio_labels.append("intro")
                    
            closing_script = script_data.get("closing_script", {}) if isinstance(script_data, dict) else {}
            if isinstance(closing_script, dict):
                if closing_script.get("summary"):
                    expected_audio_labels.append("closing")
            elif isinstance(closing_script, str) and closing_script:
                expected_audio_labels.append("closing")
                
            for s in slides_data:
                expected_audio_labels.append(f"slide_{s['slide_number']}")

            track_labels = {t["label"] for t in audio_tracks}
            for label in expected_audio_labels:
                if label not in track_labels:
                    audios_valid = False
                    errors.append(f"Missing generated audio track for label: {label}")

        # Check physical files and checksums
        if audios_valid:
            for track in audio_tracks:
                file_path = session_dir / "audio" / track["filename"]
                if not file_path.exists():
                    audios_valid = False
                    errors.append(f"Physical audio file missing: {track['filename']}")

        checks["every_audio_generated"] = audios_valid

        # Overall Status
        passed = len(errors) == 0

        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session_id": session_id,
            "verification_passed": passed,
            "checks": checks,
            "errors": errors
        }

        # Write validation_report.json (which sits inside package folder)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        if not passed:
            raise ValueError(f"Verification Pipeline failed checks: {', '.join(errors)}")

        return report

verification_pipeline = VerificationPipeline()
