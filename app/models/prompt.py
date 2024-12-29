from datetime import datetime
from typing import List
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, JSON, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.schemas.prompt import PromptStatus

class Prompt(Base):
    """Prompt model"""
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    content = Column(String(10000), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    variables = Column(JSON, default=list)
    output_schema = Column(JSONB, nullable=True)
    max_tokens = Column(Integer, nullable=False)
    temperature = Column(Float, default=0.7)
    status = Column(SQLEnum(PromptStatus), default=PromptStatus.DRAFT)
    current_version = Column(Integer, default=1)
    version_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="prompts")
    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="prompt", cascade="all, delete-orphan")

    # Ensure unique prompt names within a project
    __table_args__ = (
        UniqueConstraint('name', 'project_id', name='uix_prompt_name_project'),
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    prompt_id = Column(Integer, ForeignKey("prompts.id"), primary_key=True)
    version = Column(Integer, primary_key=True)  # Version is part of primary key
    description = Column(String(500))
    content = Column(String(10000), nullable=False)
    variables = Column(JSON, default=list)
    max_tokens = Column(Integer, nullable=False)
    temperature = Column(Float)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Add these properties to match the schema requirements
    @property
    def prompt_name(self):
        return self.prompt.name if self.prompt else None

    @property
    def prompt_description(self):
        return self.prompt.description if self.prompt else None

    @property
    def project_id(self):
        return self.prompt.project_id if self.prompt else None
    
    # Relationships
    prompt = relationship("Prompt", back_populates="versions")

    # Ensure versions start from 0 and are unique per prompt
    __table_args__ = (
        UniqueConstraint('prompt_id', 'version', name='uix_prompt_version'),
    )
