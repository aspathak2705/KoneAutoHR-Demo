import os
import shutil
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.parser.presentation_parser import presentation_parser
from app.modules.induction.parser.employee_parser import employee_parser
from app.modules.induction.package.asset_manager import asset_manager

class ParsingPipeline:
    async def execute(
        self,
        db: DBSession,
        presentation_id: str,
        ppt_path: str,
        employee_list_id: str,
        excel_path: str,
        session_id: str,
        session_dir: Path
    ) -> dict:
        """
        Executes Phase 1 Preparation:
        Validate -> Extract PPT -> Generate Script -> Generate Narration -> Generate Timeline -> Generate Manifest.
        """
        logger.info(f"ParsingPipeline | Beginning deterministic package preparation for session {session_id}")

        # 1. Validate files
        ppt_file_path = Path(ppt_path)
        excel_file_path = Path(excel_path)
        if not ppt_file_path.exists():
            raise FileNotFoundError(f"PowerPoint file not found: {ppt_path}")
        if not excel_file_path.exists():
            raise FileNotFoundError(f"Excel employee list file not found: {excel_path}")

        # Ensure session PPTX copy exists (Phase 2 Session Directory spec)
        session_ppt_copy = session_dir / "presentation.pptx"
        if not session_ppt_copy.exists():
            shutil.copy2(ppt_file_path, session_ppt_copy)
            logger.info(f"ParsingPipeline | Copied presentation deck to {session_ppt_copy}")

        # 2. Extract PPT
        slides = presentation_parser.parse_deck(str(session_ppt_copy), session_dir)
        
        # Build slide image thumbnails
        from app.services.presentation_service import PowerPointSlideExtractor, SlideFingerprintGenerator
        slides_dir = session_dir / "presentation_assets" / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        
        extractor = PowerPointSlideExtractor()
        slide_count = extractor.extract_slides(str(session_ppt_copy), slides_dir)
        
        # Generate perceptual fingerprints
        fingerprints_file = session_dir / "presentation_assets" / "fingerprints.json"
        fingerprint_gen = SlideFingerprintGenerator()
        fingerprint_gen.generate_fingerprints(slides_dir, fingerprints_file)

        # 3. Parse Employees & Build Context
        employees = employee_parser.parse_employees(str(excel_file_path))
        
        from app.models.session import Session
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found in database.")

        from app.modules.induction.context.context_builder import context_builder
        structured_context = context_builder.build_context(db, session, slides, employees)

        # 4. Generate AI Script
        from app.modules.induction.services.script_pipeline import script_pipeline
        scripts = await script_pipeline.execute(db, structured_context, session_dir)
        
        # Save script.md
        from app.services.presentation_service import export_script_to_md
        export_script_to_md(scripts, session_dir / "script.md")
        logger.info(f"ParsingPipeline | Saved presentation script to {session_dir / 'script.md'}")

        logger.info(f"ParsingPipeline | Script generation completed successfully for session {session_id}")

        return {
            "slides": slides,
            "employees": employees,
            "slide_count": slide_count
        }

parsing_pipeline = ParsingPipeline()

