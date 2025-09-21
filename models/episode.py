"""
Episode data models.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class EpisodeInfo:
    """Information about a TV episode."""
    season: int
    episode: int
    title: str
    full_season_pack: bool = False
    episode_range: Optional[list] = None


@dataclass
class SearchResult:
    """Torznab search result."""
    title: str
    guid: str
    link: str
    pub_date: str
    size: int
    magnet: str
    seeders: int
    peers: int
    category: str
    season: Optional[int] = None
    episode: Optional[int] = None
    thread_id: Optional[str] = None
    thread_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'guid': self.guid,
            'link': self.link,
            'pubDate': self.pub_date,
            'size': self.size,
            'magnet': self.magnet,
            'seeders': self.seeders,
            'peers': self.peers,
            'category': self.category,
            'season': self.season,
            'episode': self.episode,
            'thread_id': self.thread_id,
            'thread_url': self.thread_url,
        }


@dataclass
class ThreadInfo:
    """Information about a forum thread."""
    thread_id: str
    title: str
    url: Optional[str] = None