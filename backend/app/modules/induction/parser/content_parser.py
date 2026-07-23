from pathlib import Path
from pptx import Presentation
from app.modules.induction.parser.slide_extractor import extract_slide_text
from app.modules.induction.parser.notes_extractor import extract_slide_notes
from app.modules.induction.parser.media_extractor import extract_slide_media
from app.modules.induction.package.asset_manager import asset_manager
from sqlalchemy.orm import Session as DBSession

class ContentParser:
    def parse_deck(self, db: DBSession, presentation_id: str, ppt_path: str, session_id: str) -> list[dict]:
        """
        Parses PPTX file and extracts slides text, speaker notes, and embedded assets.
        Saves and registers extracted media files.
        """
        prs = Presentation(ppt_path)
        slides_knowledge = []

        # Target session directory structure
        session_folder = Path("sessions") / session_id
        
        for idx, slide in enumerate(prs.slides):
            slide_number = idx + 1
            title, content = extract_slide_text(slide)
            notes = extract_slide_notes(slide)
            
            # Temporary extraction path to run checks
            images, videos = extract_slide_media(slide, slide_number, Path("uploads") / "sessions" / session_id)

            # Register extracted images as database assets via AssetManager
            registered_images = []
            for img_file in images:
                img_rel = f"sessions/{session_id}/slides/{img_file}"
                img_path = Path("uploads") / img_rel
                if img_path.exists():
                    with open(img_path, "rb") as f:
                        img_data = f.read()
                    asset = asset_manager.save_and_register_asset(
                        db=db,
                        presentation_id=presentation_id,
                        relative_path=img_rel,
                        content=img_data,
                        asset_type="image"
                    )
                    registered_images.append(img_file)

            # Register video shapes
            registered_videos = []
            for v_meta in videos:
                registered_videos.append(v_meta["filename"])

            slides_knowledge.append({
                "slide_number": slide_number,
                "title": title,
                "content": content,
                "speaker_notes": notes or None,
                "images": registered_images,
                "videos": registered_videos,
                "has_video": len(videos) > 0
            })

        return slides_knowledge

content_parser = ContentParser()
