from typing import List, Optional, TypeVar, Type
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from loguru import logger
from fastapi import status as http_status  # Rename to avoid collision

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectStatus
from app.core.exceptions import NotFoundError, ValidationError, AppException

ProjectModel = TypeVar('ProjectModel', bound=Project)

class ProjectService:
    """
    Service class for handling project-related database operations.

    Attributes:
        db (Session): SQLAlchemy database session
        model (Type[ProjectModel]): Project model class reference
    """

    def __init__(self, db: Session):
        self.db = db
        self.model: Type[ProjectModel] = Project  # Define model class reference

    def create_project(self, project: ProjectCreate) -> Project:
        """
        Create a new project in the database.

        Args:
            project (ProjectCreate): Project data validated by Pydantic model

        Returns:
            Project: The created project instance

        Raises:
            ValidationError: If project with same name exists
            AppException: For database errors
        """
        try:
            db_project = Project(**project.model_dump())
            self.db.add(db_project)
            self.db.commit()
            self.db.refresh(db_project)
            logger.info(
                "Project created successfully",
                extra={
                    "project_id": db_project.id,
                    "project_name": db_project.name,
                    "status": db_project.status.value
                }
            )
            return db_project
        except IntegrityError as e:
            logger.error(
                "Project creation failed - integrity error",
                extra={"error": str(e), "project_name": project.name}
            )
            self.db.rollback()
            raise ValidationError("Project with this name already exists")
        except SQLAlchemyError as e:
            logger.error(
                "Project creation failed - database error",
                extra={"error": str(e), "project_name": project.name}
            )
            self.db.rollback()
            raise AppException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating project",
                error_code="DB_ERROR"
            )

    def get_project(self, project_id: int) -> ProjectModel:
        """
        Retrieve a project by its ID.

        Args:
            project_id (int): Unique identifier of the project

        Returns:
            ProjectModel: The retrieved project

        Raises:
            NotFoundError: If project with given ID doesn't exist
            AppException: For database errors
        """
        try:
            project = self.db.get(self.model, project_id)
            if not project:
                logger.warning(f"Project not found", extra={"project_id": project_id})
                raise NotFoundError(f"Project with ID {project_id} not found")

            logger.debug(
                "Project retrieved",
                extra={
                    "project_id": project.id,
                    "project_name": project.name
                }
            )
            return project
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(
                "Project retrieval failed",
                extra={"error": str(e), "project_id": project_id}
            )
            raise AppException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while retrieving project",
                error_code="DB_ERROR"
            )

    def get_projects(
            self,
            skip: int = 0,
            limit: int = 100,
            status: Optional[ProjectStatus] = None,
            tag: Optional[str] = None
    ) -> List[ProjectModel]:
        """
        Retrieve a list of projects with optional filtering.

        Args:
            skip (int, optional): Number of records to skip. Defaults to 0.
            limit (int, optional): Maximum number of records to return. Defaults to 100.
            status (ProjectStatus, optional): Filter by project status. Defaults to None.
            tag (str, optional): Filter by project tag. Defaults to None.

        Returns:
            List[ProjectModel]: List of projects matching the criteria

        Raises:
            ValidationError: If tag length is invalid
            AppException: For database errors
        """
        try:
            from sqlalchemy import and_  # Add this import at the top of file

            query = self.db.query(self.model)

            if status:
                query = query.filter(and_(self.model.status == status))
            if tag:
                if not (2 <= len(tag) <= 20):
                    raise ValidationError("Tag length must be between 2 and 20 characters")
                query = query.filter(and_(self.model.tags.contains([tag])))

            projects = query.offset(skip).limit(limit).all()
            logger.info(
                "Projects retrieved successfully",
                extra={
                    "count": len(projects),
                    "skip": skip,
                    "limit": limit,
                    "status_filter": status.value if status else None,
                    "tag_filter": tag
                }
            )
            return projects
        except SQLAlchemyError as e:
            logger.error(
                "Project listing failed",
                extra={"error": str(e), "status": status, "tag": tag}
            )
            raise AppException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing projects",
                error_code="DB_ERROR"
            )

    def update_project(self, project_id: int, project_update: ProjectUpdate) -> Project:
        """
        Update an existing project.

        Args:
            project_id (int): ID of the project to update
            project_update (ProjectUpdate): Updated project data

        Returns:
            Project: The updated project instance

        Raises:
            NotFoundError: If project doesn't exist
            ValidationError: For integrity violations
            AppException: For database errors
        """
        try:
            db_project = self.get_project(project_id)

            update_data = project_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_project, field, value)

            self.db.commit()
            self.db.refresh(db_project)

            logger.info(
                "Project updated successfully",
                extra={
                    "project_id": db_project.id,
                    "project_name": db_project.name,
                    "updated_fields": list(update_data.keys())
                }
            )
            return db_project
        except IntegrityError as e:
            logger.error(
                "Project update failed - integrity error",
                extra={
                    "error": str(e),
                    "project_id": project_id,
                    "update_data": update_data
                }
            )
            self.db.rollback()
            raise ValidationError("Invalid update data")
        except SQLAlchemyError as e:
            logger.error(
                "Project update failed - database error",
                extra={"error": str(e), "project_id": project_id}
            )
            self.db.rollback()
            raise AppException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while updating project",
                error_code="DB_ERROR"
            )

    def delete_project(self, project_id: int) -> None:
        """
        Delete a project from the database.

        Args:
            project_id (int): ID of the project to delete

        Raises:
            NotFoundError: If project doesn't exist
            AppException: For database errors
        """
        try:
            db_project = self.get_project(project_id)
            project_name = db_project.name  # Store for logging

            self.db.delete(db_project)
            self.db.commit()

            logger.info(
                "Project deleted successfully",
                extra={
                    "project_id": project_id,
                    "project_name": project_name
                }
            )
        except SQLAlchemyError as e:
            logger.error(
                "Project deletion failed",
                extra={"error": str(e), "project_id": project_id}
            )
            self.db.rollback()
            raise AppException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while deleting project",
                error_code="DB_ERROR"
            )

    def increment_prompt_count(self, project_id: int) -> Project:
        """
        Increment the prompt count for a project by one.

        Args:
            project_id (int): ID of the project

        Returns:
            Project: The updated project instance

        Raises:
            NotFoundError: If project doesn't exist
            AppException: For database errors
        """
        try:
            db_project = self.get_project(project_id)
            db_project.increment_prompt_count()  # Using model method

            self.db.commit()
            self.db.refresh(db_project)

            logger.info(
                "Project prompt count incremented",
                extra={
                    "project_id": project_id,
                    "new_count": db_project.prompt_count
                }
            )
            return db_project
        except SQLAlchemyError as e:
            logger.error(
                "Prompt count increment failed",
                extra={"error": str(e), "project_id": project_id}
            )
            self.db.rollback()
            raise AppException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while updating prompt count",
                error_code="DB_ERROR"
            )