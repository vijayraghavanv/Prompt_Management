from typing import List, Optional, Sequence, Union

from fastapi import APIRouter, Depends, Path, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.prompt import Prompt, PromptCreate, PromptUpdate, PromptStatus, PromptVersion
from app.services.project import ProjectService
from app.services.prompt import PromptService

router = APIRouter()

@router.post("/", response_model=Prompt, status_code=201)
def create_prompt(
    prompt: PromptCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new prompt.

    This endpoint creates a new prompt with the specified configuration.
    
    Important Notes:
    - Variable Types:
        - Supports 'string' and 'image' variable types
        - If using an image variable, it must be the only variable in the prompt
        - Cannot mix image and string variables in the same prompt
    
    Args:
        prompt (PromptCreate): The prompt configuration
            - name: Unique name within project (3-100 chars, alphanumeric with _ - .)
            - description: Optional description
            - content: The prompt template (10-10000 chars)
            - project_id: ID of the project this prompt belongs to
            - variables: List of variables used in the prompt
                - name: Variable name (alphanumeric with _)
                - description: Optional description
                - required: Whether variable is required (default: true)
                - type: Variable type ('string' or 'image')
            - max_tokens: Maximum tokens in response (1-4000)
            - temperature: Response randomness (0-1, default: 0.7)
            - status: Prompt status (default: 'draft')
            - output_schema: Optional JSON schema for structured output
    
    Returns:
        Prompt: The created prompt object

    Raises:
        422: Validation Error
            - If variable types are mixed (image + string)
            - If multiple variables when using image type
            - If variable names are invalid
            - If other validation rules are violated
        404: Project not found
        500: Database error
    """
    service = PromptService(db)
    return service.create(prompt)

@router.get("/{prompt_id}", response_model=Prompt)
def get_prompt(
    prompt_id: int = Path(..., title="The ID of the prompt to get", ge=1),
    db: Session = Depends(get_db)
):
    """Get a specific prompt by ID"""
    service = PromptService(db)
    prompt = service.get(prompt_id)
    if not prompt:
        raise NotFoundError(detail=f"Prompt {prompt_id} not found")
    return prompt

@router.get("/project/{project_id}", response_model=List[Prompt])
def list_project_prompts(
    project_id: int = Path(..., title="The ID of the project to get prompts for", ge=1),
    status: Optional[PromptStatus] = None,
    db: Session = Depends(get_db)
):
    """List all prompts for a project with optional status filter"""
    # Verify project exists
    project_service = ProjectService(db)
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError(detail=f"Project {project_id} not found")
    
    service = PromptService(db)
    prompts = service.get_by_project(project_id)
    
    # Filter by status if provided
    if status:
        prompts = [p for p in prompts if p.status == status]
    
    return prompts

@router.put("/{prompt_id}", response_model=Prompt)
def update_prompt(
    prompt_id: int = Path(..., title="The ID of the prompt to update", ge=1),
    prompt: PromptUpdate = None,
    db: Session = Depends(get_db)
):
    """Update a prompt"""
    service = PromptService(db)
    return service.update(prompt_id, prompt)

@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(
    prompt_id: int = Path(..., title="The ID of the prompt to delete", ge=1),
    db: Session = Depends(get_db)
):
    """Delete a prompt"""
    service = PromptService(db)
    service.delete(prompt_id)

@router.get("/{prompt_id}/versions", response_model=List[PromptVersion])
def list_prompt_versions(
    prompt_id: int = Path(..., title="The ID of the prompt to get versions for", ge=1),
    db: Session = Depends(get_db)
):
    """List all versions of a prompt"""
    service = PromptService(db)
    return service.get_versions(prompt_id)

@router.get("/{prompt_id}/version/{version}", response_model=PromptVersion)
def get_prompt_version(
    prompt_id: int = Path(..., title="The ID of the prompt", ge=1),
    version: int = Path(..., title="The version number to get", ge=1),
    db: Session = Depends(get_db)
):
    """Get a specific version of a prompt"""
    service = PromptService(db)
    prompt_version = service.get_version(prompt_id, version)
    if not prompt_version:
        raise NotFoundError(detail=f"Version {version} of prompt {prompt_id} not found")
    
    # Add prompt details to version
    prompt = service.get(prompt_id)
    prompt_version.prompt_name = prompt.name
    prompt_version.prompt_description = prompt.description
    prompt_version.project_id = prompt.project_id
    
    return prompt_version

@router.post("/{prompt_id}/publish", response_model=Prompt)
def publish_prompt(
    prompt_id: int = Path(..., title="The ID of the prompt to publish", ge=1),
    db: Session = Depends(get_db)
):
    """Publish a prompt"""
    service = PromptService(db)
    return service.publish(prompt_id)
