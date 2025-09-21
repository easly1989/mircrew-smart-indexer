"""
General utility functions for MIRCrew Smart Indexer.
"""
import re
from typing import Optional, Dict


def clean_query_string(query: str) -> str:
    """Clean and normalize query string for searching."""
    return re.sub(r'[^\w\s]', '', query).strip()


def extract_season_episode(text: str) -> Optional[Dict[str, int]]:
    """
    Extract season and episode from text.

    Returns:
        Dict with 'season' and 'episode' keys, or None if not found.
    """
    # Simple S01E01 pattern
    match = re.search(r'S(\d{1,2})E(\d{1,3})', text, re.IGNORECASE)
    if match:
        return {
            'season': int(match.group(1)),
            'episode': int(match.group(2))
        }
    return None


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return url_pattern.match(url) is not None


def safe_get_env(key: str, default: str = "") -> str:
    """Safely get environment variable."""
    import os
    return os.getenv(key, default)