"""
MIRCrew Smart Indexer - Modular Flask Application
"""
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, session
from sqlalchemy.orm import Session

from config.settings import settings
from utils.logging import setup_logging, get_logger
from indexer.core import MIRCrewSmartIndexer
from indexer.api_auth import APIAuthManager
from indexer.torznab import torznab_search, torznab_caps, torznab_error, torznab_test
from services.cache_service import CacheService
from models import SessionLocal, UserThreadLikes, ThreadMetadataCache, LikeHistory
from background.scheduler import start_background_tasks

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize services
indexer = MIRCrewSmartIndexer()
api_auth = APIAuthManager()
cache = CacheService()

# Perform initial authentication (blocking startup)
logger.info("Performing initial authentication...")
if not indexer.auth.login():
    logger.error("Initial authentication failed. Exiting.")
    exit(1)
logger.info("Initial authentication successful.")

# Start background tasks for proactive renewal
start_background_tasks(indexer.auth)


@app.route('/api')
def torznab_api():
    """Main Torznab API endpoint."""
    try:
        t = request.args.get('t', '')
        if t == 'caps':
            return torznab_caps()
        elif t == 'test':
            return torznab_test(indexer)
        elif t in ['search', 'tvsearch']:
            return torznab_search(indexer, request)
        else:
            return torznab_error("Unknown function")
    except Exception as e:
        logger.error(f"API error: {e}")
        return torznab_error(str(e))


@app.route('/health')
def health():
    """Health check endpoint with authentication status."""
    auth_status = "authenticated" if indexer.auth.is_already_logged_in() else "not_authenticated"
    return {
        "status": "ok",
        "indexer": "MIRCrew Smart",
        "version": "2.0.0",
        "authentication": auth_status
    }


@app.route('/api/csrf-token')
def get_csrf_token():
    """Get CSRF token for write operations."""
    valid, user_or_error = api_auth.validate_read_access()
    if not valid:
        return jsonify({"error": user_or_error}), 401

    if user_or_error:
        token = api_auth.get_csrf_token(user_or_error)
        return jsonify({"csrf_token": token})
    return jsonify({"error": "User not found"}), 401


@app.route('/api/thread/<thread_id>/status')
def get_thread_status(thread_id):
    """Get thread status and like information."""
    user_id = request.args.get('userId')
    valid, auth_user_or_error = api_auth.validate_read_access()
    if not valid:
        # Allow anonymous access but without user-specific data
        user_id = None

    # Try cache first
    cached_status = cache.get_thread_status(thread_id, user_id)
    if cached_status:
        return jsonify(cached_status)

    # Get from database
    db: Session = SessionLocal()
    try:
        metadata = db.query(ThreadMetadataCache).filter_by(thread_id=thread_id).first()
        if not metadata:
            return jsonify({"error": "Thread not found"}), 404

        status = {
            "thread_id": thread_id,
            "like_count": metadata.like_count,
            "last_updated": metadata.last_update.isoformat(),
            "cached": False
        }

        if user_id:
            like_record = db.query(UserThreadLikes).filter_by(
                thread_id=thread_id,
                user_id=user_id,
                unliked_at=None
            ).first()
            status["user_liked"] = like_record is not None

        # Cache the result
        cache.set_thread_status(thread_id, status)
        status["cached"] = True

        return jsonify(status)
    finally:
        db.close()


