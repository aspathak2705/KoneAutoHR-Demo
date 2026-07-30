import os
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.parser.presentation_parser import presentation_parser
from app.modules.induction.parser.employee_parser import employee_parser
from app.modules.induction.package.asset_manager import asset_manager

class ParsingPipeline:
    def execute(
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
        Executes presentation and employee parsing, registers slide image assets in the database.
        Returns:
            dict: {"slides": slide_data, "employees": employee_data}
        """
        # 1. Parse Presentation
        slides = presentation_parser.parse_deck(ppt_path, session_dir)
        
        # Build V0.1 slide presentation assets (images, fingerprints, metadata)
        from app.services.presentation_service import PresentationAssetBuilder
        try:
            asset_builder = PresentationAssetBuilder()
            asset_builder.build_assets(session_id, ppt_path)
        except Exception as e:
            logger.error(f"ParsingPipeline | Failed to build V0.1 slide presentation assets: {e}")
        
        # 2. Register Slide Images in Database
        for s in slides:
            registered_images = []
            for img_file in s["images"]:
                img_rel = f"sessions/{session_id}/slides/{img_file}"
                img_path = session_dir / "slides" / img_file
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
            s["images"] = registered_images

        # 3. Parse Employees
        employees = employee_parser.parse_employees(excel_path)

        return {
            "slides": slides,
            "employees": employees
        }

parsing_pipeline = ParsingPipeline()
