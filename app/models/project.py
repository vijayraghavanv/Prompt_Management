from sqlalchemy import Column, Integer, String, DateTime, Boolean, ARRAY, Enum as SQLEnum, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.schemas.project import ProjectStatus
from loguru import logger

class Project(Base):
    """
    SQLAlchemy model for projects table.
    Represents a project in the prompt management system.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(50),
        nullable=False,
        index=True,
        unique=True,  # Ensure project names are unique
    )
    description = Column(
        String(500),
        nullable=True
    )
    status = Column(
        SQLEnum(ProjectStatus),
        default=ProjectStatus.DRAFT,
        nullable=False
    )
    tags = Column(
        ARRAY(String(20)),  # Limit individual tag length to 20 chars
        default=list,
        nullable=False
    )
    version = Column(
        String(10),
        default="1.0.0",
        nullable=False
    )
    is_public = Column(
        Boolean,
        default=False,
        nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    prompt_count = Column(
        Integer,
        default=0,
        nullable=False
    )

    # Relationships
    prompts = relationship("Prompt", back_populates="project", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="project", cascade="all, delete-orphan")

    # Add constraints
    __table_args__ = (
        CheckConstraint('length(name) >= 3', name='check_name_length'),
        CheckConstraint('prompt_count >= 0', name='check_prompt_count_positive'),
        # Add constraint for version format if needed
        CheckConstraint(
            "version ~ '^\\d+\\.\\d+\\.\\d+$'",
            name='check_version_format'
        ),
        CheckConstraint('array_length(tags, 1) <= 5', name='max_tags_check'),
    )

    def __repr__(self):
        """String representation of the project"""
        return f"<Project(id={self.id}, name='{self.name}', status={self.status.value})>"

    def increment_prompt_count(self):
        """Increment the prompt count safely"""
        self.prompt_count += 1
        logger.debug(f"Incremented prompt count for project {self.id} to {self.prompt_count}")

    def decrement_prompt_count(self):
        """Decrement the prompt count safely"""
        if self.prompt_count > 0:
            self.prompt_count -= 1
            logger.debug(f"Decremented prompt count for project {self.id} to {self.prompt_count}")