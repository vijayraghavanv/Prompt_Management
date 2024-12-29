# app/schemas/project.py
from pydantic import BaseModel, ConfigDict, Field, field_validator, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum
from ..core.exceptions import ValidationError
from loguru import logger
from .prompt import PromptBase


class ProjectStatus(str, Enum):
    """
    Enum for project status
    ACTIVE: Project is currently in use
    ARCHIVED: Project is archived but kept for reference
    DRAFT: Project is still in development
    """
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"

    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive enum matching"""
        if isinstance(value, str):
            # Try to match case-insensitively
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None


class ProjectBase(BaseModel):
    model_config = ConfigDict()

    """
    Base Project Schema with common attributes

    Attributes:
        name: Project name (3-50 chars)
        description: Optional detailed description
        status: Project status (default: DRAFT)
        tags: Optional list of project tags for organization
        version: Project version string
        is_public: Whether project is publicly accessible
    """
    name: str = Field(
        min_length=3,
        max_length=50,
        description="Name of the project"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Detailed description of the project"
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.DRAFT,
        description="Current status of the project"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=5,  # Maximum 5 tags
        description="List of project tags for organization"
    )
    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Project version in semantic versioning format"
    )
    is_public: bool = Field(
        default=False,
        description="Whether project is publicly accessible"
    )

    @field_validator('tags')
    def validate_tags(cls, v):
        if len(v) > 5:
            raise ValidationError(detail="Maximum 5 tags allowed")
        if not all(isinstance(tag, str) and len(tag) <= 20 for tag in v):
            raise ValidationError(detail="Tags must be strings with maximum length of 20 characters")
        return v


class ProjectCreate(ProjectBase):
    """Schema for creating a new project"""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project
    All fields are optional"""
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[ProjectStatus] = None
    tags: Optional[List[str]] = Field(None, max_length=5)
    version: Optional[str] = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    is_public: Optional[bool] = None

    @field_validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            if len(v) > 5:
                raise ValidationError(detail="Maximum 5 tags allowed")
            if not all(isinstance(tag, str) and len(tag) <= 20 for tag in v):
                raise ValidationError(detail="Tags must be strings with maximum length of 20 characters")
        return v


class Project(ProjectBase):
    """Complete project schema including database fields

    Additional Attributes:
        id: Unique project identifier
        created_at: Timestamp of project creation
        updated_at: Timestamp of last update
        prompt_count: Number of prompts in the project
        prompts: List of prompts associated with the project
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{
                "id": 1,
                "name": "my-project",
                "description": "A sample project",
                "status": "active",
                "tags": ["production", "gpt4"],
                "version": "1.0.0",
                "is_public": False,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
                "prompt_count": 5,
                "prompts": []
            }]
        }
    )
    id: int = Field(description="Unique project identifier")
    created_at: datetime = Field(description="Timestamp of project creation")
    updated_at: datetime = Field(description="Timestamp of last update")
    prompt_count: int = Field(
        default=0,
        ge=0,
        description="Number of prompts in the project"
    )
    prompts: List[PromptBase] = Field(
        default_factory=list,
        description="List of prompts associated with the project"
    )