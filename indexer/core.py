"""
Core indexer logic for MIRCrew Smart Indexer.
"""
import re
import time
import random
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import quote_plus, urlencode
from bs4 import BeautifulSoup

from .auth import AuthManager
from .parsing import EpisodeParser
from .sonarr import SonarrClient

logger = logging.getLogger(__name__)


class MIRCrewSmartIndexer:
    """
    Main indexer class that orchestrates authentication, parsing, and search functionality.
    """

    def __init__(self):
        self.auth = AuthManager()
        self.parser = EpisodeParser()
        self.sonarr = SonarrClient()
        self.thread_cache = {}

    def is_tv_search(self, query_params: Dict) -> bool:
        """Check if the search is for TV content."""
        tv_indicators = [
            'cat=5000',
            'cat=5070',
            'season=',
            'ep=',
            't=tvsearch'
        ]
        query_string = str(query_params)
        return any(indicator in query_string for indicator in tv_indicators)

    def click_like_if_present(self, thread_id: str):
        """Click like button on thread if present."""
        try:
            thread_url = f"{self.auth.mircrew_url}/viewtopic.php?t={thread_id}"
            response = self.auth.session.get(thread_url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find first post with h3.first
            first_post_div = soup.select_one('div.post.has-profile')
            if not first_post_div:
                logger.info("Primo post non trovato, non clicco like")
                return

            h3_first = first_post_div.find('h3', class_='first')
            post_buttons = None
            # Find post-buttons ul element
            if h3_first:
                post_buttons = h3_first.find_next_sibling('ul', class_='post-buttons')

            if not post_buttons:
                logger.info("Post buttons non presenti nel primo post, non clicco like")
                return

            # Find like button
            like_anchor = post_buttons.find('a', id=re.compile(r'^lnk_thanks_post\d+'))
            if like_anchor:
                like_href = like_anchor.get('href')
                if like_href and like_href.startswith('./'):
                    like_href = like_href[2:]
                full_like_url = f"{self.auth.mircrew_url}/{like_href}"
                logger.info(f"Clicco il like: {full_like_url}")
                self.auth.session.get(full_like_url, timeout=15)
                delay = random.uniform(5, 15)
                logger.info(f"Dormo {delay:.1f} secondi per non triggerare sistemi anti-bot")
                time.sleep(delay)
            else:
                logger.info("Like non presente nel primo post (post-buttons), non clicco nulla")

        except Exception as e:
            logger.warning(f"Impossibile effettuare il like su thread {thread_id}: {e}")

    def _find_series_threads(self, query: str, season: Optional[int] = None, tv_search: bool = False) -> List[Dict]:
        """Find series threads matching the query."""
        if not self.auth.login():
            logger.error("Cannot login to MIRCrew")
            return []

        try:
            clean_query = re.sub(r'[^\w\s]', '', query).strip()
            logger.info(f"Searching MIRCrew for: '{clean_query}' (season {season})")
            search_url = f"{self.auth.mircrew_url}/search.php"
            params = {
                'keywords': quote_plus(f'{query}'),
                'terms': 'all',
                'author': '',
                'fid[]': ['26', '28', '29', '51', '52', '30', '31', '33', '35', '37'],
                'sc': '0',
                'sf': 'titleonly',
                'sr': 'topics',
                'sk': 't',
                'sd': 'd',
                'st': '0',
                'ch': '300',
                't': '0',
                'submit': 'Cerca'
            }

            expanded_params = []
            for k, v in params.items():
                if isinstance(v, list):
                    for item in v:
                        expanded_params.append((k, item))
                else:
                    expanded_params.append((k, v))

            query_string = urlencode(expanded_params)
            logger.info(f"Searching URL: {search_url}?{query_string}")

            response = self.auth.session.get(search_url, params=expanded_params, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            found_threads = []
            topiclist = soup.select_one('ul.topiclist.topics')
            if topiclist:
                logger.info("Siamo nella topiclist!")
                for title_link in topiclist.select('a.topictitle'):
                    logger.info(f"Abbiamo trovato un topictitle: {title_link.get_text()}")
                    thread_title = title_link.get_text().strip()
                    thread_url = title_link.get('href', '').lstrip('./')
                    thread_match = re.search(r't=(\d+)(?:&|$)', thread_url)
                    if thread_match:
                        thread_id = thread_match.group(1)
                        logger.info(f"Abbiamo trovato un thread: {thread_id}")
                        if season is None or self.parser.contains_season(thread_title, season):
                            found_threads.append({'thread_id': thread_id, 'title': thread_title})
            else:
                logger.warning("No topiclist container found in search results")

            logger.info(f"Total matching threads found: {len(found_threads)}")
            return found_threads

        except Exception as e:
            logger.error(f"Thread search error: {e}")
            return []

    def search_mircrew_smart_tv(self, query: str, season: Optional[int] = None) -> List[Dict]:
        """Perform smart TV search expanding threads into individual episodes."""
        logger.info(f"Smart TV search: {query} S{season}")
        threads = self._find_series_threads(query, season, tv_search=True)
        if not threads:
            logger.warning(f"No threads found for {query}")
            return []

        all_episodes = []
        for thr in threads[:5]:  # Limit to 5 threads per request
            thread_id = thr['thread_id']
            logger.info(f"Expanding thread {thread_id} - '{thr['title']}'")
            try:
                episodes = self._expand_thread_episodes(thread_id)
                if not episodes:
                    continue
                all_episodes.extend(episodes)
            except Exception as e:
                logger.error(f"Error expanding thread {thread_id}: {e}")

        logger.info(f"Total episodes returned: {len(all_episodes)}")

        # Sonarr-based filtering
        if self.sonarr.sonarr_api and season is not None:  # Only if Sonarr is configured and season specified
            try:
                missing_episodes = self.sonarr.get_missing_episodes(query, season)
                if missing_episodes:
                    logger.info(f"Found {len(missing_episodes)} missing episodes from Sonarr")
                    missing_set = {(e['season'], e['episode']) for e in missing_episodes}

                    # Filter episodes to only include missing ones
                    filtered_episodes = [
                        ep for ep in all_episodes
                        if ep['season'] is not None
                        and ep['episode'] is not None
                        and (ep['season'], ep['episode']) in missing_set
                    ]
                    logger.info(f"Filtered from {len(all_episodes)} to {len(filtered_episodes)} episodes")
                    return filtered_episodes
                else:
                    logger.info("No missing episodes found in Sonarr, returning no results")
                    return []
            except Exception as e:
                logger.error(f"Sonarr filtering failed: {str(e)}", exc_info=True)
                return all_episodes  # Fallback to unfiltered results

        return all_episodes  # Return unfiltered if Sonarr not configured

    def _expand_thread_episodes(self, thread_id: str) -> List[Dict]:
        """Expand a thread into individual episode entries."""
        try:
            self.click_like_if_present(thread_id)
            thread_url = f"{self.auth.mircrew_url}/viewtopic.php?t={thread_id}"
            response = self.auth.session.get(thread_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            episodes = []
            # Find magnet links in the thread
            magnet_links = soup.select('a.magnetBtn[href^="magnet:"]')
            logger.info(f"Trovati {len(magnet_links)} magnet link nel thread {thread_id}")

            thread_title = soup.select_one('h2.topic-title')
            series_title = thread_title.get_text().strip() if thread_title else f"Thread {thread_id}"

            for a in magnet_links:
                magnet_link = a['href']
                # Find episode info from context
                title_context = a.find_parent(['dd', 'div', 'li', 'td'])
                context_text = title_context.get_text(separator=" ") if title_context else ""

                episode_info = self.parser.extract_episode_info(context_text)
                if episode_info and 'season' in episode_info and 'episode' in episode_info:
                    season = episode_info['season']
                    episode = episode_info['episode']
                    title = f"{series_title} S{season:02d}E{episode:02d}"
                else:
                    season = None
                    episode = None
                    title = series_title

                episodes.append({
                    'title': title,
                    'season': season,
                    'episode': episode,
                    'thread_id': thread_id,
                    'thread_url': thread_url,
                    'magnet': magnet_link,
                    'size': self.parser.estimate_size_from_title(series_title),
                    'seeders': 1,
                    'peers': 0,
                    'category': self.parser.categorize_title(series_title),
                    'publish_date': datetime.now().isoformat()
                })

            return episodes

        except Exception as e:
            logger.error(f"Thread expansion error: {e}")
            return []