from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum

from app.core.database import Base
from app.core.security import encrypt_value, decrypt_value


class SettingType(Enum):
    """Types of settings that can be stored"""
    API_KEY = "api_key"
    CONFIG = "config"


class Setting(Base):
    """
    Model for storing encrypted settings like API keys
    
    Uses Fernet encryption to store sensitive values. The encryption key
    should be stored in environment variables.
    """
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    key = Column(String, unique=True, nullable=False, index=True)
    type = Column(SQLEnum(SettingType), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    description = Column(String, nullable=True)

    @staticmethod
    def mask_value(value: str) -> str:
        """Mask sensitive values, showing only first and last 4 chars"""
        if not value or len(value) < 8:
            return "*" * len(value) if value else ""
        return f"{value[:4]}...{value[-4:]}"

    @property
    def value(self) -> str:
        """Get the setting value, masked for API keys"""
        decrypted = decrypt_value(self.encrypted_value)
        if self.type == SettingType.API_KEY:
            return self.mask_value(decrypted)
        return decrypted

    @value.setter
    def value(self, plain_value: str):
        """Encrypt and store the setting value"""
        self.encrypted_value = encrypt_value(plain_value)

    def get_decrypted_value(self) -> str:
        """Internal method to get the actual decrypted value when needed"""
        return decrypt_value(self.encrypted_value)
