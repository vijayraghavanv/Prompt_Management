from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.settings import SettingType


class SettingBase(BaseModel):
    """
    Base schema for settings

    Attributes:
        key: Unique identifier for the setting
        type: Type of setting (API_KEY, CONFIG)
        value: The setting value (will be encrypted for API keys)
        description: Optional description of what the setting is for
    """
    model_config = ConfigDict(from_attributes=True)

    key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r'^[a-zA-Z][a-zA-Z0-9_\-\.]*$',
        description="Unique key for the setting"
    )
    type: SettingType = Field(description="Type of setting")
    description: Optional[str] = Field(None, description="Optional description")


class SettingResponse(SettingBase):
    """
    Schema for setting responses
    
    For API keys, returns a masked value
    For other settings, returns the actual value
    """
    id: int = Field(description="Unique identifier")
    value: str = Field(description="Setting value (masked for API keys)")


class SettingCreate(SettingBase):
    """Schema for creating a new setting"""
    value: str = Field(description="Setting value")


class SettingUpdate(BaseModel):
    """
    Schema for updating a setting
    
    All fields are optional since we may want to update
    just the value or just the description
    """
    model_config = ConfigDict(from_attributes=True)

    value: Optional[str] = Field(None, description="New setting value")
    description: Optional[str] = Field(None, description="New description")
