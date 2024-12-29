from typing import List
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.settings import SettingResponse, SettingCreate, SettingUpdate
from app.services.settings import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/", response_model=List[SettingResponse])
def list_settings(db: Session = Depends(get_db)):
    """List all settings"""
    service = SettingsService(db)
    return service.list_all()


@router.get("/{setting_id}", response_model=SettingResponse)
def get_setting(
    setting_id: int = Path(..., title="The ID of the setting to get", ge=1),
    db: Session = Depends(get_db)
):
    """Get a specific setting by ID"""
    service = SettingsService(db)
    return service.get(setting_id)


@router.post("/", response_model=SettingResponse)
def create_setting(setting: SettingCreate, db: Session = Depends(get_db)):
    """Create a new setting"""
    service = SettingsService(db)
    return service.create(setting)


@router.patch("/{setting_id}", response_model=SettingResponse)
def update_setting(
    setting_id: int = Path(..., title="The ID of the setting to update", ge=1),
    setting: SettingUpdate = None,
    db: Session = Depends(get_db)
):
    """Update a setting"""
    service = SettingsService(db)
    return service.update(setting_id, setting)


@router.delete("/{setting_id}", status_code=204)
def delete_setting(
    setting_id: int = Path(..., title="The ID of the setting to delete", ge=1),
    db: Session = Depends(get_db)
):
    """Delete a setting"""
    service = SettingsService(db)
    service.delete(setting_id)
