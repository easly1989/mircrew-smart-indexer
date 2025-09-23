"""
Parsing utilities for episode information extraction and categorization.
"""
import re
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EpisodeParser:
    """Handles episode information extraction and parsing."""

    def extract_episode_info(self, text: str) -> Optional[Dict]:
        """Extract season and episode information from text."""
        # Handle empty/whitespace input
        if not text or text.isspace():
            logger.debug("Skipping episode extraction for empty text")
            return None

        season_pack_patterns = [
            r'complete\s*season\s*(\d+)',
            r'full\s*season\s*(\d+)',
            r'season\s*(\d+)\s*pack',
            r's(\d{1,2})\s*complete',
            r's(\d{1,2})\s*full',
            r's(\d{1,2})\s*complete\s*pack'
        ]
        for pattern in season_pack_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                season = int(match.group(1))
                return {
                    'season': season,
                    'full_season_pack': True
                }

        range_patterns = [
            r's(\d{1,2})e(\d{1,3})\s*-\s*e(\d{1,3})',
            r's(\d{1,2})e(\d{1,3})\s*-\s*s\d{1,2}e(\d{1,3})',
            r'episodes?\s*(\d+)[\s\-to]+(\d+)',
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                season = int(match.group(1))
                start_ep = int(match.group(2))
                end_ep = int(match.group(3))
                episode_range = list(range(start_ep, end_ep + 1))
                return {
                    'season': season,
                    'episode_range': episode_range
                }

        single_patterns = [
            r'S(\d{1,2})E(\d{1,3})',
            r'(\d{1,2})x(\d{1,3})',
            r'Stagion[ei]\s*(\d+).*?Episodio\s*(\d+)',
        ]
        for pattern in single_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    'season': int(match.group(1)),
                    'episode': int(match.group(2))
                }
        logger.warning(f"Failed to extract episode info from text: '{text}'")
        return None

    def parse_episode_from_context(self, soup: BeautifulSoup, magnet: str) -> Optional[Dict]:
        """Parse episode info from context around magnet link."""
        for text_elem in soup.find_all(string=re.compile(re.escape(magnet))):
            for level in range(3):
                current = text_elem
                for _ in range(level):
                    current = getattr(current, 'parent', None)
                    if not current:
                        break
                if current:
                    text = current.get_text() if hasattr(current, 'get_text') else str(current)
                    episode_info = self.extract_episode_info(text)
                    if episode_info:
                        return episode_info
        return None

    def matches_series(self, title1: str, title2: str) -> bool:
        """Check if two series titles match by comparing keywords."""
        norm1 = re.sub(r'[^\w\s]', '', title1.lower())
        norm2 = re.sub(r'[^\w\s]', '', title2.lower())
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'da', 'di', 'il', 'la', 'le', 'lo', 'gli', 'una', 'un', 'serie', 'season', 'stagione', 'complete', 'completa'}
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        common = words1.intersection(words2)
        return len(common) >= 1 and len(common) / max(len(words1), len(words2)) >= 0.3

    def contains_season(self, title: str, season: int) -> bool:
        """Check if title contains specific season number."""
        season_str = str(season)
        patterns = [
            rf'Season\s*0*{season}',                      # Season 1 or Season 01
            rf'Stagion[ei]\s*0*{season}(\s*-\s*0*\d+)?',  # Stagione 1 or Stagione 01-03
            rf'S0*{season}(\s*-\s*S0*\d+)?',              # S01 or S01-S05
            rf'S{season_str}',                            # S1 (without leading zero)
            rf'\b{season_str}\b',                         # '1' isolated (generic fallback)
            rf'Stagion[ei]\s*complete',                   # Stagione completa (without number)
            rf'\bcomplete\b',                             # 'complete' anywhere (generic)
            rf'\bcompleta\b',                             # 'completa' anywhere (italian)
            rf'S\d{1,2}-S\d{1,2}',                        # range S01-S05 generic
            rf'Stagion[ei]\s*\d{1,2}-\d{1,2}',            # range Stagione 01-03
        ]
        title_lower = title.lower()
        for pattern in patterns:
            if re.search(pattern, title_lower, flags=re.IGNORECASE):
                return True
        return False

    def estimate_size_from_title(self, title: str) -> int:
        """Estimate file size based on title content."""
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB)', title, re.IGNORECASE)
        if size_match:
            size_val = float(size_match.group(1))
            size_unit = size_match.group(2).upper()
            return int(size_val * (1024**3 if size_unit == 'GB' else 1024**2))
        if any(word in title.lower() for word in ['1080p', 'bluray']):
            return 2 * 1024**3
        elif any(word in title.lower() for word in ['720p', 'hdtv']):
            return 1024**3
        else:
            return 512 * 1024**2

    def categorize_title(self, title: str) -> str:
        """Categorize title based on content."""
        if any(word in title.lower() for word in ['s0', 'season', 'episode', 'stagione']):
            return '5000'
        elif any(word in title.lower() for word in ['movie', 'film']):
            return '2000'
        elif any(word in title.lower() for word in ['anime']):
            return '5070'
        else:
            return '8000'