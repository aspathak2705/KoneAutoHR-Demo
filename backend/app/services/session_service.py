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
        session = self.get_session(db, session_id)
        
        has_presentation = session.presentation_id is not None
        has_employees = session.employee_list_id is not None
        
        from app.repositories.presentation_script_repository import presentation_script_repository
        from app.repositories.presentation_question_repository import presentation_question_repository
        from app.models.meeting import Meeting
        
        has_script = False
        if has_presentation:
            script = presentation_script_repository.get_active(db, session.presentation_id)
            has_script = script is not None and script.status == "COMPLETED"
            
        has_faq = False
        if has_presentation:
            faq = presentation_question_repository.get_active(db, session.presentation_id)
            has_faq = faq is not None and faq.status == "COMPLETED"
            
        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        has_meeting = meeting is not None
        
        # Session is fully ready if all 5 checks pass
        is_ready = has_presentation and has_employees and has_script and has_faq and has_meeting
        
        # Update session status if ready
        if is_ready and session.status == "PENDING":
            from app.schemas.session import SessionUpdate
            session_repository.update(db, session, SessionUpdate(status="READY"))
            
        return {
            "session_id": session_id,
            "has_presentation": has_presentation,
            "has_employees": has_employees,
            "has_script": has_script,
            "has_faq": has_faq,
            "has_meeting": has_meeting,
            "is_ready": is_ready
        }

session_service = SessionService()
