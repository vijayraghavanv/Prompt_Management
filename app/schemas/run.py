from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field, ConfigDict


class TokenUsage(BaseModel):
    """
    Token usage breakdown for a run
    
    Tracks different types of tokens used in the request/response
    """
    model_config = ConfigDict(from_attributes=True)
    
    prompt_tokens: int = Field(description="Tokens used in the prompt")
    completion_tokens: int = Field(description="Tokens used in the completion")
    embedding_tokens: Optional[int] = Field(None, description="Tokens used for embeddings")
    total_tokens: int = Field(description="Total tokens used")


class RunBase(BaseModel):
    """Base schema for run operations"""
    model_config = ConfigDict(from_attributes=True)

    prompt_id: int = Field(..., description="ID of the prompt to run", example=1)
    project_id: int = Field(..., description="ID of the project this run belongs to", example=1)
    input_variables: Dict = Field(
        ..., 
        description="""Variables to inject into the prompt template. 
        For image inputs, the image should be base64 encoded.
        Example: {"text": "What is ML?"} or {"image": "base64...", "question": "What's in this image?"}""",
        example={"text": "What is machine learning?"}
    )
    model: Optional[str] = Field(
        None, 
        description="Specific model to use for this run. If not provided, uses system default",
        example="gpt-4"
    )
    structured_output: bool = Field(
        False,
        description="Whether to request structured JSON output based on prompt's output_schema",
        example=False
    )
    version: Optional[int] = Field(
        None,
        description="Specific version of the prompt to run. If not provided, uses current version",
        example=1
    )


class RunCreate(RunBase):
    """Schema for creating a new run"""
    pass


class Run(RunBase):
    """Schema for a complete run including results"""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "prompt_id": 1,
                "project_id": 1,
                "version": 1,
                "input_variables": {
                    "text": "What is machine learning?"
                },
                "output": "Machine learning is a subset of artificial intelligence...",
                "model": "gpt-4",
                "structured_output": False,
                "prompt_tokens": 50,
                "completion_tokens": 150,
                "total_tokens": 200,
                "latency_ms": 1500,
                "run_metadata": {
                    "structured_output": False,
                    "has_images": False,
                    "timestamp": "2024-12-27T17:10:00Z"
                },
                "created_at": "2024-12-27T17:10:00Z",
                "updated_at": "2024-12-27T17:10:00Z"
            }
        }
    )

    id: int = Field(..., description="Unique identifier for the run", example=1)
    output: str = Field(
        ..., 
        description="Output from the model. May be plain text or JSON string if structured_output=True",
        example="Machine learning is a subset of artificial intelligence..."
    )
    prompt_tokens: int = Field(
        ..., 
        description="Number of tokens in the prompt",
        example=50
    )
    completion_tokens: int = Field(
        ..., 
        description="Number of tokens in the completion",
        example=150
    )
    total_tokens: int = Field(
        ..., 
        description="Total number of tokens used",
        example=200
    )
    latency_ms: int = Field(
        ..., 
        description="Time taken to generate the response in milliseconds",
        example=1500
    )
    run_metadata: Dict = Field(
        ..., 
        description="""Additional metadata about the run.
        Contains structured_output flag, has_images flag, and timestamp""",
        example={
            "structured_output": False,
            "has_images": False,
            "timestamp": "2024-12-27T17:10:00Z"
        }
    )
    created_at: datetime = Field(
        ..., 
        description="When this run was created",
        example="2024-12-27T17:10:00Z"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="When this run was last updated",
        example="2024-12-27T17:10:00Z"
    )


class RunInPrompt(BaseModel):
    """Schema for runs when included in prompt responses"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    output: str
    model: Optional[str]
    token_usage: TokenUsage
    version: int
