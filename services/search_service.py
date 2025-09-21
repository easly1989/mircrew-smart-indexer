"""
Search service for coordinating search operations.
"""
from typing import List, Dict, Optional
from utils.logging import get_logger

from indexer.core import MIRCrewSmartIndexer

logger = get_logger(__name__)


class SearchService:
    """Service for handling search operations."""

    def __init__(self, indexer: MIRCrewSmartIndexer):
        self.indexer = indexer

    def perform_tv_search(self, query: str, season: Optional[int] = None) -> List[Dict]:
        """
        Perform TV search with smart episode expansion.

        Args:
            query: Search query
            season: Season number (optional)

        Returns:
            List of search results
        """
        try:
            logger.info(f"Performing TV search: query='{query}', season={season}")
            results = self.indexer.search_mircrew_smart_tv(query, season)
            logger.info(f"TV search completed: {len(results)} results found")
            return results
        except Exception as e:
            logger.error(f"Error in TV search: {e}")
            return []

    def perform_general_search(self, query: str, category: Optional[str] = None) -> List[Dict]:
        """
        Perform general search (movies, music, etc.).

        Args:
            query: Search query
            category: Category filter

        Returns:
            List of search results
        """
        # For now, delegate to existing functionality
        # In future, could implement different search strategies
        try:
            logger.info(f"Performing general search: query='{query}', category={category}")
            # Placeholder - implement based on requirements
            results = []
            logger.info(f"General search completed: {len(results)} results found")
            return results
        except Exception as e:
            logger.error(f"Error in general search: {e}")
            return []