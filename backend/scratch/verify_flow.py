import asyncio
import sys
import shutil
from pathlib import Path
from loguru import logger

# Add backend directory to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models.session import Session
from app.services.runtime_service import runtime_service
from app.services.presentation_service import PowerPointSlideExtractor, SlideFingerprintGenerator
from app.modules.meeting_bot.media.audio_controller import AudioController

async def test_full_induction_pipeline():
    logger.info("Audit | Starting system integration verification...")
    
    db = SessionLocal()
    temp_test_dir = Path(__file__).resolve().parent / "temp_audit"
    temp_test_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 1. Fetch latest session PPT
        sess = db.query(Session).order_by(Session.created_at.desc()).first()
        if not sess:
            logger.error("Audit | No session found in DB.")
            return

        session_id = str(sess.id)
        logger.info(f"Audit | Active Session: {session_id}")

        runtime_context = runtime_service.get_runtime_context(db, session_id)
        ppt_path = runtime_context.get("presentation", {}).get("storage_path")
        if not ppt_path or not Path(ppt_path).exists():
            logger.error(f"Audit | PPT file not found: {ppt_path}")
            return
            
        # 2. Extract slides windowed mock execution
        logger.info("Audit | Launching PowerPoint slide extractor test...")
        extractor = PowerPointSlideExtractor()
        out_slides = temp_test_dir / "slides"
        slide_count = extractor.extract_slides(ppt_path, out_slides)
        logger.info(f"Audit | PowerPoint extractor completed. Extracted {slide_count} slides.")

        # 3. Generate fingerprints
        logger.info("Audit | Launching SlideFingerprintGenerator test...")
        fp_gen = SlideFingerprintGenerator()
        fp_file = temp_test_dir / "fingerprints.json"
        fp_gen.generate_fingerprints(out_slides, fp_file)
        logger.info("Audit | SlideFingerprintGenerator completed.")

        # 4. Boot persistent PowerShell player
        logger.info("Audit | Booting persistent PowerShell player test...")
        audio = AudioController(session_id)
        # Mock preload slide narration track
        dummy_audio = temp_test_dir / "greeting.mp3"
        dummy_audio.write_bytes(b"")
        audio.preload_all_tracks()
        logger.info("Audit | PowerPoint preloader boot: SUCCESS")
        audio.stop_audio()
        
        # Shut down persistent powerpoint/powershell
        if audio._ps_process:
            audio._ps_process.terminate()
            
        logger.info("Audit | End-to-end pipeline test completed successfully with 0 errors!")
    except Exception as e:
        logger.error(f"Audit | Pipeline test encountered error: {e}")
    finally:
        db.close()
        # Cleanup
        try:
            shutil.rmtree(temp_test_dir)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(test_full_induction_pipeline())
