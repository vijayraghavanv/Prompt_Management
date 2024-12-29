from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, Project, ProjectStatus
from app.services.project import ProjectService
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=Project, status_code=201)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db)
):
    """Create a new project"""
    service = ProjectService(db)
    return service.create_project(project)

@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: int = Path(..., title="The ID of the project to get", ge=1),
    db: Session = Depends(get_db)
):
    """Get a specific project by ID"""
    service = ProjectService(db)
    return service.get_project(project_id)

@router.get("/", response_model=List[Project])
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[ProjectStatus] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List projects with optional filtering"""
    service = ProjectService(db)
    return service.get_projects(skip=skip, limit=limit, status=status, tag=tag)

@router.put("/{project_id}", response_model=Project)
def update_project(
    project_id: int = Path(..., title="The ID of the project to update", ge=1),
    project: ProjectUpdate = None,
    db: Session = Depends(get_db)
):
    """Update a project"""
    service = ProjectService(db)
    return service.update_project(project_id, project)

@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int = Path(..., title="The ID of the project to delete", ge=1),
    db: Session = Depends(get_db)
):
    """Delete a project"""
    service = ProjectService(db)
    service.delete_project(project_id)

@router.post("/{project_id}/increment-prompt", response_model=Project)
def increment_prompt_count(
    project_id: int = Path(..., title="The ID of the project to increment prompt count", ge=1),
    db: Session = Depends(get_db)
):
    """Increment the prompt count for a project"""
    service = ProjectService(db)
    return service.increment_prompt_count(project_id)
