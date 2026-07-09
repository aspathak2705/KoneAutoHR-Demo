from pptx.slide import Slide

def extract_slide_notes(slide: Slide) -> str:
    """
    Extracts speaker notes text from a slide.
    """
    if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
        notes = slide.notes_slide.notes_text_frame.text.strip()
        # Filter out default placeholder texts if any
        if notes and not notes.startswith("Click to edit Speaker notes"):
            return notes
    return ""
