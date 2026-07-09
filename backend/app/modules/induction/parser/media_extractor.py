import os
from pathlib import Path
from pptx.slide import Slide
from pptx.enum.shapes import MSO_SHAPE_TYPE

def extract_slide_media(slide: Slide, slide_number: int, session_dir: Path) -> tuple[list[str], list[dict]]:
    """
    Extracts images and detects embedded videos in a slide.
    Returns:
        tuple[list[str], list[dict]]: (list_of_image_filenames, list_of_video_metadata)
    """
    images_dir = session_dir / "slides"
    images_dir.mkdir(parents=True, exist_ok=True)

    videos_dir = session_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []
    videos = []

    image_count = 0
    for shape in slide.shapes:
        # 1. Image extraction
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            image_count += 1
            image = shape.image
            ext = image.ext  # e.g., 'png', 'jpeg'
            img_filename = f"slide_{slide_number}_img_{image_count}.{ext}"
            img_path = images_dir / img_filename

            try:
                with open(img_path, "wb") as f:
                    f.write(image.blob)
                image_paths.append(img_filename)
            except Exception:
                # Silently skip if image extraction fails
                pass

        # 2. Video shape detection (MEDIA = 16 or 26)
        elif shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
            video_name = getattr(shape, "name", f"video_slide_{slide_number}") or "video"
            video_meta = {
                "filename": f"{video_name}.mp4",
                "slide_number": slide_number,
                "duration": None,
                "playback_position": "auto"
            }
            videos.append(video_meta)

    return image_paths, videos
