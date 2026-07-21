from sqlalchemy.orm import Session as DBSession
from typing import List
from app.repositories.session_repository import session_repository
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate
from app.services.presentation_job_service import presentation_job_service
from app.services.storage_service import storage_service
from app.core.exceptions import SessionNotFoundException

class SessionService:
    def create_session(self, db: DBSession, session_in: SessionCreate) -> Session:
        session = session_repository.create(db, session_in)
        storage_service.create_session_directories(session.id)
        
        # Copy presentation file if linked
        if session.presentation_id:
            from app.repositories.presentation_repository import presentation_repository
            from app.core.constants import UploadType
            from pathlib import Path
            import shutil
            import datetime
            
            pres = presentation_repository.get(db, session.presentation_id)
            if pres:
                presentation_repository.update(
                    db, pres, 
                    last_used=datetime.datetime.now(), 
                    session_count=pres.session_count + 1
                )
                target_dir = storage_service.get_session_upload_dir(session.id, UploadType.PRESENTATION)
                dest = target_dir / Path(pres.storage_path).name
                shutil.copy2(pres.storage_path, dest)
                
        # Copy employee list file if linked
        if session.employee_list_id:
            from app.repositories.employee_list_repository import employee_list_repository
            from app.core.constants import UploadType
            from pathlib import Path
            import shutil
            import datetime
            
            emp = employee_list_repository.get(db, session.employee_list_id)
            if emp:
                employee_list_repository.update(
                    db, emp, 
                    last_used=datetime.datetime.now()
                )
                target_dir = storage_service.get_session_upload_dir(session.id, UploadType.EMPLOYEE_LIST)
                dest = target_dir / Path(emp.storage_path).name
                shutil.copy2(emp.storage_path, dest)
                
        # Create presentation job record
        job = presentation_job_service.create_job(db, session.id)
        
        # If script and questions are already generated, mark job as completed immediately
        if session.presentation_id:
            from app.repositories.presentation_script_repository import presentation_script_repository
            from app.repositories.presentation_question_repository import presentation_question_repository
            from app.core.constants import JobStatus
            
            script = presentation_script_repository.get_active(db, session.presentation_id)
            questions = presentation_question_repository.get_active(db, session.presentation_id)
            if script and questions:
                presentation_job_service.update_job_status(db, job.id, JobStatus.COMPLETED, progress=1.0)
                
        return session

    def get_session(self, db: DBSession, id: str) -> Session:
        session = session_repository.get(db, id)
        if not session:
            raise SessionNotFoundException(id)
        return session

    def get_all_sessions(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[Session]:
        return session_repository.get_all(db, skip, limit)

    def update_session(self, db: DBSession, id: str, session_in: SessionUpdate) -> Session:
        session = self.get_session(db, id)  # Raises if not found
        return session_repository.update(db, session, session_in)

    def delete_session(self, db: DBSession, id: str) -> Session:
        session = self.get_session(db, id)  # Raises if not found
        storage_service.delete_session_files(id)
        return session_repository.delete(db, id)

    def validate_readiness(self, db: DBSession, session_id: str) -> dict:
        from app.services.asset_service import asset_service
        session = self.get_session(db, session_id)
        
        readiness = asset_service.validate_linked_assets_readiness(db, session_id)
        
        # Update session status if ready
        if readiness["is_ready"] and session.status == "PENDING":
            from app.schemas.session import SessionUpdate
            session_repository.update(db, session, SessionUpdate(status="READY"))
            
        return readiness

session_service = SessionService()
