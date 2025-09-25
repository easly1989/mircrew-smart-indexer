"""
General utility functions for MIRCrew Smart Indexer.
"""
import re
from typing import Optional, Dict, List, Any
import xml.etree.ElementTree as ET
from flask import Response
from datetime import datetime


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
    match = re.search(r'S(\d{1,3})E(\d{1,3})', text, re.IGNORECASE)
    if match:
        return {
            'season': int(match.group(1)),
            'episode': int(match.group(2))
        }
    return None


def validate_url(url) -> bool:
    """Basic URL validation."""
    if not isinstance(url, str):
        return False

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


def parse_torrent_filename(filename) -> Optional[Dict[str, Any]]:
    """
    Parse torrent filename to extract metadata.

    Args:
        filename: The torrent filename

    Returns:
        Dict with parsed metadata or None if parsing fails
    """
    if not filename or not isinstance(filename, str):
        return None

    # Remove file extension
    filename = re.sub(r'\.(torrent|mkv|mp4|avi|mov)$', '', filename, flags=re.IGNORECASE)

    # Common patterns for TV shows
    patterns = [
        # Show.Name.S01E01.1080p.WEB-DL.x264-Group
        r'^(.+?)\.S(\d{1,2})E(\d{1,3})\.(.+?)(?:\.(x264|h264|avc))?(?:-(\w+))?$',
        # Show.Name.S01E01E02.1080p (double episode)
        r'^(.+?)\.S(\d{1,2})E(\d{1,3})E(\d{1,3})\.(.+?)$',
        # Show.Name.S01E01.1080p.WEB-DL.x264-Group (simpler)
        r'^(.+?)\.S(\d{1,2})E(\d{1,3})\.(.+?)$',
        # Show Name - S01E01 - Episode Title
        r'^(.+?)\s*-\s*S(\d{1,2})E(\d{1,3})\s*-\s*(.+)$',
    ]

    for pattern_idx, pattern in enumerate(patterns):
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            groups = match.groups()
            show_name = groups[0].replace('.', ' ').strip()
            season = int(groups[1])
            episode = int(groups[2])

            # Parse remaining parts for quality and group
            quality = ''
            group = ''

            # Check if group was captured by regex (for pattern 1)
            if len(groups) >= 6 and groups[5]:  # Pattern 1 has group in groups[5]
                group = groups[5]
                remaining = groups[3]  # quality part
                quality_keywords = ['1080p', '720p', '480p', '2160p', '4k', 'hdtv', 'web-dl', 'bluray', 'dvdrip']
                if remaining.lower() in quality_keywords:
                    quality = remaining
            elif pattern_idx == 1:  # Double episode pattern
                remaining = groups[4] if len(groups) > 4 else ''
                quality_keywords = ['1080p', '720p', '480p', '2160p', '4k', 'hdtv', 'web-dl', 'bluray', 'dvdrip']
                if remaining.lower() in quality_keywords:
                    quality = remaining
            else:
                # For other patterns, groups[3] contains everything after episode
                if len(groups) > 3 and groups[3]:
                    remaining = groups[3]

                    # Split by dots
                    parts = remaining.split('.')

                    # Find the rightmost dash-separated group (usually after codec)
                    quality_parts = []

                    for i, part in enumerate(parts):
                        if '-' in part:
                            # This might be codec-group
                            codec_and_group = part.split('-', 1)
                            if len(codec_and_group) == 2:
                                # Check if first part looks like a codec
                                codec = codec_and_group[0].lower()
                                if codec in ['x264', 'h264', 'avc', 'x265', 'h265', 'hevc']:
                                    group = codec_and_group[1]
                                    quality_parts = parts[:i]  # Everything before codec is quality
                                    break

                    # If no codec-group found, quality is all parts
                    if not quality_parts:
                        quality_parts = parts

                    # Find quality from quality parts
                    quality_keywords = ['1080p', '720p', '480p', '2160p', '4k', 'hdtv', 'web-dl', 'bluray', 'dvdrip']
                    for part in quality_parts:
                        part_lower = part.lower()
                        if any(q in part_lower for q in quality_keywords):
                            quality = part
                            break

            result = {
                'show_name': show_name,
                'season': season,
                'episode': episode,
                'quality': quality,
                'group': group
            }

            # Handle double episodes (pattern_idx == 1)
            if pattern_idx == 1 and len(groups) >= 4:
                result['episode_range'] = [result['episode'], int(groups[3])]

            return result

    # Fallback: try to extract basic info
    season_ep_match = re.search(r'S(\d{1,2})E(\d{1,3})', filename, re.IGNORECASE)
    if season_ep_match:
        show_name = re.sub(r'S\d{1,2}E\d{1,3}.*', '', filename).replace('.', ' ').strip()
        return {
            'show_name': show_name,
            'season': int(season_ep_match.group(1)),
            'episode': int(season_ep_match.group(2)),
            'quality': '',
            'group': ''
        }

    return None


