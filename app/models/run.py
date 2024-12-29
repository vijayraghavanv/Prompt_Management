from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.database import Base

class Run(Base):
    """
    Model for storing prompt runs

    Each run represents a single execution of a prompt version with specific input variables.
    Stores both the input and output along with metadata about the execution.
    """
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign keys
    prompt_id = Column(Integer, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Run details
    version = Column(Integer, nullable=False)
    input_variables = Column(JSON, nullable=False)
    output = Column(String, nullable=False)
    model = Column(String(50), nullable=False)
    
    # Token usage
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    embedding_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=False)
    
    # Performance
    latency_ms = Column(Integer, nullable=False)
    run_metadata = Column(JSON, nullable=False, default=dict)

    # Relationships
    prompt = relationship("Prompt", back_populates="runs")
    project = relationship("Project", back_populates="runs")

    @property
    def token_usage(self):
        """Get token usage stats as a TokenUsage object"""
        from app.schemas.run import TokenUsage
        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            embedding_tokens=self.embedding_tokens,
            total_tokens=self.total_tokens
        )
