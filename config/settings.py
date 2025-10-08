"""
Configuration settings for MIRCrew Smart Indexer.
"""
import os
from typing import Optional


class Settings:
    """Application configuration settings."""

    # MIRCrew settings
    mircrew_base_url: str = os.getenv('MIRCREW_BASE_URL', 'https://mircrew-releases.org')
    mircrew_username: Optional[str] = os.getenv('MIRCREW_USERNAME')
    mircrew_password: Optional[str] = os.getenv('MIRCREW_PASSWORD')

    # Sonarr settings
    sonarr_url: str = os.getenv('SONARR_URL', 'http://sonarr:8989')
    sonarr_api_key: Optional[str] = os.getenv('SONARR_API_KEY')

    # Server settings
    port: int = int(os.getenv('PORT', '9898'))
    running_in_docker: bool = os.getenv('RUNNING_IN_DOCKER', 'false').lower() == 'true'

    # Database settings
    @property
    def database_url(self) -> str:
        return os.getenv('DATABASE_URL', 'sqlite:////config/smart-indexer.db' if self.running_in_docker else 'sqlite:///smart-indexer.db')


    # Cache TTL settings (in seconds)
    thread_metadata_ttl: int = int(os.getenv('THREAD_METADATA_TTL', str(24 * 3600)))  # 24 hours
    like_counts_ttl: int = int(os.getenv('LIKE_COUNTS_TTL', str(1 * 3600)))  # 1 hour
    user_like_status_ttl: int = int(os.getenv('USER_LIKE_STATUS_TTL', str(15 * 60)))  # 15 minutes
    search_results_ttl: int = int(os.getenv('SEARCH_RESULTS_TTL', str(30 * 60)))  # 30 minutes

    # Session settings
    session_ttl: int = int(os.getenv('SESSION_TTL', str(6 * 3600)))  # 6 hours
    csrf_token_ttl: int = int(os.getenv('CSRF_TOKEN_TTL', str(1 * 3600)))  # 1 hour

    # Rate limiting
    rate_limit_window: int = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds
    rate_limit_max_requests: int = int(os.getenv('RATE_LIMIT_MAX_REQUESTS', '10'))


# Global settings instance
settings = Settings()