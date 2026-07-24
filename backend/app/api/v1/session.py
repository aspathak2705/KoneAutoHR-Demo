from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from typing import List, Any
from app.core.dependencies import get_session_service, get_uow
from app.db.unit_of_work import UnitOfWork
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse, SessionDetailResponse
from app.services.session_service import SessionService
from app.services.presentation_job_service import presentation_job_service
from app.modules.induction.services.preparation_orchestrator import preparation_orchestrator

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session_in: SessionCreate,
    uow: UnitOfWork = Depends(get_uow),
    service: SessionService = Depends(get_session_service),
):
    return service.create_session(uow.db, session_in)

@router.get("", response_model=List[SessionResponse])
def read_sessions(
    skip: int = 0,
    limit: int = 100,
    uow: UnitOfWork = Depends(get_uow),
    service: SessionService = Depends(get_session_service),
):
    return service.get_all_sessions(uow.db, skip=skip, limit=limit)

@router.get("/{id}", response_model=SessionDetailResponse)
def read_session(
    id: str,
    uow: UnitOfWork = Depends(get_uow),
    service: SessionService = Depends(get_session_service),
):
    return service.get_session(uow.db, id)

@router.put("/{id}", response_model=SessionResponse)
def update_session(
    id: str,
    session_in: SessionUpdate,
    uow: UnitOfWork = Depends(get_uow),
    service: SessionService = Depends(get_session_service),
):
    return service.update_session(uow.db, id, session_in)

@router.delete("/{id}", response_model=SessionResponse)
def delete_session(
    id: str,
    uow: UnitOfWork = Depends(get_uow),
    service: SessionService = Depends(get_session_service),
):
    return service.delete_session(uow.db, id)

@router.post("/{id}/generate-script")
async def trigger_script_generation(
    id: str,
    background_tasks: BackgroundTasks,
    uow: UnitOfWork = Depends(get_uow)
):
    # 1. Check if job already exists, delete/recreate if failed/completed
    db = uow.db
    job = presentation_job_service.get_job_by_session(db, session_id=id, job_type="SCRIPT")
    if job:
        presentation_job_service.update_job_status(db, job.id, status="PENDING", progress=0.0, error_message=None)
    else:
        job = presentation_job_service.create_job(db, session_id=id, job_type="SCRIPT")
        
    background_tasks.add_task(preparation_orchestrator.run_script_generation, id, job.id)
    return {"message": "Script generation pipeline started.", "job_id": job.id, "job_type": "SCRIPT"}

@router.post("/{id}/generate-audio")
async def trigger_audio_generation(
    id: str,
    background_tasks: BackgroundTasks,
    uow: UnitOfWork = Depends(get_uow)
):
    # 1. Check if job already exists
    db = uow.db
    job = presentation_job_service.get_job_by_session(db, session_id=id, job_type="AUDIO")
    if job:
        presentation_job_service.update_job_status(db, job.id, status="PENDING", progress=0.0, error_message=None)
    else:
        job = presentation_job_service.create_job(db, session_id=id, job_type="AUDIO")

    background_tasks.add_task(preparation_orchestrator.run_audio_generation, id, job.id)
    return {"message": "Audio generation pipeline started.", "job_id": job.id, "job_type": "AUDIO"}

@router.post("/{id}/generate-package")
async def trigger_package_generation(
    id: str,
    background_tasks: BackgroundTasks,
    uow: UnitOfWork = Depends(get_uow)
):
    db = uow.db
    # Check if package job already exists
    job = presentation_job_service.get_job_by_session(db, session_id=id, job_type="PACKAGE")
    if job:
        presentation_job_service.update_job_status(db, job.id, status="PENDING", progress=0.0, error_message=None)
    else:
        job = presentation_job_service.create_job(db, session_id=id, job_type="PACKAGE")
        
    # Also reset verification job
    ver_job = presentation_job_service.get_job_by_session(db, session_id=id, job_type="VERIFICATION")
    if ver_job:
        presentation_job_service.update_job_status(db, ver_job.id, status="PENDING", progress=0.0, error_message=None)
    else:
        ver_job = presentation_job_service.create_job(db, session_id=id, job_type="VERIFICATION")

    background_tasks.add_task(preparation_orchestrator.run_package_generation, id, job.id)
    return {"message": "Packaging pipeline started.", "job_id": job.id, "job_type": "PACKAGE"}

@router.get("/{id}/jobs")
def get_session_jobs(id: str, uow: UnitOfWork = Depends(get_uow)):
    jobs = presentation_job_service.get_all_jobs_by_session(uow.db, id)
    return [{"id": j.id, "job_type": j.job_type, "status": j.status, "progress": j.progress, "error_message": j.error_message} for j in jobs]