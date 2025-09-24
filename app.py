"""
MIRCrew Smart Indexer - Modular Flask Application
"""
import os
import logging
from flask import Flask, request

from config.settings import settings
from utils.logging import setup_logging, get_logger
from indexer.core import MIRCrewSmartIndexer
from indexer.torznab import torznab_search, torznab_caps, torznab_error, torznab_test
from background.scheduler import start_background_tasks

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize indexer
indexer = MIRCrewSmartIndexer()

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


if __name__ == '__main__':
    logger.info("Starting MIRCrew Smart Indexer v2.0.0")
    app.run(
        host='0.0.0.0',
        port=settings.port,
        debug=False
    )