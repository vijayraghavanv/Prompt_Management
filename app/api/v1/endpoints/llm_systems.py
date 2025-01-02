from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.llm_system_service import LLMSystemService
from app.schemas.llm_system import LLMSystem

router = APIRouter()

@router.get("/", response_model=List[LLMSystem])
def get_all_llm_systems(
    db: Session = Depends(get_db)
) -> List[LLMSystem]:
    """
    Retrieve all LLM systems.
    """
    service = LLMSystemService(db)
    return service.list_all()
