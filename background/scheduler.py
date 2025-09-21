"""
Background task scheduler for the indexer.
"""
import logging
import threading
from typing import List

from indexer.auth import AuthManager

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """Manages background tasks for the indexer."""

    def __init__(self):
        self.threads: List[threading.Thread] = []

    def start_auth_scheduler(self, auth_manager: AuthManager):
        """Start the authentication scheduler in a background thread."""
        auth_thread = threading.Thread(
            target=auth_manager._proactive_auth_loop,
            daemon=True,
            name="auth-scheduler"
        )
        auth_thread.start()
        self.threads.append(auth_thread)
        logger.info("Authentication scheduler started in background")

    def get_active_threads(self) -> List[str]:
        """Get list of active background threads."""
        return [t.name for t in self.threads if t.is_alive()]


# Global scheduler instance
scheduler = BackgroundScheduler()


def start_background_tasks(auth_manager: AuthManager):
    """Initialize all background tasks."""
    logger.info("Starting background tasks...")
    scheduler.start_auth_scheduler(auth_manager)
    logger.info(f"Background tasks initialized: {scheduler.get_active_threads()}")