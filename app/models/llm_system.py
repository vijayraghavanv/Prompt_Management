from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class LLMSystem(Base):
    """
    Model for storing LLM system configurations
    
    This stores information about different LLM providers (OpenAI, Claude, etc.)
    and their configuration details.
    """
    __tablename__ = "llm_systems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)  # e.g., "OpenAI", "Claude"
    api_key_setting = Column(String, nullable=False)  # e.g., "openai_api_key"
    default_model = Column(String, nullable=False)  # e.g., "gpt-4-turbo"
    default_multimodal = Column(String, nullable=True)  # e.g., "gpt-4-vision"
    available_models = Column(String, nullable=False)  # JSON string of available models
    is_default = Column(Boolean, default=False)  # Whether this is the default LLM system
