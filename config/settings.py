"""
Centralized configuration management for MIRCrew Smart Indexer.
"""
import os
from typing import Optional


class Settings:
    """Application settings with validation."""

    def __init__(self):
        # MIRCrew settings
        self.mircrew_base_url: str = os.getenv('MIRCREW_BASE_URL', 'https://mircrew-releases.org')
        self.mircrew_username: Optional[str] = os.getenv('MIRCREW_USERNAME')
        self.mircrew_password: Optional[str] = os.getenv('MIRCREW_PASSWORD')

        # Sonarr settings
        self.sonarr_url: str = os.getenv('SONARR_URL', 'http://sonarr:8989')
        self.sonarr_api_key: Optional[str] = os.getenv('SONARR_API_KEY')

        # Application settings
        self.port: int = int(os.getenv('PORT', '9898'))
        self.running_in_docker: bool = os.getenv('RUNNING_IN_DOCKER', 'false').lower() == 'true'

        # Validate required settings
        self._validate()

    def _validate(self):
        """Validate required configuration settings."""
        missing = []
        if not self.mircrew_username:
            missing.append('MIRCREW_USERNAME')
        if not self.mircrew_password:
            missing.append('MIRCREW_PASSWORD')

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    @property
    def is_sonarr_configured(self) -> bool:
        """Check if Sonarr is configured."""
        return bool(self.sonarr_api_key)


# Global settings instance
settings = Settings()