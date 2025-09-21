#!/usr/bin/env python3
"""
MIRCrew Smart Indexer - Custom Indexer che espande automaticamente serie TV
Compatibile con Prowlarr/Sonarr tramite Torznab API
Funzionalità:
1. Ricerca normale per movies/music/books
2. Per serie TV: espande thread completo e ritorna tutti gli episodi
3. Filtra solo episodi che Sonarr realmente vuole
4. Zero script esterni necessari
"""
import os
import re
import random
import time
import logging
import pickle
import requests
from flask import Flask, request, Response
from bs4 import BeautifulSoup, Tag
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, quote_plus, urlencode
from typing import List, Dict, Optional
from datetime import datetime

# Registrazione namespace Torznab
ET.register_namespace("torznab", "http://torznab.com/schemas/2015/feed")
ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Configurazione globale
COOKIE_FILE = "mircrew_cookies.pkl"
MIRCREW_BASE_URL = os.getenv('MIRCREW_BASE_URL', 'https://mircrew-releases.org')
MIRCREW_USERNAME = os.getenv('MIRCREW_USERNAME')
MIRCREW_PASSWORD = os.getenv('MIRCREW_PASSWORD')

class MIRCrewSmartIndexer:
    def __init__(self):
        self.mircrew_url = MIRCREW_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.load_cookies()
        self.thread_cache = {}
        self.sonarr_url = os.getenv('SONARR_URL', 'http://sonarr:8989')
        self.sonarr_api = os.getenv('SONARR_API_KEY')
        self.sonarr_session = requests.Session()
        if self.sonarr_api:
            self.sonarr_session.headers.update({'X-Api-Key': self.sonarr_api})

    def load_cookies(self):
        try:
            if os.path.exists(COOKIE_FILE):
                with open(COOKIE_FILE, 'rb') as f:
                    cookies = pickle.load(f)
                    self.session.cookies.update(cookies)
                logger.debug("Cookies loaded from file")
        except Exception as e:
            logger.warning(f"Error loading cookies: {e}")

    def save_cookies(self):
        try:
            with open(COOKIE_FILE, 'wb') as f:
                pickle.dump(self.session.cookies, f)
            logger.debug("Cookies saved to file")
        except Exception as e:
            logger.warning(f"Error saving cookies: {e}")

    def login(self, retries=15, initial_wait=5):
        if self.is_already_logged_in():
            logger.info("Already authenticated on MIRCrew")
            for cookie in self.session.cookies:
                if "sid" in cookie.name:
                    return cookie.value
            return True

        def is_logged_in(soup):
            error_indicators = [
                soup.find(string=re.compile(r'(?i)login.*failed|invalid.*credentials|wrong.*password|access.*denied')),
                soup.find('div', {'class': re.compile(r'error|alert')}, string=re.compile(r'(?i)login|password')),
                soup.find('form', {'id': 'login'})
            ]
            if any(error_indicators):
                logger.debug("Login failure indicators found on page")
                return False
            success_indicators = [
                soup.find('a', {'href': re.compile(r'mode=logout')}),
                soup.find('a', {'href': re.compile(r'logout')}),
                soup.find('a', string=re.compile(r'(?i)logout|esci|log out')),
                soup.find(['span', 'div', 'a'], string=re.compile(f'(?i){re.escape(MIRCREW_USERNAME)}')),
                soup.find('strong', string=re.compile(f'(?i){re.escape(MIRCREW_USERNAME)}')),
                soup.find(string=re.compile(r'(?i)welcome.*back|benvenuto|logged.*in')),
                soup.find('div', {'class': re.compile(r'user.*panel|welcome')}),
                soup.find('li', {'class': 'user-info'})
            ]
            logged_in = any(success_indicators)
            logger.debug(f"Login verification: {len([x for x in success_indicators if x])} success indicators found")
            return logged_in

        for attempt in range(retries):
            try:
                if attempt > 0:
                    wait_time = min(initial_wait * (2 ** (attempt - 1)), 300)
                    jitter = random.uniform(0.5, 1.5)
                    actual_wait = wait_time * jitter
                    logger.info(f"Retrying login in {actual_wait:.1f} seconds... (attempt {attempt+1}/{retries})")
                    time.sleep(actual_wait)
                login_url = urljoin(MIRCREW_BASE_URL, "ucp.php?mode=login")
                logger.info(f"Login attempt {attempt+1}/{retries}")
                try:
                    resp = self.session.get(login_url, timeout=30)
                    resp.raise_for_status()
                except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                    logger.warning(f"Error requesting login form: {e}")
                    if attempt == retries - 1:
                        logger.error("Unable to get login form after all attempts")
                        return False
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                form = soup.find('form', {'id': 'login'})
                if not form or not isinstance(form, Tag):
                    logger.error("Login form not found on page")
                    if attempt == retries - 1:
                        return False
                    continue
                form_action = str(form.attrs.get('action', login_url))
                if not form_action.startswith('http'):
                    form_action = urljoin(MIRCREW_BASE_URL, form_action)
                login_data = {}
                for input_tag in form.find_all('input'):
                    if not isinstance(input_tag, Tag):
                        continue
                    name = input_tag.attrs.get('name')
                    if name:
                        input_type = str(input_tag.attrs.get('type', 'text')).lower()
                        if input_type == 'checkbox':
                            if input_tag.attrs.get('checked'):
                                login_data[name] = input_tag.attrs.get('value', 'on')
                        else:
                            login_data[name] = input_tag.attrs.get('value', '')
                login_data.update({
                    'username': MIRCREW_USERNAME,
                    'password': MIRCREW_PASSWORD,
                    'login': 'Login',
                    'redirect': './index.php'
                })
                logger.debug(f"Submitting login to: {form_action}")
                try:
                    resp = self.session.post(form_action, data=login_data, allow_redirects=True, timeout=30)
                    logger.info(f"Login POST status: {resp.status_code}, URL finale: {resp.url}")
                except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                    logger.warning(f"Error sending login data: {e}")
                    if attempt == retries - 1:
                        logger.error("Unable to send login data after all attempts")
                        return False
                    continue
                if resp.status_code not in (200, 302):
                    logger.warning(f"Login POST failed with status {resp.status_code}")
                    if attempt == retries - 1:
                        return False
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                if is_logged_in(soup):
                    sid = None
                    for cookie in self.session.cookies:
                        if "sid" in cookie.name:
                            sid = cookie.value
                            break
                    self.save_cookies()
                    if sid:
                        logger.info(f"Login successful with SID: {sid[:8]}...")
                    else:
                        logger.info("Login successful (no SID found)")
                    return sid or True
                else:
                    logger.warning(f"Login attempt {attempt+1} failed - checking page...")
                    error_text = soup.find(string=re.compile(r'(?i)error|failed|wrong|invalid'))
                    if error_text:
                        error_str = str(error_text).strip()
                        logger.warning(f"Possible error found on page: {error_str[:100]}...")
                    if attempt == retries - 1:
                        logger.error("Login failed after all attempts")
                        return False
            except Exception as e:
                logger.error(f"Unexpected error in login attempt {attempt+1}: {e}")
                if attempt == retries - 1:
                    logger.error("Login failed due to repeated errors")
                    return False
        return False

    def is_already_logged_in(self):
        try:
            index_url = urljoin(MIRCREW_BASE_URL, "index.php")
            resp = self.session.get(index_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            if soup.find('form', {'id': 'login'}):
                logger.debug("Login form found - not logged in")
                return False
            logout_links = soup.find_all('a', {'href': re.compile(r'(mode=logout|logout)')})
            username_elements = soup.find_all(['span', 'div', 'a'], string=re.compile(f'(?i){re.escape(MIRCREW_USERNAME)}'))
            if logout_links or username_elements:
                logger.debug("Logout link or username found - already logged in")
                return True
            logger.debug("Unable to determine login status from index page")
            return False
        except Exception as e:
            logger.warning(f"Error checking login status: {e}")
            return False

    def verify_session(self):
        try:
            if self.is_already_logged_in():
                return True
            test_url = urljoin(MIRCREW_BASE_URL, "ucp.php?mode=login")
            resp = self.session.get(test_url, allow_redirects=False, timeout=30)
            if resp.status_code == 302 and "login" in resp.headers.get('Location', ''):
                logger.warning("Session expired - redirecting to login")
                return False
            soup = BeautifulSoup(resp.text, 'html.parser')
            if soup.find('form', {'id': 'login'}):
                logger.warning("Session expired - login form present")
                return False
            return True
        except Exception as e:
            logger.warning(f"Error verifying session: {e}")
            return False

    def is_tv_search(self, query_params: Dict) -> bool:
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
        try:
            thread_url = f"{self.mircrew_url}/viewtopic.php?t={thread_id}"
            response = self.session.get(thread_url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Individua il primo post con h3.first
            first_post_div = soup.select_one('div.post.has-profile')
            if not first_post_div:
                logger.info("Primo post non trovato, non clicco like")
                return

            h3_first = first_post_div.find('h3', class_='first')
            post_buttons = None
            # Cerca il <ul class="post-buttons"> fratello di h3.first
            if h3_first:
                post_buttons = h3_first.find_next_sibling('ul', class_='post-buttons')

            if not post_buttons:
                logger.info("Post buttons non presenti nel primo post, non clicco like")
                return

            # Cerca il pulsante like nell'elenco post-buttons
            like_anchor = post_buttons.find('a', id=re.compile(r'^lnk_thanks_post\d+'))
            if like_anchor:
                like_href = like_anchor.get('href')
                if like_href and like_href.startswith('./'):
                    like_href = like_href[2:]
                full_like_url = f"{self.mircrew_url}/{like_href}"
                logger.info(f"Clicco il like: {full_like_url}")
                self.session.get(full_like_url, timeout=15)
                delay = random.uniform(5, 15)
                logger.info(f"Dormo {delay:.1f} secondi per non triggerare sistemi anti-bot")
                time.sleep(delay)
            else:
                logger.info("Like non presente nel primo post (post-buttons), non clicco nulla")

        except Exception as e:
            logger.warning(f"Impossibile effettuare il like su thread {thread_id}: {e}")

    def _extract_episode_info(self, text: str) -> Optional[Dict]:
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
        return None

    def _parse_episode_from_context(self, soup: BeautifulSoup, magnet: str) -> Optional[Dict]:
        for text_elem in soup.find_all(string=re.compile(re.escape(magnet))):
            for level in range(3):
                current = text_elem
                for _ in range(level):
                    current = getattr(current, 'parent', None)
                    if not current:
                        break
                if current:
                    text = current.get_text() if hasattr(current, 'get_text') else str(current)
                    episode_info = self._extract_episode_info(text)
                    if episode_info:
                        return episode_info
        return None

    def _matches_series(self, title1: str, title2: str) -> bool:
        norm1 = re.sub(r'[^\w\s]', '', title1.lower())
        norm2 = re.sub(r'[^\w\s]', '', title2.lower())
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'da', 'di', 'il', 'la', 'le', 'lo', 'gli', 'una', 'un', 'serie', 'season', 'stagione', 'complete', 'completa'}
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        common = words1.intersection(words2)
        logger.debug(f"Series matching: '{title1}' vs '{title2}' - common words: {common}")
        return len(common) >= 1 and len(common) / max(len(words1), len(words2)) >= 0.3

    def _contains_season(self, title: str, season: int) -> bool:
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

    def _estimate_size_from_title(self, title: str) -> int:
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

    def _categorize_title(self, title: str) -> str:
        if any(word in title.lower() for word in ['s0', 'season', 'episode', 'stagione']):
            return '5000'
        elif any(word in title.lower() for word in ['movie', 'film']):
            return '2000'
        elif any(word in title.lower() for word in ['anime']):
            return '5070'
        else:
            return '8000'

    def _find_series_threads(self, query: str, season: int = None, tv_search: bool = False) -> List[Dict]:
        if not self.login():
            logger.error("Cannot login to MIRCrew")
            return []
        try:
            clean_query = re.sub(r'[^\w\s]', '', query).strip()
            logger.info(f"Searching MIRCrew for: '{clean_query}' (season {season})")
            search_url = f"{self.mircrew_url}/search.php"
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

            response = self.session.get(search_url, params=expanded_params, timeout=20)
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
                        if season is None or self._contains_season(thread_title, season):
                            found_threads.append({'thread_id': thread_id, 'title': thread_title})
            else:
                logger.warning("No topiclist container found in search results")

            logger.info(f"Total matching threads found: {len(found_threads)}")
            return found_threads

        except Exception as e:
            logger.error(f"Thread search error: {e}")
            return []

    def search_mircrew_smart_tv(self, query: str, season: int = None) -> List[Dict]:
        logger.info(f"Smart TV search: {query} S{season}")
        threads = self._find_series_threads(query, season, tv_search=True)
        if not threads:
            logger.warning(f"No threads found for {query}")
            return []

        all_episodes = []
        for thr in threads[:5]:  # Limite a 5 thread per richiesta
            thread_id = thr['thread_id']
            logger.info(f"Expanding thread {thread_id} - '{thr['title']}'")
            try:
                episodes = self._expand_thread_episodes(thread_id)
                if not episodes:
                    continue
                #if season:
                #    episodes = [ep for ep in episodes if ep.get('season') == season]
                all_episodes.extend(episodes)
            except Exception as e:
                logger.error(f"Error expanding thread {thread_id}: {e}")

        logger.info(f"Total episodes returned: {len(all_episodes)}")
        return all_episodes

    def _expand_thread_episodes(self, thread_id: str) -> List[Dict]:
        try:
            self.click_like_if_present(thread_id)
            thread_url = f"{self.mircrew_url}/viewtopic.php?t={thread_id}"
            response = self.session.get(thread_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            episodes = []
            # Cerca i magnet link con classe magnetBtn nel primo post o in tutto il thread
            magnet_links = soup.select('a.magnetBtn[href^="magnet:"]')
            logger.info(f"Trovati {len(magnet_links)} magnet link nel thread {thread_id}")

            for a in magnet_links:
                magnet_link = a['href']
                # Ricava info episodio dal testo vicino, per esempio dal parent o dal precedente sibling
                # Qui dipende da come è strutturato il markup, puoi adattare le regex o scraping
                title_context = a.find_parent(['dd', 'div', 'li', 'td'])
                context_text = title_context.get_text(separator=" ") if title_context else ""

                episode_info = self._extract_episode_info(context_text)
                if not episode_info:
                    # fallback: set default season 0 episode 0 o prova titolo thread
                    episode_info = {'season': 0, 'episode': 0}

                thread_title = soup.select_one('h2.topic-title')
                series_title = thread_title.get_text().strip() if thread_title else f"Thread {thread_id}"

                episodes.append({
                    'title': f"{series_title} S{episode_info.get('season', 0):02d}E{episode_info.get('episode', 0):02d}",
                    'season': episode_info.get('season', 0),
                    'episode': episode_info.get('episode', 0),
                    'thread_id': thread_id,
                    'thread_url': thread_url,
                    'magnet': magnet_link,
                    'size': self._estimate_size_from_title(series_title),
                    'seeders': 1,
                    'peers': 0,
                    'category': '5000',
                    'publish_date': datetime.now().isoformat()
                })

            return episodes
        except Exception as e:
            logger.error(f"Thread expansion error: {e}")
            return []

    def _get_missing_episodes_from_sonarr(self, series_title: str, season: int) -> List[Dict]:
        if not self.sonarr_api:
            logger.warning("Sonarr API key not set; cannot contact Sonarr.")
            return []
        try:
            response = self.sonarr_session.get(f"{self.sonarr_url}/api/v3/series", timeout=10)
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
            response = self.sonarr_session.get(f"{self.sonarr_url}/api/v3/episode?seriesId={series_id}", timeout=10)
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

def torznab_error(message: str) -> Response:
    error_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<error code="100" description="{message}"/>'''
    return Response(error_xml, mimetype='application/xml')

def build_torznab_xml(results: List[Dict]) -> Response:
    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    rss.set('xmlns:torznab', 'http://torznab.com/schemas/2015/feed')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'MIRCrew Smart'
    ET.SubElement(channel, 'description').text = 'MIRCrew Smart Indexer for TV Series'

    for result in results:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = result.get('title', 'Unknown')
        guid = f"mircrew-{result.get('thread_id', '0')}-{result.get('season', 0)}-{result.get('episode', 0)}"
        ET.SubElement(item, 'guid').text = guid
        ET.SubElement(item, 'link').text = result.get('thread_url', '')
        ET.SubElement(item, 'pubDate').text = result.get('publish_date', datetime.now().isoformat())
        ET.SubElement(item, 'size').text = str(result.get('size', 0))
        enclosure = ET.SubElement(item, 'enclosure')
        enclosure.set('url', result.get('magnet', ''))
        enclosure.set('type', 'application/x-bittorrent')
        enclosure.set('length', str(result.get('size', 0)))
        ET.SubElement(item, '{http://torznab.com/schemas/2015/feed}attr',
                      name='category',
                      value=str(result.get('category', '5000')))
        ET.SubElement(item, '{http://torznab.com/schemas/2015/feed}attr',
                      name='seeders',
                      value=str(result.get('seeders', 1)))
        ET.SubElement(item, '{http://torznab.com/schemas/2015/feed}attr',
                      name='peers',
                      value=str(result.get('peers', 0)))
        if 'season' in result and result['season']:
            ET.SubElement(item, '{http://torznab.com/schemas/2015/feed}attr',
                          name='season',
                          value=str(result['season']))
        if 'episode' in result and result['episode']:
            ET.SubElement(item, '{http://torznab.com/schemas/2015/feed}attr',
                          name='episode',
                          value=str(result['episode']))

    xml_str = ET.tostring(rss, encoding='unicode')
    return Response(xml_str, mimetype='application/xml')

def torznab_search():
    query = request.args.get('q', '')
    season = request.args.get('season', '')
    season_int = int(season) if season.isdigit() else None
    results = indexer.search_mircrew_smart_tv(query, season_int)
    return build_torznab_xml(results)

def torznab_caps():
    caps_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<caps>
    <server version="1.0" title="MIRCrew Smart" />
    <limits max="100" default="25"/>
    <searching>
        <search available="yes" supportedParams="q,cat"/>
        <tv-search available="yes" supportedParams="q,season,ep,cat"/>
    </searching>
    <categories>
        <category id="2000" name="Movies"/>
        <category id="5000" name="TV">
            <subcat id="5070" name="Anime"/>
        </category>
        <category id="7000" name="Books"/>
        <category id="3000" name="Music"/>
    </categories>
</caps>'''
    return Response(caps_xml, mimetype='application/xml')

@app.route('/api')
def torznab_api():
    try:
        t = request.args.get('t', '')
        if t == 'caps':
            return torznab_caps()
        elif t in ['search', 'tvsearch']:
            return torznab_search()
        else:
            return torznab_error("Unknown function")
    except Exception as e:
        logger.error(f"API error: {e}")
        return torznab_error(str(e))

@app.route('/health')
def health():
    return {"status": "ok", "indexer": "MIRCrew Smart"}

indexer = MIRCrewSmartIndexer()

if __name__ == '__main__':
    logger.info("Starting MIRCrew Smart Indexer")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '9898')), debug=False)