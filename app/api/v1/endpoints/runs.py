from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.run_service import RunService
from app.schemas.run import Run, RunCreate
from app.core.exceptions import AppException, NotFoundError, ValidationError

router = APIRouter(
    tags=["runs"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    }
)

@router.post("", response_model=Run, status_code=201)
def create_run(
    *,
    run_in: RunCreate = Body(
        ...,
        examples={
            "normal": {
                "summary": "A normal example",
                "description": "Create a run with text input",
                "value": {
                    "prompt_id": 1,
                    "project_id": 1,
                    "input_variables": {"text": "What is machine learning?"},
                    "structured_output": False
                }
            },
            "structured": {
                "summary": "Structured output example",
                "description": "Create a run with structured output",
                "value": {
                    "prompt_id": 1,
                    "project_id": 1,
                    "input_variables": {"text": "Extract entities from: John works at Google"},
                    "structured_output": True
                }
            },
            "image": {
                "summary": "Image input example",
                "description": "Create a run with image input",
                "value": {
                    "prompt_id": 1,
                    "project_id": 1,
                    "input_variables": {
                        "image": "base64_encoded_image_data",
                        "question": "What's in this image?"
                    },
                    "structured_output": False
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    """
    Create a new run for a prompt.

    This endpoint executes a prompt with the given input variables and returns the result.
    The run is stored in the database for future reference.

    Args:
        run_in: The run creation parameters
        db: Database session

    Returns:
        Run: The created run object

    Raises:
        404: If the prompt is not found
        400: If the input variables are invalid
        500: If there's an internal server error
    """
    try:
        run_service = RunService(db)
        return run_service.create_run(
            prompt_id=run_in.prompt_id,
            project_id=run_in.project_id,
            input_variables=run_in.input_variables,
            structured_output=run_in.structured_output,
            model=run_in.model
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/{prompt_id}/list", response_model=List[Run])
def list_runs(
    prompt_id: int = Path(..., description="ID of the prompt to list runs for", example=1),
    skip: int = Query(
        0, 
        ge=0,
        description="Number of records to skip for pagination",
        example=0
    ),
    limit: int = Query(
        100, 
        ge=1, 
        le=1000,
        description="Maximum number of records to return",
        example=100
    ),
    order_by_latest: bool = Query(
        True, 
        description="If True, returns latest runs first",
        example=True
    ),
    db: Session = Depends(get_db)
):
    """
    List all runs for a specific prompt with pagination support.

    This endpoint returns a paginated list of runs for a given prompt ID.
    The results can be ordered by creation time (latest first or oldest first).

    Args:
        prompt_id: ID of the prompt to list runs for
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        order_by_latest: If True, returns latest runs first
        db: Database session

    Returns:
        List[Run]: List of run objects

    Raises:
        404: If the prompt is not found
        500: If there's an internal server error

    Examples:
        Get latest 10 runs:
        ```
        GET /runs/1/list?skip=0&limit=10&order_by_latest=true
        ```

        Get next page of runs:
        ```
        GET /runs/1/list?skip=10&limit=10&order_by_latest=true
        ```

        Get oldest runs first:
        ```
        GET /runs/1/list?skip=0&limit=10&order_by_latest=false
        ```
    """
    try:
        run_service = RunService(db)
        return run_service.get_runs_by_prompt(prompt_id, skip, limit, order_by_latest)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
