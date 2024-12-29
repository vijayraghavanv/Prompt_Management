from datetime import datetime, timezone
import json
import os
import time
from typing import Dict, Optional, Sequence

from jsonschema_pydantic import jsonschema_to_pydantic
from llama_index.core.output_parsers import PydanticOutputParser
from llama_index.core.program import MultiModalLLMCompletionProgram
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import AppException, NotFoundError
from app.core.prompt_template import CustomPromptTemplate
from app.models.run import Run
from app.schemas.prompt import VariableType
from app.services.llama_service import LlamaService
from app.services.llm_system_service import LLMSystemService
from app.services.prompt import PromptService


class RunService:
    """Service for managing runs"""

    def __init__(self, db: Session):
        """Initialize service"""
        self.db = db
        self.prompt_service = PromptService(db)
        self.llm_system_service = LLMSystemService(db)
        self.llama_service = LlamaService(db)

    def create_run(
        self,
        prompt_id: int,
        project_id: int,
        input_variables: Dict,
        structured_output: bool = False,
        model: Optional[str] = None
    ) -> Run:
        """Create new run"""
        try:
            # Get the prompt and its variables
            prompt_obj = self.prompt_service.get(prompt_id)
            if not prompt_obj:
                raise NotFoundError(f"Prompt {prompt_id} not found")

            # Validate structured output requirements
            if structured_output:
                if not prompt_obj.output_schema:
                    raise ValidationError("Structured output requested but prompt has no output schema defined")

            # Determine if we have any image variables and process them
            has_image = False
            image_documents = []
            for var in prompt_obj.variables:
                if var.get("type") == VariableType.IMAGE.value:
                    has_image = True
                    var_name = var.get("name")
                    if var_name not in input_variables:
                        raise ValidationError(f"Missing required image variable: {var_name}")
                    
                    image_doc = self.llama_service.process_image(input_variables[var_name])
                    image_documents.append(image_doc)

            # Get appropriate model based on variable types
            if model is None:
                if has_image:
                    system = self.llm_system_service.get_default()
                    if not system or not system.default_multimodal:
                        raise ValidationError("No default multimodal model configured")
                    model = system.default_multimodal
                else:
                    system = self.llm_system_service.get_default()
                    if not system:
                        raise ValidationError("No default LLM system configured")
                    model = system.default_model

            # Create LLM instance
            llm = self.llama_service.get_llm(model, is_multimodal=has_image)
            
            # Format prompt with variables
            prompt_template = CustomPromptTemplate(prompt_obj.content)
            if not has_image:
                formatted_prompt = prompt_template.format(**input_variables)
            else:
                formatted_prompt = prompt_obj.content

            # Start timing before LLM operations
            start_time = time.time()

            # Handle structured output
            if structured_output:
                # Convert JSON schema to Pydantic model
                OutputModel = jsonschema_to_pydantic(prompt_obj.output_schema)
                
                if has_image:
                    # For multi-modal with structured output, use MultiModalLLMCompletionProgram
                    
                    # Add schema instructions to prompt
                    formatted_prompt += "\n\nProvide your response in valid JSON format following this schema:\n"
                    formatted_prompt += json.dumps(prompt_obj.output_schema, indent=2)
                    
                    program = MultiModalLLMCompletionProgram.from_defaults(
                        output_parser=PydanticOutputParser(OutputModel),
                        image_documents=image_documents,
                        prompt_template_str=formatted_prompt,
                        multi_modal_llm=llm,
                        verbose=True
                    )
                    response = program()
                else:
                    # For text-only structured output, use regular structured LLM
                    llm = llm.as_structured_llm(OutputModel)
                    # Add schema instructions to prompt
                    formatted_prompt += "\n\nProvide your response in valid JSON format following this schema:\n"
                    formatted_prompt += json.dumps(prompt_obj.output_schema, indent=2)
                    response = llm.complete(
                        formatted_prompt,
                        temperature=prompt_obj.temperature,
                        max_tokens=prompt_obj.max_tokens
                    )
            else:
                # Regular completion without structured output
                if has_image:
                    response = llm.complete(
                        prompt=formatted_prompt,
                        image_documents=image_documents,
                        temperature=prompt_obj.temperature,
                        max_tokens=prompt_obj.max_tokens
                    )
                else:
                    response = llm.complete(
                        formatted_prompt,
                        temperature=prompt_obj.temperature,
                        max_tokens=prompt_obj.max_tokens
                    )

            # Clean up temp files if we have images
            if has_image:
                for doc in image_documents:
                    temp_file = doc.metadata.get('temp_file')
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Process output based on response type
            if has_image and structured_output:
                # For MultiModalLLMCompletionProgram, response is already a Pydantic model
                output = response.model_dump_json()
            else:
                # For regular completion or text-only structured output
                output = response.text
                if structured_output:
                    try:
                        # Response is already validated by structured LLM
                        output_json = json.loads(output)
                        # Just convert to string for storage
                        output = json.dumps(output_json)
                    except json.JSONDecodeError:
                        logger.warning(f"Expected JSON output but got: {output}")
                        raise AppException(
                            status_code=400,
                            detail="Failed to get structured JSON output",
                            error_code="INVALID_JSON_OUTPUT"
                        )

            tokens = self.llama_service.get_token_counts()
            self.llama_service.reset_token_counter()

            # Create run record
            db_run = Run(
                prompt_id=prompt_id,
                project_id=project_id,
                version=prompt_obj.current_version,
                input_variables=input_variables,
                output=output,
                model=model,
                prompt_tokens=tokens['prompt_tokens'] or 0,
                completion_tokens=tokens['completion_tokens'] or 0,
                total_tokens=tokens['total_tokens'] or 0,
                latency_ms=latency_ms,
                run_metadata={
                    "structured_output": structured_output,
                    "has_images": has_image,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            self.db.add(db_run)
            self.db.commit()
            self.db.refresh(db_run)
            
            return db_run
            
        except NotFoundError:
            raise
        except ValidationError:
            raise
        except AppException:
            raise
        except Exception as e:
            self.db.rollback()
            raise AppException(
                status_code=500,
                detail=f"Error creating run: {str(e)}",
                error_code="RUN_CREATION_ERROR"
            )

    def get_runs_by_prompt(
        self,
        prompt_id: int,
        skip: int = 0,
        limit: int = 100,
        order_by_latest: bool = True
    ) -> Sequence[Run]:
        """
        Get all runs for a specific prompt.

        Args:
            prompt_id: ID of the prompt to get runs for
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            order_by_latest: If True, returns latest runs first

        Returns:
            List of runs for the prompt

        Raises:
            NotFoundError: If prompt doesn't exist
            AppException: If database operation fails
        """
        try:
            # First check if prompt exists
            prompt = self.prompt_service.get(prompt_id)
            if not prompt:
                raise NotFoundError(f"Prompt {prompt_id} not found")

            # Build query
            query = self.db.query(Run).filter(Run.prompt_id == prompt_id)
            
            # Add ordering
            if order_by_latest:
                query = query.order_by(Run.created_at.desc())
            else:
                query = query.order_by(Run.created_at.asc())
            
            # Add pagination
            query = query.offset(skip).limit(limit)
            
            return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving runs for prompt {prompt_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve runs",
                error_code="DB_ERROR"
            )