@app.route('/api/thread/<thread_id>/like', methods=['POST'])
@api_auth.require_write_auth
def like_thread(thread_id):
    """Like or unlike a thread."""
    data = request.get_json()
    action = data.get('action', 'like')
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401

    if action not in ['like', 'unlike']:
        return jsonify({"error": "Invalid action"}), 400

    # Check rate limit
    if not api_auth.check_rate_limit(user_id, 'like'):
        return jsonify({"error": "Rate limit exceeded"}), 429

    db: Session = SessionLocal()
    try:
        # Check current like status
        existing_like = db.query(UserThreadLikes).filter_by(
            thread_id=thread_id,
            user_id=user_id,
            unliked_at=None
        ).first()

        if action == 'like' and existing_like:
            return jsonify({"error": "Already liked"}), 400
        elif action == 'unlike' and not existing_like:
            return jsonify({"error": "Not liked"}), 400

        if action == 'like':
            # Add new like
            new_like = UserThreadLikes(thread_id=thread_id, user_id=user_id)
            db.add(new_like)
            cache.set_user_like(thread_id, user_id)
            new_count = cache.increment_like_count(thread_id)
        else:
            # Unlike
            existing_like.unliked_at = datetime.utcnow()
            cache.remove_user_like(thread_id, user_id)
            cache.invalidate_user_likes_cache(user_id)
            new_count = cache.decrement_like_count(thread_id)

        # Record in history
        history = LikeHistory(
            thread_id=thread_id,
            user_id=user_id,
            action=action,
            ip_address=request.remote_addr
        )
        db.add(history)

        # Update metadata cache
        metadata = db.query(ThreadMetadataCache).filter_by(thread_id=thread_id).first()
        if metadata:
            metadata.like_count = new_count
            metadata.last_update = datetime.utcnow()

        db.commit()

        return jsonify({
            "thread_id": thread_id,
            "new_status": action + "d",
            "total_likes": new_count
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Like action failed: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db.close()


@app.route('/api/thread/<thread_id>/releases')
def get_thread_releases(thread_id):
    """Get releases from specific thread."""
    season = request.args.get('season', type=int)
    episode = request.args.get('episode', type=int)

    # Try to get thread data
    thread_data = indexer._get_thread_data(thread_id)
    if not thread_data:
        return jsonify({"error": "Thread not found"}), 404

    episodes = indexer._expand_thread_episodes(thread_data)

    # Filter by season/episode if specified
    if season is not None:
        episodes = [ep for ep in episodes if ep.get('season') == season]
    if episode is not None:
        episodes = [ep for ep in episodes if ep.get('episode') == episode]

    # Return as Torznab XML for compatibility
    from indexer.torznab import build_torznab_xml
    return build_torznab_xml(episodes)


@app.route('/api/liked-threads')
@api_auth.require_read_auth
def get_liked_threads():
    """Get user's liked threads."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 25, type=int), 100)  # Max 100 per page

    offset = (page - 1) * limit

    db: Session = SessionLocal()
    try:
        # Get liked threads with pagination
        likes = db.query(UserThreadLikes).filter_by(
            user_id=user_id,
            unliked_at=None
        ).order_by(UserThreadLikes.liked_at.desc()).offset(offset).limit(limit).all()

        total_count = db.query(UserThreadLikes).filter_by(
            user_id=user_id,
            unliked_at=None
        ).count()

        results = []
        for like in likes:
            metadata = db.query(ThreadMetadataCache).filter_by(thread_id=like.thread_id).first()
            result = {
                "thread_id": like.thread_id,
                "like_date": like.liked_at.isoformat(),
                "release_count": 0  # Would need to calculate from thread data
            }
            if metadata:
                result["title"] = metadata.title
            results.append(result)

        return jsonify({
            "results": results,
            "pagination": {
                "total": total_count,
                "page": page,
                "pages": (total_count + limit - 1) // limit
            }
        })
    finally:
        db.close()


@app.route('/api/search/refresh/<thread_id>', methods=['POST'])
def refresh_thread_cache(thread_id):
    """Refresh cached thread data (admin only)."""
    # TODO: Implement admin authentication
    # For now, allow any authenticated user

    valid, user_or_error = api_auth.validate_write_access()
    if not valid:
        return jsonify({"error": user_or_error}), 403

    try:
        # Clear cache
        cache.invalidate_thread_cache(thread_id)

        # Refresh thread data
        thread_data = indexer._get_thread_data(thread_id)
        new_releases = len(thread_data.get('magnets', [])) if thread_data else 0

        # Update metadata cache
        if thread_data:
            cache.set_cached_metadata(thread_id, {
                "title": thread_data.get('title', ''),
                "last_updated": datetime.utcnow().isoformat(),
                "release_count": new_releases
            })

        return jsonify({
            "thread_id": thread_id,
            "refreshed_at": datetime.utcnow().isoformat(),
            "new_releases": new_releases
        })
    except Exception as e:
        logger.error(f"Cache refresh failed: {e}")
        return jsonify({"error": "Refresh failed"}), 500


if __name__ == '__main__':
    logger.info("Starting MIRCrew Smart Indexer v2.0.0")
    app.run(
        host='0.0.0.0',
        port=settings.port,
        debug=False
    )