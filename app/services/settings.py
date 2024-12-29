from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.settings import Setting, SettingType
from app.schemas.settings import SettingCreate, SettingUpdate
from app.core.exceptions import AppException, NotFoundError, ValidationError


class SettingsService:
    """Service for managing application settings"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, setting_id: int) -> Optional[Setting]:
        """Get a setting by ID"""
        return self.db.query(Setting).filter(Setting.id == setting_id).first()

    def get_by_key(self, key: str) -> Optional[Setting]:
        """Get a setting by its key"""
        return self.db.query(Setting).filter(Setting.key == key).first()

    def get_decrypted_value(self, key: str) -> str:
        """
        Get the actual decrypted value for a setting
        
        This method should only be used internally by other services
        that need to use the actual value (e.g., LlamaIndex service)
        
        Args:
            key: Setting key to get value for
            
        Returns:
            Decrypted value
            
        Raises:
            NotFoundError: If setting doesn't exist
        """
        setting = self.get_by_key(key)
        if not setting:
            raise NotFoundError(f"Setting with key '{key}' not found")
        return setting.get_decrypted_value()

    def list_all(self) -> List[Setting]:
        """List all settings"""
        return self.db.query(Setting).all()

    def create(self, setting: SettingCreate) -> Setting:
        """
        Create a new setting
        
        Args:
            setting: Setting data
            
        Returns:
            Created setting
            
        Raises:
            ValidationError: If setting with key already exists
            AppException: If database operation fails
        """
        try:
            # Check if key already exists
            if self.get_by_key(setting.key):
                raise ValidationError(f"Setting with key '{setting.key}' already exists")

            # Create new setting
            db_setting = Setting(
                key=setting.key,
                type=setting.type,
                description=setting.description
            )
            # Set value through property to trigger encryption
            db_setting.value = setting.value

            self.db.add(db_setting)
            self.db.commit()
            self.db.refresh(db_setting)

            return db_setting

        except SQLAlchemyError as e:
            logger.error(f"Error creating setting: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to create setting",
                error_code="DB_ERROR"
            )

    def update(self, setting_id: int, setting: SettingUpdate) -> Setting:
        """
        Update a setting
        
        Args:
            setting_id: ID of setting to update
            setting: New setting data
            
        Returns:
            Updated setting
            
        Raises:
            NotFoundError: If setting not found
            AppException: If database operation fails
        """
        try:
            db_setting = self.get(setting_id)
            if not db_setting:
                raise NotFoundError(f"Setting {setting_id} not found")

            # Update fields if provided
            if setting.value is not None:
                db_setting.value = setting.value
            if setting.description is not None:
                db_setting.description = setting.description

            self.db.commit()
            self.db.refresh(db_setting)

            return db_setting

        except SQLAlchemyError as e:
            logger.error(f"Error updating setting {setting_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to update setting",
                error_code="DB_ERROR"
            )

    def delete(self, setting_id: int):
        """
        Delete a setting
        
        Args:
            setting_id: ID of setting to delete
            
        Raises:
            NotFoundError: If setting not found
            AppException: If database operation fails
        """
        try:
            db_setting = self.get(setting_id)
            if not db_setting:
                raise NotFoundError(f"Setting {setting_id} not found")

            self.db.delete(db_setting)
            self.db.commit()

        except SQLAlchemyError as e:
            logger.error(f"Error deleting setting {setting_id}: {str(e)}")
            raise AppException(
                status_code=500,
                detail="Failed to delete setting",
                error_code="DB_ERROR"
            )

    def get_api_key(self, key: str) -> Optional[str]:
        """
        Get decrypted API key by its key name
        
        Args:
            key: Key name of the API key setting
            
        Returns:
            Decrypted API key or None if not found
        """
        setting = self.get_by_key(key)
        if setting and setting.type == SettingType.API_KEY:
            return setting.value
        return None
