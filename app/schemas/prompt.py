from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime

from loguru import logger
from pydantic import BaseModel, field_validator, model_validator, Field, ConfigDict

from app.core.exceptions import ValidationError


class PromptStatus(Enum):
    """
    Status of a prompt in its lifecycle

    Attributes:
        DRAFT: Initial status, prompt is being developed
        TESTING: Prompt is ready for testing/review
        PUBLISHED: Prompt is approved and live
        DEPRECATED: Prompt is marked for removal but still usable
        ARCHIVED: Prompt is no longer in use
    """
    DRAFT = "draft"
    TESTING = "testing"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

    def can_transition_to(self, new_status: 'PromptStatus') -> bool:
        """
        Check if current status can transition to new status

        Valid transitions:
        DRAFT -> TESTING, PUBLISHED
        TESTING -> DRAFT, PUBLISHED
        PUBLISHED -> DEPRECATED
        DEPRECATED -> ARCHIVED
        ARCHIVED -> No transitions allowed
        """
        transitions = {
            PromptStatus.DRAFT: {PromptStatus.TESTING, PromptStatus.PUBLISHED},
            PromptStatus.TESTING: {PromptStatus.DRAFT, PromptStatus.PUBLISHED},
            PromptStatus.PUBLISHED: {PromptStatus.DEPRECATED},
            PromptStatus.DEPRECATED: {PromptStatus.ARCHIVED},
            PromptStatus.ARCHIVED: set()
        }
        return new_status in transitions.get(self, set())


class VariableType(str, Enum):
    """Type of prompt variable"""
    STRING = "string"
    IMAGE = "image"


class PromptVariable(BaseModel):
    """
    Schema for prompt variables

    Attributes:
        name: Name of the variable
        description: Description of what the variable represents
        required: Whether this variable must be provided
        type: Type of variable (string or image)
    """
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(
        min_length=1,
        max_length=50,
        pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$',
        description="Name of the variable"
    )
    description: Optional[str] = Field(
        None,
        max_length=200,
        description="Description of what the variable represents"
    )
    required: bool = Field(
        default=True,
        description="Whether this variable must be provided"
    )
    type: VariableType = Field(
        default=VariableType.STRING,
        description="Type of variable (string or image)"
    )


