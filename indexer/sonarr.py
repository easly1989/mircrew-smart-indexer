"""
Sonarr API client for episode management.
"""
import os
import logging
import requests
from typing import List, Dict, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class SonarrClient:
    """Client for interacting with Sonarr API."""

    def __init__(self):
        self.sonarr_url = settings.sonarr_url
        self.sonarr_api = settings.sonarr_api_key
        self.session = requests.Session()
        if self.sonarr_api:
            self.session.headers.update({'X-Api-Key': self.sonarr_api})

    def is_configured(self) -> bool:
        return bool(self.sonarr_api)

    def get_missing_episodes(self, series_title: str, season: int) -> List[Dict]:
        """
        Retrieve missing episodes for a series from Sonarr.

        Args:
            series_title: Name of the series
            season: Season number to check

        Returns:
            List of dictionaries containing episode information
        """
        if not self.sonarr_api:
            logger.warning("Sonarr API key not set; cannot contact Sonarr.")
            return []

        try:
            response = self.session.get(f"{self.sonarr_url}/api/v3/series", timeout=10)
            if response.status_code != 200:
                logger.error(f"Sonarr series request failed: {response.status_code}")
                return []
            series_list = response.json()
            series_id = None
            for series in series_list:
                if self._matches_series(series['title'], series_title):
                    series_id = series['id']
                    break
            if not series_id:
                logger.info(f"Series {series_title} not found in Sonarr")
                return []
            response = self.session.get(f"{self.sonarr_url}/api/v3/episode?seriesId={series_id}", timeout=10)
            if response.status_code != 200:
                logger.error(f"Sonarr episodes request failed: {response.status_code}")
                return []
            episodes = response.json()
            missing = []
            for ep in episodes:
                if (ep.get('seasonNumber') == season and
                    ep.get('monitored', False) and
                    not ep.get('hasFile', False)):
                    missing.append({
                        'season': ep['seasonNumber'],
                        'episode': ep['episodeNumber']
                    })
            logger.info(f"Found {len(missing)} missing episodes in Sonarr for {series_title} S{season}")
            return missing
        except Exception as e:
            logger.error(f"Sonarr API error: {e}")
            return []

    def _matches_series(self, title1: str, title2: str) -> bool:
        """Check if two series titles match."""
        import re
        norm1 = re.sub(r'[^\w\s]', '', title1.lower())
        norm2 = re.sub(r'[^\w\s]', '', title2.lower())
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'da', 'di', 'il', 'la', 'le', 'lo', 'gli', 'una', 'un', 'serie', 'season', 'stagione', 'complete', 'completa'}
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        common = words1.intersection(words2)
        return len(common) >= 1 and len(common) / max(len(words1), len(words2)) >= 0.3