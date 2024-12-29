from typing import Optional, Dict, List
import json
import os
import tempfile
import base64

import tiktoken
from llama_index.core import Settings, SimpleDirectoryReader
from llama_index.core.callbacks import TokenCountingHandler, CallbackManager
from llama_index.core.llms import LLM
from llama_index.core.schema import ImageDocument, Document
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic
from llama_index.multi_modal_llms.openai import OpenAIMultiModal
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ValidationError
from app.services.llm_system_service import LLMSystemService
from app.services.settings import SettingsService


class LlamaService:
    """Service for LlamaIndex operations"""

    _instance = None
    _is_initialized = False
    _settings = None
    _llm_instances: Dict[str, LLM] = {}
    _current_llm: Optional[LLM] = None
    _tokenizers: Dict[str, TokenCountingHandler] = {}  # Store tokenizers for each model

    def __new__(cls, db: Session = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db: Session = None):
        # Skip initialization if already done
        if LlamaService._is_initialized:
            return
            
        if db is None:
            raise ValueError("db is required for first initialization")
            
        self.db = db
        self.settings_service = SettingsService(db)
        self.llm_system_service = LLMSystemService(db)
        
        # Initialize tokenizers for all models
        self._initialize_tokenizers()
        
        LlamaService._is_initialized = True

    def _initialize_tokenizers(self):
        """Initialize tokenizers for all available models"""
        # Get all LLM systems
        systems = self.llm_system_service.list_all()
        
        for system in systems:
            if system.name.lower() == "openai":
                # For OpenAI, create tokenizer for each available model
                available_models = json.loads(system.available_models)
                for model in available_models:
                    self._tokenizers[model] = TokenCountingHandler(
                        tokenizer=tiktoken.encoding_for_model(model).encode
                    )
            elif system.name.lower() == "anthropic":
                # For Anthropic, create a single tokenizer for all models
                self._tokenizers["anthropic"] = TokenCountingHandler(
                    tokenizer=Anthropic().tokenizer.encode
                )

    def get_tokenizer(self, model: str) -> Optional[TokenCountingHandler]:
        """Get tokenizer for specified model"""
        # For Anthropic models, return the common tokenizer
        if any(name in model.lower() for name in ["claude", "anthropic"]):
            return self._tokenizers.get("anthropic")
        
        # For OpenAI models, return model-specific tokenizer
        return self._tokenizers.get(model)

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if service is initialized"""
        return cls._is_initialized

    def get_api_key(self, system_name: str) -> Optional[str]:
        """
        Get API key for a specific LLM system
        Returns None if key not configured
        """
        try:
            system = self.llm_system_service.get_by_name(system_name)
            if not system:
                return None
            return self.settings_service.get_decrypted_value(system.api_key_setting)
        except Exception:
            return None

    def is_ready(self) -> bool:
        """Check if service is ready to handle requests"""
        try:
            default_system = self.llm_system_service.get_default()
            if not default_system:
                return False
            api_key = self.get_api_key(default_system.name)
            return api_key is not None
        except Exception:
            return False

    def initialize(self) -> None:
        """
        Initialize LlamaIndex settings
        Does not require API key - will be initialized when needed
        """
        if self._settings:
            return

        # Initialize with base settings
        self._settings = Settings

    def ensure_llm_ready(self):
        """
        Ensure LLM is ready to use
        Raises AppException if not ready
        """
        if not self.is_ready():
            raise AppException("LLM service not ready - API key not configured")

    def process_image(self, base64_image: str) -> Document:
        """
        Process base64 image and create ImageDocument
        
        Args:
            base64_image: Base64 encoded image string
            
        Returns:
            ImageDocument for the processed image
            
        Raises:
            ValidationError: If image processing fails
        """
        try:
            # Create temp directory under app root if it doesn't exist
            app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            temp_dir = os.path.join(app_root, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Create unique filename
            import uuid
            temp_file = os.path.join(temp_dir, f"temp_image_{uuid.uuid4()}.jpg")
            
            # Remove data:image prefix if present
            if "base64," in base64_image:
                base64_image = base64_image.split("base64,")[1]
            
            # Decode and write image
            with open(temp_file, "wb") as f:
                f.write(base64.b64decode(base64_image))
            
            # Load image using SimpleDirectoryReader and add temp file path to metadata
            image_document: Document = SimpleDirectoryReader(
                input_files=[temp_file]
            ).load_data()[0]
            
            # Store temp file path in document metadata for cleanup
            if not image_document.metadata:
                image_document.metadata = {}
            image_document.metadata['temp_file'] = temp_file
            
            return image_document
                
        except Exception as e:
            # Clean up file if there's an error
            if 'temp_file' in locals() and os.path.exists(temp_file):
                os.remove(temp_file)
            raise ValidationError(f"Failed to process image: {str(e)}")

    def get_llm(self, model: str = None, is_multimodal: bool = False) -> LLM:
        """
        Get LLM instance
        
        Args:
            model: Optional model name to use, if not specified uses default
            is_multimodal: Whether this is a multimodal request
            
        Returns:
            LLM instance
            
        Raises:
            AppException: If not initialized or model invalid
        """
        self.ensure_llm_ready()
        
        if model:
            if model not in self._llm_instances:
                # Get current system's API key
                default_system = self.llm_system_service.get_default()
                api_key = self.get_api_key(default_system.name)
                
                # Set up token counter for this model
                tokenizer = self.get_tokenizer(model)
                if tokenizer:
                    Settings.callback_manager = CallbackManager([tokenizer])
                
                if default_system.name.lower() == "openai":
                    if is_multimodal:
                        self._llm_instances[model] = OpenAIMultiModal(
                            model=model,
                            api_key=api_key,
                            max_retries=3,
                            max_new_tokens=10000,
                            timeout=600,
                            image_detail='high'
                        )
                    else:
                        self._llm_instances[model] = OpenAI(
                            model=model,
                            api_key=api_key
                        )
                elif default_system.name.lower() == "anthropic":
                    self._llm_instances[model] = Anthropic(
                        model=model,
                        api_key=api_key
                    )
            return self._llm_instances[model]
        
        if not self._current_llm:
            # Initialize default LLM
            default_system = self.llm_system_service.get_default()
            api_key = self.get_api_key(default_system.name)
            model = default_system.default_model
            
            # Set up token counter for default model
            tokenizer = self.get_tokenizer(model)
            if tokenizer:
                Settings.callback_manager = CallbackManager([tokenizer])
            
            if default_system.name.lower() == "openai":
                if is_multimodal:
                    self._current_llm = OpenAIMultiModal(
                        model=model,
                        api_key=api_key,
                        max_retries=3,
                        max_new_tokens=10000,
                        timeout=600,
                        image_detail='high'
                    )
                else:
                    self._current_llm = OpenAI(
                        model=model,
                        api_key=api_key
                    )
            elif default_system.name.lower() == "anthropic":
                self._current_llm = Anthropic(
                    model=model,
                    api_key=api_key
                )
        return self._current_llm

    def get_token_counts(self) -> Dict[str, int]:
        """
        Get current token counts from the active token counter
        
        Returns:
            Dictionary containing embedding, prompt, completion and total token counts
        """
        if not Settings.callback_manager or not Settings.callback_manager.handlers:
            return {
                "embedding_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
            
        # Get the token counter from handlers
        token_counter = next(
            (handler for handler in Settings.callback_manager.handlers 
             if isinstance(handler, TokenCountingHandler)),
            None
        )
        
        if not token_counter:
            return {
                "embedding_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
            
        return {
            "embedding_tokens": token_counter.total_embedding_token_count,
            "prompt_tokens": token_counter.prompt_llm_token_count,
            "completion_tokens": token_counter.completion_llm_token_count,
            "total_tokens": token_counter.total_llm_token_count
        }

    def reset_token_counter(self):
        """Reset the token counter to get fresh counts for next LLM call"""
        if Settings.callback_manager and Settings.callback_manager.handlers:
            token_counter = next(
                (handler for handler in Settings.callback_manager.handlers 
                 if isinstance(handler, TokenCountingHandler)),
                None
            )
            if token_counter:
                token_counter.reset_counts()