class PromptBase(BaseModel):
    """
    Base Prompt Schema with common attributes and validations

    Attributes:
        name: Unique name within project
        description: Detailed description of prompt's purpose
        content: Actual prompt template with variables
        project_id: Associated project
        variables: List of variables used in prompt
        max_tokens: Maximum response length
        temperature: Response randomness (0-1)
        status: Current lifecycle status
        output_schema: JSON schema for validating structured output
    """
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(
        min_length=3,
        max_length=100,
        pattern=r'^[a-zA-Z][a-zA-Z0-9_\-\.]*$',
        description="Name of the prompt"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Description of what the prompt does"
    )
    content: str = Field(
        min_length=10,
        max_length=10000,
        description="The actual prompt template"
    )
    project_id: int = Field(gt=0, description="ID of the project this prompt belongs to")
    variables: List[PromptVariable] = Field(
        default_factory=list,
        description="""List of variables used in the prompt. 
        Note: If using an image variable, it must be the only variable in the prompt.
        You cannot mix image and string variables."""
    )
    max_tokens: int = Field(
        ge=0,
        le=9999999999,
        description="Maximum tokens in response"
    )
    temperature: float = Field(
        ge=0.0,
        le=1.0,
        default=0.7,
        description="Sampling temperature"
    )
    status: PromptStatus = Field(
        default=PromptStatus.DRAFT,
        description="Current status of the prompt"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="JSON schema for validating structured output"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate prompt name format"""
        if not v[0].isalpha():
            logger.error(f"Invalid prompt name: {v} - Must start with letter")
            raise ValidationError("Prompt name must start with a letter")
        return v

    @model_validator(mode='after')
    def validate_content_variables(self) -> 'PromptBase':
        """
        Validate prompt content and extract variables

        Checks:
        1. Variable syntax {var_name}
        2. All variables are defined in variables list
        3. No duplicate variables
        4. Variable names follow naming convention
        """
        import re

        # Extract variables from content using single braces
        var_pattern = r'\{([^}]+)\}'
        found_vars = {var.strip() for var in re.findall(var_pattern, self.content)}

        # Validate variable names
        for var in found_vars:
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', var):
                logger.error(f"Invalid variable name in content: {var}")
                raise ValidationError(
                    f"Invalid variable name: {var}. Must start with letter and contain only letters, numbers, and underscores"
                )

        # Check if all content variables are defined in variables list
        defined_vars = {var.name for var in self.variables}
        undefined_vars = found_vars - defined_vars
        
        if undefined_vars:
            logger.error(f"Undefined variables in content: {undefined_vars}")
            raise ValidationError(
                f"Variables used but not defined: {undefined_vars}. "
                f"Make sure to define all variables used in the content using the format: {{var}} for each variable."
            )

        return self

    @model_validator(mode='after')
    def validate_status_transition(self) -> 'PromptBase':
        """Validate status transitions"""
        if hasattr(self, 'id'):  # Only check for existing prompts
            old_status = getattr(self, '_old_status', None)
            if old_status and not old_status.can_transition_to(self.status):
                logger.error(
                    f"Invalid status transition",
                    extra={
                        "from_status": old_status,
                        "to_status": self.status
                    }
                )
                raise ValidationError(
                    f"Cannot transition from {old_status.value} to {self.status.value}"
                )
        return self

    @model_validator(mode='after')
    def validate_published_requirements(self) -> 'PromptBase':
        """
        Validate requirements for published status

        Requirements:
        1. Must have description
        2. All variables must have descriptions
        3. Must have at least one test case
        """
        if self.status == PromptStatus.PUBLISHED:
            if not self.description:
                raise ValidationError("Published prompts must have a description")

            for var in self.variables:
                if not var.description:
                    raise ValidationError(
                        f"All variables must have descriptions when publishing. Missing for: {var.name}"
                    )
        return self

    @model_validator(mode='after')
    def validate_variable_types(self) -> 'PromptBase':
        """
        Validate prompt variable types and output schema combinations.
        
        Rules:
        1. If using an image variable:
           - Can only have one image variable
           - Can have output_schema for structured output (multi-modal with structured output)
           - Cannot have other variable types
        2. If using string variables:
           - Can have multiple string variables
           - Can have output_schema for structured output
        """
        if not self.variables:
            return self
            
        # Get unique variable types
        var_types = {var.type for var in self.variables}
        
        # Check if we have an image variable
        if VariableType.IMAGE in var_types:
            # If we have an image variable, it must be the only variable
            if len(self.variables) > 1:
                raise ValidationError(
                    "When using an image variable, it must be the only variable in the prompt. "
                    "You cannot mix image and string variables."
                )
            
            # If we have both image and output_schema, this is a multi-modal prompt with structured output
            if self.output_schema:
                logger.info(
                    "Multi-modal prompt with structured output detected",
                    extra={
                        "variable_type": "image",
                        "has_output_schema": True,
                        "output_schema": self.output_schema
                    }
                )
        
        return self

    @model_validator(mode='after')
    def validate_multi_modal_requirements(self) -> 'PromptBase':
        """
        Validate requirements for multi-modal prompts.

        Requirements:
        1. Must have exactly one image variable
        """
        # Check if this is a multi-modal prompt
        has_image = any(var.type == VariableType.IMAGE for var in self.variables)

        if has_image:
            if len(self.variables) > 1:
                raise ValidationError(
                    "Multi-modal prompts must have exactly one image variable"
                )

            logger.info(
                "Validated multi-modal prompt",
                extra={
                    "has_image": True
                }
            )

        return self


class Prompt(PromptBase):
    """Schema for prompt responses"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PromptStatus = PromptStatus.DRAFT
    version_count: int = Field(default=1)
    current_version: int = Field(default=1)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PromptCreate(PromptBase):
    """Schema for creating a new prompt"""
    id: Optional[int] = Field(None, description="ID of the prompt to version. If provided, creates a new version.")


class PromptUpdate(PromptBase):
    """Schema for updating an existing prompt"""
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    project_id: Optional[int] = None
    variables: Optional[List[PromptVariable]] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    status: Optional[PromptStatus] = None
    output_schema: Optional[Dict[str, Any]] = None


class PromptInProject(PromptBase):
    """Schema for prompt when included in project response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    version_count: int
    current_version: int

    class Config:
        from_attributes = True


class PromptVersionBase(BaseModel):
    """
    Schema for prompt version data

    Attributes:
        version: Version number
        content: Prompt template content
        variables: List of variables used in prompt
        output_schema: JSON schema for validating structured output
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        created_at: When this version was created
    """
    model_config = ConfigDict(from_attributes=True)

    version: int = Field(description="Version number")
    content: str = Field(description="Prompt template content")
    variables: List[Dict] = Field(description="List of variables used in prompt")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for validating structured output")
    max_tokens: int = Field(description="Maximum tokens in response")
    temperature: float = Field(description="Sampling temperature")
    created_at: datetime = Field(description="When this version was created")


class PromptVersion(PromptVersionBase):
    """
    Schema for prompt version with prompt details

    Includes all base version fields plus prompt details
    """
    model_config = ConfigDict(from_attributes=True)

    # Add prompt details
    prompt_id: int = Field(description="ID of the prompt")
    prompt_name: str = Field(description="Name of the prompt")
    prompt_description: Optional[str] = Field(description="Description of the prompt")
    project_id: int = Field(description="ID of the project")