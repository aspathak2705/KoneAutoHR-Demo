import json
import datetime
import shutil
from pathlib import Path
from app.modules.induction.package.schema import PackageManifest, RuntimeMetadataEntry, PresentationPackage

class PackageBuilder:
    def build_package(
        self,
        session_id: str,
        session_dir: Path,
        structured_context: dict,
        script_data: dict,
        audio_manifest: dict,
        validation_report: dict
    ) -> PresentationPackage:
        """
        Assembles all generated artifacts (manifest, script, audio manifest, runtime metadata, validation report)
        using the PresentationPackage domain model structure and serializes them to disk.
        """
        assets_dir = session_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # 1. Copy slide images to package assets directory
        slides_src = session_dir / "slides"
        if slides_src.exists():
            for img_file in slides_src.glob("*"):
                shutil.copy(img_file, assets_dir / img_file.name)

        # 2. Compile audio tracks
        audio_tracks = audio_manifest.get("tracks", [])
        voice = audio_tracks[0]["voice"] if len(audio_tracks) > 0 else "en-US-AriaNeural"

        # 3. Create RuntimeMetadataEntry domain models
        metadata_entries = []
        
        # Opening greeting
        greeting_track = next((t for t in audio_tracks if t["label"] == "greeting"), None)
        metadata_entries.append(RuntimeMetadataEntry(
            slide_id="greeting",
            audio_file=greeting_track["path"] if greeting_track else None,
            duration=greeting_track["duration"] if greeting_track else 4.5,
            start_delay=0.0,
            expected_slide=0,
            contains_video=False,
            pause_points=[],
            hash=greeting_track["checksum"] if greeting_track else "",
            version=greeting_track["version"] if greeting_track else 1,
            language=structured_context["session"]["language"],
            voice=voice,
            generation_time=datetime.datetime.now().isoformat()
        ))
        
        # Opening intro
        intro_track = next((t for t in audio_tracks if t["label"] == "intro"), None)
        metadata_entries.append(RuntimeMetadataEntry(
            slide_id="intro",
            audio_file=intro_track["path"] if intro_track else None,
            duration=intro_track["duration"] if intro_track else 3.5,
            start_delay=0.5,
            expected_slide=0,
            contains_video=False,
            pause_points=[],
            hash=intro_track["checksum"] if intro_track else "",
            version=intro_track["version"] if intro_track else 1,
            language=structured_context["session"]["language"],
            voice=voice,
            generation_time=datetime.datetime.now().isoformat()
        ))

        # Slides
        for s in structured_context["presentation"]["slides"]:
            slide_num = s["slide_number"]
            label = f"slide_{slide_num}"
            track = next((t for t in audio_tracks if t["label"] == label), None)
            
            metadata_entries.append(RuntimeMetadataEntry(
                slide_id=f"slide_{slide_num}",
                audio_file=track["path"] if track else None,
                duration=track["duration"] if track else 3.0,
                start_delay=1.0,
                expected_slide=slide_num,
                contains_video=s["has_video"],
                pause_points=[2.5] if s["has_video"] else [],
                hash=track["checksum"] if track else "",
                version=track["version"] if track else 1,
                language=structured_context["session"]["language"],
                voice=voice,
                generation_time=datetime.datetime.now().isoformat()
            ))

        # Closing
        closing_track = next((t for t in audio_tracks if t["label"] == "closing"), None)
        metadata_entries.append(RuntimeMetadataEntry(
            slide_id="closing",
            audio_file=closing_track["path"] if closing_track else None,
            duration=closing_track["duration"] if closing_track else 3.5,
            start_delay=0.5,
            expected_slide=99,
            contains_video=False,
            pause_points=[],
            hash=closing_track["checksum"] if closing_track else "",
            version=closing_track["version"] if closing_track else 1,
            language=structured_context["session"]["language"],
            voice=voice,
            generation_time=datetime.datetime.now().isoformat()
        ))

        # 4. Create PackageManifest domain model
        manifest = PackageManifest(
            package_version="1.0.0",
            creation_time=datetime.datetime.now().isoformat(),
            session_id=session_id,
            presentation_version=1,
            assets=[
                {
                    "type": "presentation",
                    "id": structured_context["session"].get("presentation_id"),
                    "name": "presentation"
                }
            ],
            checksums={t["filename"]: t["checksum"] for t in audio_tracks},
            generation_status="READY",
            runtime_version="0.1.0"
        )

        # 5. Create PresentationPackage domain model
        package = PresentationPackage(
            manifest=manifest,
            session_script=script_data,
            audio_manifest=audio_manifest,
            runtime_metadata=metadata_entries,
            validation_report=validation_report,
            assets_dir=str(assets_dir.resolve())
        )

        # 6. Serialize package outputs to disk
        with open(session_dir / "manifest.json", "w", encoding="utf-8") as f:
            f.write(package.manifest.model_dump_json(indent=2))

        with open(session_dir / "session_script.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(package.session_script, indent=2))

        with open(session_dir / "audio_manifest.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(package.audio_manifest, indent=2))

        with open(session_dir / "runtime_metadata.json", "w", encoding="utf-8") as f:
            f.write(json.dumps([m.model_dump() for m in package.runtime_metadata], indent=2))

        with open(session_dir / "validation_report.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(package.validation_report, indent=2))

        # Ensure compatibility fallback file induction_package.json is generated
        induction_package_path = session_dir / "induction_package.json"
        compat_package = {
            "session_metadata": structured_context["session"],
            "meeting_context": structured_context["presenter_profile"],
            "ai_persona": script_data.get("ai_persona", {}),
            "employee_profiles": structured_context["audience"]["profiles"],
            "welcome_flow": script_data.get("welcome_flow", {}),
            "slide_narrations": script_data.get("slide_narrations", {}),
            "faq": script_data.get("faq", []),
            "closing_script": script_data.get("closing_script", {}),
            "audio_metadata": audio_tracks
        }
        with open(induction_package_path, "w", encoding="utf-8") as f:
            json.dump(compat_package, f, indent=2)

        return package

package_builder = PackageBuilder()