def validate_sonarr_episode_data(episode_data) -> bool:
    """
    Validate episode data from Sonarr API.

    Args:
        episode_data: Episode data dictionary from Sonarr

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(episode_data, dict):
        return False

    required_fields = ['seasonNumber', 'episodeNumber', 'title']
    for field in required_fields:
        if field not in episode_data:
            return False

    # Validate types
    if not isinstance(episode_data.get('seasonNumber'), int) or episode_data['seasonNumber'] < 0:
        return False

    if not isinstance(episode_data.get('episodeNumber'), int) or episode_data['episodeNumber'] < 0:
        return False

    if not isinstance(episode_data.get('title'), str) or not episode_data['title'].strip():
        return False

    # Optional fields validation
    if 'hasFile' in episode_data and not isinstance(episode_data['hasFile'], bool):
        return False

    if 'monitored' in episode_data and not isinstance(episode_data['monitored'], bool):
        return False

    return True


def generate_torznab_response(results: List[Dict[str, Any]], error_message: Optional[str] = None) -> Response:
    """
    Generate Torznab-compatible XML response.

    Args:
        results: List of result dictionaries
        error_message: Optional error message

    Returns:
        Flask Response with XML content
    """
    if error_message:
        return Response(f'<?xml version="1.0" encoding="UTF-8"?><error code="100" description="{error_message}"/>',
                       mimetype='application/xml')

    # Register namespaces
    ET.register_namespace("torznab", "http://torznab.com/schemas/2015/feed")
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    rss.set('xmlns:torznab', 'http://torznab.com/schemas/2015/feed')

    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'MIRCrew Smart Indexer'
    ET.SubElement(channel, 'description').text = 'MIRCrew Smart Indexer for TV Series'
    ET.SubElement(channel, 'link').text = 'https://mircrew.com'
    ET.SubElement(channel, 'language').text = 'en-us'

    for result in results:
        if not isinstance(result, dict):
            continue

        item = ET.SubElement(channel, 'item')

        # Required fields
        title = result.get('title', 'Unknown')
        ET.SubElement(item, 'title').text = str(title)

        guid = result.get('guid', f"mircrew-{result.get('thread_id', '0')}")
        ET.SubElement(item, 'guid').text = str(guid)

        link = result.get('link') or result.get('thread_url', '')
        if link:
            ET.SubElement(item, 'link').text = str(link)

        pub_date = result.get('pubDate') or result.get('publish_date', datetime.now().isoformat())
        ET.SubElement(item, 'pubDate').text = str(pub_date)

        size = result.get('size', 0)
        ET.SubElement(item, 'size').text = str(size)

        # Enclosure for torrent
        magnet = result.get('magnet', '')
        if magnet:
            enclosure = ET.SubElement(item, 'enclosure')
            enclosure.set('url', str(magnet))
            enclosure.set('type', 'application/x-bittorrent')
            enclosure.set('length', str(size))

        # Torznab attributes
        category = result.get('category', '5000')
        ET.SubElement(item, 'torznab:attr', name='category', value=str(category))

        seeders = result.get('seeders', 1)
        ET.SubElement(item, 'torznab:attr', name='seeders', value=str(seeders))

        peers = result.get('peers', 0)
        ET.SubElement(item, 'torznab:attr', name='peers', value=str(peers))

        # Season/Episode info
        if 'season' in result and result['season'] is not None:
            ET.SubElement(item, 'torznab:attr', name='season', value=str(result['season']))

        if 'episode' in result and result['episode'] is not None:
            ET.SubElement(item, 'torznab:attr', name='episode', value=str(result['episode']))

    xml_str = ET.tostring(rss, encoding='unicode')
    return Response(xml_str, mimetype='application/xml')


def sanitize_search_query(query) -> str:
    """
    Sanitize and normalize search query.

    Args:
        query: Raw search query

    Returns:
        Sanitized query string
    """
    if not isinstance(query, str):
        return ""

    # Remove potentially dangerous characters
    query = re.sub(r'[^\w\s\-\.\'"]', '', query)

    # Normalize whitespace
    query = re.sub(r'\s+', ' ', query)

    # Remove leading/trailing whitespace
    query = query.strip()

    # Limit length to prevent abuse
    if len(query) > 200:
        query = query[:200]

    return query


def format_episode_title(show_name: str, season: int, episode: int,
                        episode_title: Optional[str] = None,
                        quality: Optional[str] = None) -> str:
    """
    Format episode title consistently.

    Args:
        show_name: Name of the TV show
        season: Season number
        episode: Episode number
        episode_title: Optional episode title
        quality: Optional quality info

    Returns:
        Formatted episode title
    """
    if not isinstance(show_name, str) or not show_name.strip():
        raise ValueError("Show name is required and must be a non-empty string")

    if not isinstance(season, int) or season < 0:
        raise ValueError("Season must be a non-negative integer")

    if not isinstance(episode, int) or episode < 0:
        raise ValueError("Episode must be a non-negative integer")

    # Format season and episode with leading zeros
    season_str = f"{season:02d}"
    episode_str = f"{episode:02d}"

    formatted = f"{show_name} - S{season_str}E{episode_str}"

    if episode_title:
        formatted += f" - {episode_title}"

    if quality:
        formatted += f" [{quality}]"

    return formatted