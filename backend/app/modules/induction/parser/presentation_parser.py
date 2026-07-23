from pathlib import Path
from pptx import Presentation
from app.modules.induction.parser.slide_extractor import extract_slide_text
from app.modules.induction.parser.notes_extractor import extract_slide_notes
from app.modules.induction.parser.media_extractor import extract_slide_media

class PresentationParser:
    def parse_deck(self, ppt_path: str, session_dir: Path) -> list[dict]:
        """
        Parses PPTX file and returns detailed slide info dictionary.
        """
        prs = Presentation(ppt_path)
        slides = []

        for idx, slide in enumerate(prs.slides):
            slide_number = idx + 1
            title, content = extract_slide_text(slide)
            notes = extract_slide_notes(slide)
            images, videos = extract_slide_media(slide, slide_number, session_dir)

            slides.append({
                "slide_number": slide_number,
                "title": title,
                "content": content,
                "speaker_notes": notes or None,
                "images": images,
                "videos": [v["filename"] for v in videos],
                "has_video": len(videos) > 0
            })

        return slides

presentation_parser = PresentationParser()
