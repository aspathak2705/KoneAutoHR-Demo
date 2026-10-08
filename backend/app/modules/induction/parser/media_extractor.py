import os
import io
import struct
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from loguru import logger
from pptx.slide import Slide
from pptx.enum.shapes import MSO_SHAPE_TYPE


def extract_mp4_duration(data: bytes) -> Optional[float]:
    """
    Parses MP4/MOV container in-memory to extract exact media duration from 'mvhd' atom.
    Avoids external ffmpeg/ffprobe binary dependencies.
    """
    f = io.BytesIO(data)

    def parse_box(end_pos: int) -> Optional[float]:
        while f.tell() < end_pos:
            header = f.read(8)
            if len(header) < 8:
                break
            size, atom_type = struct.unpack(">I4s", header)
            start = f.tell()
            actual_size = size - 8
            if size == 1:
                large_size_bytes = f.read(8)
                if len(large_size_bytes) < 8:
                    break
                actual_size = struct.unpack(">Q", large_size_bytes)[0] - 16
            elif size == 0:
                actual_size = end_pos - start

            if atom_type in [b"moov", b"trak", b"mdia"]:
                res = parse_box(start + actual_size)
                if res is not None:
                    return res
            elif atom_type == b"mvhd":
                ver_flags = f.read(4)
                if len(ver_flags) < 4:
                    break
                version = ver_flags[0]
                if version == 1:
                    data_box = f.read(28)
                    if len(data_box) >= 28:
                        timescale, duration = struct.unpack(">IQ", data_box[16:28])
                        if timescale > 0:
                            return round(duration / float(timescale), 2)
                else:
                    data_box = f.read(16)
                    if len(data_box) >= 16:
                        timescale, duration = struct.unpack(">II", data_box[8:16])
                        if timescale > 0:
                            return round(duration / float(timescale), 2)
            else:
                f.seek(start + actual_size)
        return None

    try:
        return parse_box(len(data))
    except Exception as e:
        logger.debug(f"MediaExtractor | MP4 atom parsing error: {e}")
        return None


def get_shape_playback_mode(slide: Slide, shape_id: int) -> Tuple[str, bool, bool]:
    """
    Determines playback mode from slide timing XML.
    Returns: (playback_mode, autoplay, on_click)
    Defaults to ('auto', True, False) for automatic embedded playback.
    """
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    timing = slide._element.find("p:timing", ns)
    if timing is None:
        return "auto", True, False

    # Check for clickEffect or interactive sequence targeting this shape
    spid_str = str(shape_id)
    click_nodes = timing.findall(".//*[@nodeType='clickEffect']", ns)
    for cn in click_nodes:
        sp_tgt = cn.find(".//p:spTgt", ns)
        if sp_tgt is not None and sp_tgt.get("spid") == spid_str:
            return "on_click", False, True

    # Check command calls
    cmds = timing.findall(".//p:cmd", ns)
    for cmd in cmds:
        sp_tgt = cmd.find(".//p:spTgt", ns)
        if sp_tgt is not None and sp_tgt.get("spid") == spid_str:
            parent_par = cmd.find("...", ns)
            # If delay is indefinite, it's typically click-triggered
            conds = cmd.findall(".//p:cond", ns)
            for c in conds:
                if c.get("delay") == "indefinite":
                    return "on_click", False, True

    return "auto", True, False


def extract_slide_media(slide: Slide, slide_number: int, session_dir: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Extracts images and detects embedded/linked videos in a slide with duration and playback mode.
    Returns:
        tuple[list[str], list[dict]]: (list_of_image_filenames, list_of_video_metadata)
    """
    images_dir = session_dir / "slides"
    images_dir.mkdir(parents=True, exist_ok=True)

    videos_dir = session_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    image_paths: List[str] = []
    videos: List[Dict[str, Any]] = []

    image_count = 0
    video_count = 0

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
                pass

        # 2. Video shape detection (MEDIA = 16 or 26)
        elif shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
            video_count += 1
            video_name = getattr(shape, "name", f"video_slide_{slide_number}_{video_count}") or f"video_{slide_number}"
            shape_id = getattr(shape, "shape_id", 0)

            # Determine playback mode
            playback_mode, autoplay, on_click = get_shape_playback_mode(slide, shape_id)

            # Extract media binary and duration from relationship part if available
            duration: Optional[float] = None
            embedded = True
            filename = f"{video_name}.mp4"

            try:
                # Find media relationship
                for rel in slide.part.rels.values():
                    if "media" in getattr(rel, "reltype", "") or "video" in getattr(rel, "reltype", ""):
                        target_part = getattr(rel, "target_part", None)
                        if target_part and hasattr(target_part, "blob"):
                            media_blob = target_part.blob
                            if media_blob:
                                duration = extract_mp4_duration(media_blob)
                                if duration is not None:
                                    break
            except Exception as ex:
                logger.debug(f"MediaExtractor | Media part inspect notice: {ex}")

            # Safe duration fallback
            if duration is None:
                duration_status = "UNKNOWN"
            else:
                duration_status = "KNOWN"

            video_meta = {
                "media_id": f"s{slide_number}_v{video_count}",
                "slide_number": slide_number,
                "shape_id": shape_id,
                "filename": filename,
                "duration": duration,
                "duration_status": duration_status,
                "playback_mode": playback_mode,
                "autoplay": autoplay,
                "on_click": on_click,
                "embedded": embedded,
                "supported": autoplay and not on_click,
                "reason": (
                    "Ready for automatic presentation"
                    if (autoplay and not on_click)
                    else "On-click video requires manual playback and is not supported by automatic presentation mode."
                ),
            }
            videos.append(video_meta)
            logger.info(
                f"MediaExtractor | Slide {slide_number} video detected: {filename} "
                f"(duration: {duration}s, mode: {playback_mode}, supported: {video_meta['supported']})"
            )

    return image_paths, videos
