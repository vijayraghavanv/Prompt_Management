from typing import Optional, TypeVar, Sequence, List, Dict
from sqlalchemy import select, exc as sql_exc, union_all, JSON, desc, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.prompt import Prompt, PromptVersion
from app.schemas.prompt import PromptBase, PromptStatus, VariableType, PromptCreate
from app.core.exceptions import AppException, ValidationError, NotFoundError

T = TypeVar('T', bound=Prompt)


class PromptService:
    """
    Service class for managing prompts and their versions.
    
    This service provides methods for CRUD operations on prompts, version management,
    and status transitions. It ensures data consistency and proper error handling
    for all operations.

    Attributes:
        db (Session): SQLAlchemy database session for database operations
    """

    def __init__(self, db: Session):
        """
        Initialize the prompt service.

        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db

    def validate_variables(self, variables: List[Dict]) -> None:
        """Validate prompt variables"""
        if not variables:
            return
            
        # Check if there's an image variable
        has_image = any(var.get("type") == VariableType.IMAGE.value for var in variables)
        
        if has_image and len(variables) > 1:
            raise ValidationError(
                "Prompts with image variables can only have one variable of type 'image'"
            )
            
        # Validate each variable
        for var in variables:
            if not var.get("name"):
                raise ValidationError("Variable name is required")
            if not var.get("type"):
                raise ValidationError("Variable type is required")
            if var.get("type") not in [e.value for e in VariableType]:
                raise ValidationError(f"Invalid variable type: {var.get('type')}")

    def create(self, prompt: PromptCreate) -> Prompt:
        """
        Create a new prompt or create a new version of an existing prompt.
        
        If prompt.id is provided, creates a new version of that prompt.
        Otherwise creates a new prompt.
        
        Args:
            prompt (PromptCreate): The prompt data
            
        Returns:
            Prompt: The created prompt or new version
            
        Raises:
            NotFoundError: If versioning a non-existent prompt
            ValidationError: If validation fails
            AppException: For other database errors
        """
        try:
            # If id is provided, create a new version
            if prompt.id:
                existing_prompt = self.get(prompt.id)
                if not existing_prompt:
                    raise NotFoundError(detail=f"Prompt {prompt.id} not found")
                return self.create_version(prompt.id, prompt)
            
            # Convert variables to JSON-serializable format
            variables = [var.model_dump() for var in prompt.variables] if prompt.variables else []
            
            db_prompt = Prompt(
                name=prompt.name,
                description=prompt.description,
                content=prompt.content,
                project_id=prompt.project_id,
                variables=variables,
                output_schema=prompt.output_schema,  # Already a dict, no need to convert
                max_tokens=prompt.max_tokens,
                temperature=prompt.temperature,
                status=prompt.status
            )
            
            self.db.add(db_prompt)
            self.db.commit()
            self.db.refresh(db_prompt)
            
            logger.info(
                "Created new prompt",
                extra={
                    "prompt_id": db_prompt.id,
                    "name": db_prompt.name,
                    "project_id": db_prompt.project_id
                }
            )
            
            return db_prompt
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                "Failed to create prompt",
                extra={
                    "error": str(e),
                    "name": prompt.name,
                    "project_id": prompt.project_id
                }
            )
            raise AppException(
                status_code=500,
                detail="Failed to create prompt",
                error_code="DB_ERROR"
            )

    def get(self, prompt_id: int) -> Optional[Prompt]:
        """
        Retrieve a prompt by its ID.

        Args:
            prompt_id (int): ID of the prompt to retrieve

        Returns:
            Optional[Prompt]: Found prompt or None if not found

        Raises:
            AppException: If database operation fails
        """
        try:
            return self.db.query(Prompt).filter(Prompt.id == prompt_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving prompt {prompt_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve prompt",
                error_code="DB_ERROR"
            )

    def get_by_project(self, project_id: int) -> Sequence[Prompt]:
        """
        Retrieve all prompts belonging to a project.

        Args:
            project_id (int): ID of the project

        Returns:
            Sequence[Prompt]: List of prompts belonging to the project

        Raises:
            AppException: If database operation fails
        """
        try:
            stmt = select(Prompt).where(Prompt.project_id == project_id)
            result = self.db.scalars(stmt).all()
            logger.debug(f"Retrieved {len(result)} prompts for project {project_id}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving prompts for project {project_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve project prompts",
                error_code="DB_ERROR"
            )

    def get_by_name_and_project(self, name: str, project_id: int) -> Optional[Prompt]:
        """
        Retrieve a prompt by its name and project_id.

        Args:
            name (str): Name of the prompt
            project_id (int): ID of the project

        Returns:
            Optional[Prompt]: Found prompt or None if not found

        Raises:
            AppException: If database operation fails
        """
        try:
            return self.db.query(Prompt).filter(
                Prompt.name == name,
                Prompt.project_id == project_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving prompt by name {name} and project {project_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve prompt",
                error_code="DB_ERROR"
            )

    def update(self, prompt_id: int, prompt_data: PromptBase) -> Prompt:
        """
        Update an existing prompt.

        Args:
            prompt_id (int): ID of the prompt to update
            prompt_data (PromptBase): New prompt data

        Returns:
            Prompt: Updated prompt instance

        Raises:
            NotFoundError: If prompt doesn't exist
            ValidationError: If update data is invalid
            AppException: If database operation fails
        """
        prompt = self.get(prompt_id)
        if not prompt:
            raise NotFoundError(detail=f"Prompt {prompt_id} not found")

        try:
            # Validate status transition if status is being updated
            if 'status' in prompt_data.model_dump() and prompt_data.status != prompt.status:
                if not prompt.status.can_transition_to(prompt_data.status):
                    raise ValidationError(
                        detail=f"Invalid status transition from {prompt.status} to {prompt_data.status}"
                    )

            # Validate variables
            self.validate_variables(prompt_data.model_dump().get("variables", []))

            for key, value in prompt_data.model_dump(exclude_unset=True).items():
                setattr(prompt, key, value)
            self.db.commit()
            self.db.refresh(prompt)
            logger.info(f"Updated prompt {prompt_id}")
            return prompt
        except sql_exc.IntegrityError as e:
            logger.error(f"Integrity error updating prompt {prompt_id}: {str(e)}")
            self.db.rollback()
            raise ValidationError(detail="Prompt with this name already exists in project")
        except SQLAlchemyError as e:
            logger.error(f"Error updating prompt {prompt_id}: {str(e)}")
            self.db.rollback()
            raise AppException(
                status_code=500,
                detail="Failed to update prompt",
                error_code="DB_ERROR"
            )

    def delete(self, prompt_id: int) -> None:
        """
        Delete a prompt and all its versions.

        Args:
            prompt_id (int): ID of the prompt to delete

        Raises:
            NotFoundError: If prompt doesn't exist
            AppException: If database operation fails
        """
        prompt = self.get(prompt_id)
        if not prompt:
            raise NotFoundError(detail=f"Prompt {prompt_id} not found")

        try:
            self.db.delete(prompt)
            self.db.commit()
            logger.info(f"Deleted prompt {prompt_id} and its versions")
        except SQLAlchemyError as e:
            logger.error(f"Error deleting prompt {prompt_id}: {str(e)}")
            self.db.rollback()
            raise AppException(
                status_code=500,
                detail="Failed to delete prompt",
                error_code="DB_ERROR"
            )

    def create_version(self, prompt_id: int, prompt_data: Optional[PromptBase] = None) -> Prompt:
        """
        Create a new version of a prompt.

        Args:
            prompt_id (int): ID of the prompt to version
            prompt_data (Optional[PromptBase]): New data for the version. If None, copies current version.

        Returns:
            Prompt: The new version of the prompt

        Raises:
            NotFoundError: If prompt not found
            ValidationError: If data validation fails
            AppException: For other errors
        """
        try:
            # Get current prompt
            prompt = self.get(prompt_id)
            if not prompt:
                raise NotFoundError(f"Prompt {prompt_id} not found")
            
            # First, store current version in prompt_versions
            version_record = PromptVersion(
                prompt_id=prompt.id,
                version=prompt.current_version,  # Store current version number
                description=prompt.description,  # Include description
                content=prompt.content,
                variables=prompt.variables,
                output_schema=prompt.output_schema,
                max_tokens=prompt.max_tokens,
                temperature=prompt.temperature
            )
            self.db.add(version_record)
            
            # Increment version numbers
            prompt.version_count += 1
            prompt.current_version = prompt.version_count
            
            # Now update prompt with new data
            if prompt_data:
                # Convert entire prompt_data to dict to ensure proper JSON serialization
                data = prompt_data.model_dump(exclude={'id', 'current_version', 'version_count'})
                for key, value in data.items():
                    if value is not None:
                        setattr(prompt, key, value)
            
            # Validate variables
            self.validate_variables(prompt_data.model_dump().get("variables", []) if prompt_data else prompt.variables)
            
            self.db.commit()
            self.db.refresh(prompt)
            
            logger.info(
                "Created new prompt version",
                extra={
                    "prompt_id": prompt.id,
                    "old_version": version_record.version,
                    "new_version": prompt.current_version,
                    "description": prompt.description
                }
            )
            
            return prompt
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating version for prompt {prompt_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to create prompt version",
                error_code="DB_ERROR"
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating prompt version: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to create prompt version",
                error_code="UNKNOWN_ERROR"
            )

    def publish(self, prompt_id: int) -> Prompt:
        """
        Publish a prompt by changing its status to PUBLISHED.
        
        This method validates the status transition and ensures the prompt
        meets all requirements for publishing.

        Args:
            prompt_id (int): ID of the prompt to publish

        Returns:
            Prompt: Published prompt instance

        Raises:
            NotFoundError: If prompt doesn't exist
            ValidationError: If status transition is invalid
            AppException: If database operation fails
        """
        prompt = self.get(prompt_id)
        if not prompt:
            raise NotFoundError(detail=f"Prompt {prompt_id} not found")

        if not prompt.status.can_transition_to(PromptStatus.PUBLISHED):
            raise ValidationError(
                detail=f"Cannot transition from {prompt.status} to {PromptStatus.PUBLISHED}"
            )

        try:
            prompt.status = PromptStatus.PUBLISHED
            self.db.commit()
            self.db.refresh(prompt)
            logger.info(f"Published prompt {prompt_id}")
            return prompt
        except SQLAlchemyError as e:
            logger.error(f"Error publishing prompt {prompt_id}: {str(e)}")
            self.db.rollback()
            raise AppException(
                status_code=500,
                detail="Failed to publish prompt",
                error_code="DB_ERROR"
            )

    def get_version(self, prompt_id: int, version: int) -> Optional[PromptVersion]:
        """
        Retrieve a specific version of a prompt.

        Args:
            prompt_id (int): ID of the prompt
            version (int): Version number to retrieve

        Returns:
            Optional[PromptVersion]: Found version or None if not found

        Raises:
            AppException: If database operation fails
        """
        try:
            return self.db.query(PromptVersion).filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.version == version
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving version {version} of prompt {prompt_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve prompt version",
                error_code="DB_ERROR"
            )

    def get_versions(self, prompt_id: int) -> Sequence[PromptVersion]:
        try:
            # Get the prompt first to get its details
            prompt = self.get(prompt_id)
            if not prompt:
                raise NotFoundError(detail=f"Prompt {prompt_id} not found")

            # Create a union query to get both historical and current versions
            versions_query = select(
                PromptVersion.prompt_id,
                PromptVersion.version,
                PromptVersion.description,
                PromptVersion.content,
                PromptVersion.variables.cast(JSON),
                PromptVersion.output_schema.cast(JSON),
                PromptVersion.max_tokens,
                PromptVersion.temperature,
                PromptVersion.created_at
            ).where(PromptVersion.prompt_id == prompt_id)

            # For the current version, use updated_at as created_at
            current_version_query = select(
                Prompt.id.label('prompt_id'),
                Prompt.current_version.label('version'),
                Prompt.description,
                Prompt.content,
                Prompt.variables.cast(JSON),
                Prompt.output_schema.cast(JSON),
                Prompt.max_tokens,
                Prompt.temperature,
                func.coalesce(Prompt.updated_at, Prompt.created_at).label('created_at')
                # Use coalesce to handle null updated_at
            ).where(Prompt.id == prompt_id)

            # Combine queries with UNION ALL and order by version descending
            final_query = versions_query.union_all(current_version_query).order_by(
                desc("version")
            )

            result = self.db.execute(final_query).all()
            logger.debug(f"Retrieved {len(result)} versions for prompt {prompt_id}")

            # Convert result to PromptVersion objects
            versions = []
            for row in result:
                version = PromptVersion(
                    prompt_id=row.prompt_id,
                    version=row.version,
                    description=row.description,
                    content=row.content,
                    variables=row.variables,
                    output_schema=row.output_schema,
                    max_tokens=row.max_tokens,
                    temperature=row.temperature,
                    created_at=row.created_at
                )
                # Set the prompt relationship for property access
                version.prompt = prompt
                versions.append(version)

            return versions

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving versions for prompt {prompt_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve prompt versions",
                error_code="DB_ERROR"
            )
    def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[Prompt]:
        """
        Get all prompts (latest versions only).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[Prompt]: List of prompts
        """
        try:
            query = (
                select(Prompt)
                .offset(skip)
                .limit(limit)
            )
            return self.db.scalars(query).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving prompts: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to retrieve prompts",
                error_code="DB_ERROR"
            )