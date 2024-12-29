import json
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.llm_system import LLMSystem
from app.schemas.llm_system import LLMSystemCreate, LLMSystemUpdate
from app.core.exceptions import AppException, NotFoundError, ValidationError


class LLMSystemService:
    """Service for managing LLM systems"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, system_id: int) -> Optional[LLMSystem]:
        """Get LLM system by ID"""
        return self.db.query(LLMSystem).filter(LLMSystem.id == system_id).first()

    def get_by_name(self, name: str) -> Optional[LLMSystem]:
        """Get LLM system by name"""
        return self.db.query(LLMSystem).filter(LLMSystem.name == name).first()

    def get_default(self) -> Optional[LLMSystem]:
        """Get the default LLM system"""
        return self.db.query(LLMSystem).filter(LLMSystem.is_default == True).first()

    def list_all(self) -> List[LLMSystem]:
        """List all LLM systems"""
        return self.db.query(LLMSystem).all()

    def create(self, system: LLMSystemCreate) -> LLMSystem:
        """Create a new LLM system"""
        try:
            # Validate models JSON
            try:
                json.loads(system.available_models)
            except json.JSONDecodeError:
                raise ValidationError("available_models must be a valid JSON string")

            # If this is set as default, unset others
            if system.is_default:
                self._unset_all_defaults()

            db_system = LLMSystem(**system.model_dump())
            self.db.add(db_system)
            self.db.commit()
            self.db.refresh(db_system)
            return db_system

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating LLM system: {str(e)}")
            raise AppException("Error creating LLM system")

    def update(self, system_id: int, update_data: LLMSystemUpdate) -> LLMSystem:
        """Update an LLM system"""
        try:
            system = self.get(system_id)
            if not system:
                raise NotFoundError(f"LLM system {system_id} not found")

            # If setting as default, unset others
            if update_data.is_default:
                self._unset_all_defaults()

            # Update fields
            if update_data.default_model is not None:
                # Validate model exists in available models
                available = json.loads(system.available_models)
                if update_data.default_model not in available:
                    raise ValidationError(f"Model {update_data.default_model} not in available models")
                system.default_model = update_data.default_model

            if update_data.default_multimodal is not None:
                # Validate multimodal model exists in available models
                available = json.loads(system.available_models)
                if update_data.default_multimodal not in available:
                    raise ValidationError(f"Model {update_data.default_multimodal} not in available models")
                system.default_multimodal = update_data.default_multimodal

            if update_data.is_default is not None:
                system.is_default = update_data.is_default

            self.db.commit()
            self.db.refresh(system)
            return system

        except (SQLAlchemyError, json.JSONDecodeError) as e:
            self.db.rollback()
            raise AppException(f"Error updating LLM system: {str(e)}")

    def _unset_all_defaults(self):
        """Helper to unset is_default on all systems"""
        try:
            self.db.query(LLMSystem).update({"is_default": False})
            self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise AppException(f"Error unsetting defaults: {str(e)}")

    def get_all_available_models(self) -> List[str]:
        """Get all available models from all LLM systems"""
        systems = self.db.query(LLMSystem).all()
        all_models = []
        for system in systems:
            models = json.loads(system.available_models)
            all_models.extend(models)
        return all_models

    def get_model_for_prompt(self, prompt_id: int) -> str:
        """Get appropriate model for a prompt based on its variables"""
        from app.services.prompt import PromptService
        from app.schemas.prompt import VariableType

        # Get prompt and check its variables
        prompt_service = PromptService(self.db)
        prompt = prompt_service.get(prompt_id)
        if not prompt:
            raise NotFoundError(f"Prompt {prompt_id} not found")

        # Get default LLM system
        system = self.get_default()
        if not system:
            raise ValidationError("No default LLM system configured")

        # Check if any variables are images
        has_image = any(var.get("type", "string") == VariableType.IMAGE.value for var in prompt.variables)

        # Return multimodal model if has images, otherwise default model
        if has_image:
            if not system.default_multimodal:
                raise ValidationError(f"No multimodal model configured for {system.name}")
            return system.default_multimodal
        return system.default_model
