"""
Authentication manager for MIRCrew with proactive session renewal.
"""
import os
import re
import time
import random
import logging
import pickle
import requests
import threading
from typing import Union
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from bs4.element import Tag

from config.settings import settings

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages MIRCrew authentication with proactive session renewal."""

    def __init__(self):
        self.mircrew_url = settings.mircrew_base_url
        self.username = settings.mircrew_username
        self.password = settings.mircrew_password
        self.cookie_file = '/config/mircrew_cookies.pkl' if settings.running_in_docker else 'mircrew_cookies.pkl'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        cookies = self.load_cookies()
        if cookies:
            self.session.cookies.update(cookies)

    def _proactive_auth_loop(self):
        """Background loop for proactive authentication renewal."""
        logger.info("Starting proactive authentication scheduler")
        consecutive_failures = 0
        max_consecutive_failures = 3

        while True:
            try:
                if not self.is_already_logged_in():
                    logger.info("Session expired, attempting login...")
                    if self.login():
                        consecutive_failures = 0
                        logger.info("Proactive login successful")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"Proactive login failed ({consecutive_failures}/{max_consecutive_failures})")

                        if consecutive_failures >= max_consecutive_failures:
                            logger.error("Too many consecutive login failures, backing off for longer period")
                            time.sleep(1800)  # 30 minutes backoff
                            consecutive_failures = 0
                            continue

                # Check every 20-60 minutes
                import random
                check_interval = random.randint(1200, 3600)  # 20-60 minutes
                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in proactive authentication loop: {e}")
                time.sleep(300)  # 5 minutes on error

    def load_cookies(self):
        """Load saved cookies from file."""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'rb') as f:
                    return pickle.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to load cookies: {str(e)}")
            return None

    def save_cookies(self):
        """Save current cookies to file."""
        try:
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(self.session.cookies, f)
        except Exception as e:
            logger.error(f"Failed to save cookies: {str(e)}")

    def login(self, retries: int = 15, initial_wait: int = 5) -> Union[str, bool]:
        """
        Perform login to MIRCrew.

        Args:
            retries: Maximum number of retry attempts
            initial_wait: Initial wait time between retries

        Returns:
            Session ID string on success, False on failure
        """
        if not self.username or not self.password:
            logger.error("MIRCrew credentials not configured")
            return False

        if self.is_already_logged_in():
            logger.info("Already authenticated on MIRCrew")
            for cookie in self.session.cookies:
                if "sid" in cookie.name:
                    return cookie.value
            return True

        def is_logged_in(soup):
            """Check if login was successful by looking for indicators."""
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
                soup.find(['span', 'div', 'a'], string=re.compile(f'(?i){re.escape(self.username)}')),
                soup.find('strong', string=re.compile(f'(?i){re.escape(self.username)}')),
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
                    logger.info(".1f")

                login_url = urljoin(self.mircrew_url, "ucp.php?mode=login")
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
                    form_action = urljoin(self.mircrew_url, form_action)

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
                    'username': self.username,
                    'password': self.password,
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

    def is_already_logged_in(self) -> bool:
        """Check if current session is still authenticated."""
        try:
            index_url = urljoin(self.mircrew_url, "index.php")
            resp = self.session.get(index_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            if soup.find('form', {'id': 'login'}):
                logger.debug("Login form found - not logged in")
                return False

            logout_links = soup.find_all('a', {'href': re.compile(r'(mode=logout|logout)')})
            username_elements = soup.find_all(['span', 'div', 'a'], string=re.compile(f'(?i){re.escape(self.username)}'))

            if logout_links or username_elements:
                logger.debug("Logout link or username found - already logged in")
                return True

            logger.debug("Unable to determine login status from index page")
            return False

        except Exception as e:
            logger.warning(f"Error checking login status: {e}")
            return False

    def verify_session(self) -> bool:
        """Verify current session is valid."""
        try:
            if self.is_already_logged_in():
                return True

            test_url = urljoin(self.mircrew_url, "ucp.php?mode=login")
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