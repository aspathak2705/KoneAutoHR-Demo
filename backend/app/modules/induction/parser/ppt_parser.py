from pathlib import Path
from pptx import Presentation
from app.modules.induction.parser.slide_extractor import extract_slide_text
from app.modules.induction.parser.notes_extractor import extract_slide_notes
from app.modules.induction.parser.media_extractor import extract_slide_media

def parse_presentation(ppt_path: str, session_dir: Path) -> list[dict]:
    """
    Parses PPTX file and extracts slides text, speaker notes, and embedded assets.
    """
    prs = Presentation(ppt_path)
    slides_knowledge = []

    for idx, slide in enumerate(prs.slides):
        slide_number = idx + 1
        title, content = extract_slide_text(slide)
        notes = extract_slide_notes(slide)
        images, videos = extract_slide_media(slide, slide_number, session_dir)

        slides_knowledge.append({
            "slide_number": slide_number,
            "title": title,
            "content": content,
            "speaker_notes": notes or None,
            "images": images,
            "videos": [v["filename"] for v in videos]  # Just keep list of filenames for schema
        })

    return slides_knowledge
