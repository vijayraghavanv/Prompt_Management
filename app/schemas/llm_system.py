from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class LLMSystemBase(BaseModel):
    """Base schema for LLM systems"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Name of the LLM system (e.g., OpenAI, Claude)")
    api_key_setting: str = Field(description="Name of the setting that contains the API key")
    default_model: str = Field(description="Default model to use")
    default_multimodal: Optional[str] = Field(None, description="Default multimodal model to use")
    available_models: str = Field(description="JSON string of available models")
    is_default: bool = Field(description="Whether this is the default LLM system")


class LLMSystem(LLMSystemBase):
    """Schema for LLM system with ID"""
    id: int = Field(description="Unique identifier")


class LLMSystemCreate(LLMSystemBase):
    """Schema for creating a new LLM system"""
    pass


class LLMSystemUpdate(BaseModel):
    """Schema for updating an LLM system"""
    model_config = ConfigDict(from_attributes=True)

    default_model: Optional[str] = Field(None, description="New default model")
    default_multimodal: Optional[str] = Field(None, description="New default multimodal model")
    is_default: Optional[bool] = Field(None, description="Set as default system")
