"""
API authentication manager for read/write operations.
"""
import secrets
import redis
import hashlib
from typing import Optional, Tuple
from flask import request, session as flask_session, jsonify
from datetime import datetime, timedelta

from .auth import AuthManager
from config.settings import settings


class APIAuthManager:
    """Manages API authentication for read/write operations."""

    def __init__(self):
        self.auth = AuthManager()
        self.redis = redis.from_url(settings.redis_url)

    def get_session_user(self) -> Optional[str]:
        """Get user ID from current session."""
        # Check if MirCrew session is valid
        if not self.auth.is_already_logged_in():
            return None

        # Get user identifier from MirCrew session
        # This would need to be implemented based on MirCrew's user identification
        # For now, we'll use a hash of the session cookie
        session_cookie = self.auth.session.cookies.get('phpbb3_session')
        if not session_cookie:
            return None

        return hashlib.sha256(session_cookie.encode()).hexdigest()[:16]

    def validate_read_access(self) -> Tuple[bool, Optional[str]]:
        """Validate read-only access (session check only)."""
        user_id = self.get_session_user()
        if not user_id:
            return False, "Invalid or expired session"
        return True, user_id

    def validate_write_access(self) -> Tuple[bool, Optional[str]]:
        """Validate write access (session + CSRF token)."""
        user_id = self.get_session_user()
        if not user_id:
            return False, "Invalid or expired session"

        csrf_token = request.headers.get('X-CSRF-Token')
        if not csrf_token:
            return False, "Missing CSRF token"

        # Verify CSRF token
        stored_user = self.redis.get(f"csrf:{csrf_token}")
        if not stored_user or stored_user.decode() != user_id:
            return False, "Invalid CSRF token"

        return True, user_id

    def get_csrf_token(self, user_id: str) -> str:
        """Generate and store CSRF token for user."""
        token = secrets.token_urlsafe(32)
        self.redis.setex(f"csrf:{token}", settings.csrf_token_ttl, user_id)
        return token

    def require_read_auth(self, f):
        """Decorator for read-only endpoints."""
        def wrapper(*args, **kwargs):
            valid, user_or_error = self.validate_read_access()
            if not valid:
                return jsonify({"error": user_or_error}), 401
            flask_session['user_id'] = user_or_error
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper

    def require_write_auth(self, f):
        """Decorator for write endpoints."""
        def wrapper(*args, **kwargs):
            valid, user_or_error = self.validate_write_access()
            if not valid:
                return jsonify({"error": user_or_error}), 403
            flask_session['user_id'] = user_or_error
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper

    def check_rate_limit(self, user_id: str, action: str) -> bool:
        """Check if user has exceeded rate limit for action."""
        key = f"ratelimit:{user_id}:{action}"
        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, settings.rate_limit_window)
        return current <= settings.rate_limit_max_requests