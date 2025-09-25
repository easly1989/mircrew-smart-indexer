"""
Search service for coordinating search operations.
"""
from typing import List, Dict, Optional, Tuple
from utils.logging import get_logger

from indexer.core import MIRCrewSmartIndexer
from services.cache_service import CacheService

logger = get_logger(__name__)


class SearchService:
    """Service for handling search operations."""

    def __init__(self, indexer: MIRCrewSmartIndexer, cache_service: Optional[CacheService] = None):
        self.indexer = indexer
        self.cache = cache_service or CacheService()

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

    def search_episodes(self, query: str, season: Optional[int] = None,
                       user_id: Optional[str] = None, page: int = 1,
                       limit: int = 50) -> Tuple[List[Dict], int]:
        """
        Search for episodes with caching, pagination, and authorization.

        Args:
            query: Search query
            season: Season number (optional)
            user_id: User ID for authorization (optional)
            page: Page number (1-based)
            limit: Results per page

        Returns:
            Tuple of (results, total_count)
        """
        # Authorization check - for now, allow anonymous access
        # In future, could add user-based restrictions

        # Check cache first
        cache_key = f"episodes:{query}:{season or ''}"
        cached = self.cache.get_search_results(cache_key, season)
        if cached:
            logger.info(f"Cache hit for search: {cache_key}")
            all_results = cached.get('results', [])
            total_count = len(all_results)

            # Apply pagination to cached results
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_results = all_results[start_idx:end_idx]

            return paginated_results, total_count

        # Perform search
        try:
            logger.info(f"Searching episodes: query='{query}', season={season}, page={page}, limit={limit}")
            all_results = self.perform_tv_search(query, season)
            total_count = len(all_results)

            # Cache all results
            cache_data = {
                'results': all_results,
                'total': total_count,
                'query': query,
                'season': season
            }
            self.cache.set_search_results(cache_key, season, cache_data)

            # Apply pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_results = all_results[start_idx:end_idx]

            logger.info(f"Search completed: {len(paginated_results)} results (page {page} of {total_count})")
            return paginated_results, total_count

        except Exception as e:
            logger.error(f"Error in episode search: {e}")
            # Return empty results on error
            return [], 0

    def get_episode_by_id(self, episode_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get a specific episode by ID with authorization check.

        Args:
            episode_id: Episode GUID
            user_id: User ID for authorization (optional)

        Returns:
            Episode data or None if not found
        """
        # Authorization check - for now, allow anonymous access

        try:
            logger.info(f"Getting episode by ID: {episode_id}")

            # Check if episode is in recent search cache
            # This is a simplified implementation - in production, episodes should be stored in database

            # For now, we can't efficiently retrieve by ID without searching
            # Return None to indicate not implemented
            # In a full implementation, this would query a database table of episodes
            logger.warning(f"Episode retrieval by ID not implemented - would require database storage")
            return None

        except Exception as e:
            logger.error(f"Error getting episode {episode_id}: {e}")
            return None