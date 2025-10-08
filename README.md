# MIRCrew Smart Indexer

A smart indexer for MIRCrew releases integrated with Sonarr/Prowlarr.

## Features

- Automatic authentication with MIRCrew
- Proactive session renewal
- Torznab API compatibility
- Sonarr integration

## Docker Usage

When running in Docker, cookies are persisted to `/config/mircrew_cookies.pkl` which should be mounted as a volume to preserve authentication across container restarts.

Mount the `/config` directory to persist cookies:

```yaml
volumes:
  - /path/to/config:/config
```

## Configuration

### Indexer Configuration

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MIRCREW_USERNAME` | Yes | - | Your MIRCrew forum username |
| `MIRCREW_PASSWORD` | Yes | - | Your MIRCrew forum password |
| `MIRCREW_BASE_URL` | No | `https://mircrew-releases.org` | MIRCrew forum base URL |
| `SONARR_URL` | No | `http://sonarr:8989` | Sonarr API endpoint URL |
| `SONARR_API_KEY` | No | - | Sonarr API key for episode filtering |
| `DATABASE_URL` | No | `sqlite:///config/mircrew_indexer.db` | Database connection string |
| `PORT` | No | `9898` | Port for the web server |
| `RUNNING_IN_DOCKER` | No | `true` | Set to `true` when running in Docker |

#### Cache Configuration

The application uses in-memory caching with configurable TTL values for improved performance:


| Variable | Default | Description |
|----------|---------|-------------|
| `THREAD_METADATA_TTL` | `86400` (24h) | Thread metadata cache TTL in seconds |
| `LIKE_COUNTS_TTL` | `3600` (1h) | Like count cache TTL in seconds |
| `USER_LIKE_STATUS_TTL` | `900` (15m) | User like status cache TTL in seconds |
| `SEARCH_RESULTS_TTL` | `1800` (30m) | Search results cache TTL in seconds |
| `SESSION_TTL` | `21600` (6h) | User session TTL in seconds |
| `CSRF_TOKEN_TTL` | `3600` (1h) | CSRF token TTL in seconds |

#### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |
| `RATE_LIMIT_MAX_REQUESTS` | `10` | Maximum requests per window |

### Browser Extension Configuration

The browser extension can be configured through the options page:

1. **API Token**: Obtain from `/api/csrf-token` endpoint after authentication
2. **Sonarr URL**: Usually `http://localhost:8989`
3. **Indexer URL**: Usually `http://localhost:9898`
4. **Notification Threshold**: Minimum number of new releases to trigger notification
5. **Theme**: Light, dark, or system theme

#### Extension Permissions

The extension requires these permissions:
- `storage`: For saving settings and cache
- `activeTab`: For interacting with Sonarr interface
- `scripting`: For injecting like buttons
- `notifications`: For release notifications

### Docker Configuration

When running in Docker, configuration is handled through environment variables and volume mounts:

```yaml
services:
  mircrew-smart:
    environment:
      - MIRCREW_USERNAME=${MIRCREW_USERNAME}
      - MIRCREW_PASSWORD=${MIRCREW_PASSWORD}
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=${SONARR_API_KEY}
    volumes:
      - /path/to/config:/config  # Cookie persistence
      - /path/to/logs:/logs      # Log files
    networks:
      - saltbox  # External network for container communication
```

### Database Setup

The indexer uses PostgreSQL with the following schema:
- `user_thread_likes`: User like/unlike actions
- `thread_metadata_cache`: Cached thread information
- `like_history`: Audit log of like actions

Run migrations on startup:
```bash
python -c "from migrations import upgrade; upgrade()"
```

## Installation

### Prerequisites

- Python 3.11+
- SQLite database (stored in /config volume when using Docker)
- Docker and Docker Compose (for containerized deployment)

### Core Dependencies

The application requires the following Python packages:
- Flask 2.3.3
- requests 2.31.0
- beautifulsoup4 4.12.2
- lxml 4.9.3
- SQLAlchemy (for database operations)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mircrew-smart-indexer
   ```

2. **Install dependencies**
   ```bash
   pip install flask requests beautifulsoup4 lxml sqlalchemy redis psycopg2-binary
   ```

3. **Set up PostgreSQL database**
   ```bash
   createdb mircrew_indexer
   ```

4. **Configure environment variables**
   ```bash
   export MIRCREW_USERNAME=your_username
   export MIRCREW_PASSWORD=your_password
   export DATABASE_URL=postgresql://user:password@localhost:5432/mircrew_indexer
   export SONARR_URL=http://localhost:8989
   export SONARR_API_KEY=your_sonarr_api_key
   ```

5. **Run database migrations**
   ```bash
   python -c "from migrations import upgrade; upgrade()"
   ```

6. **Start the application**
   ```bash
   python app.py
   ```

The indexer will be available at `http://localhost:9898`

### Docker Setup

1. **Build the Docker image**
   ```bash
   docker build -t mircrew-smart-indexer:latest .
   ```

2. **Run with Docker Compose** (recommended)
   ```bash
   docker-compose up -d
   ```

3. **Or run manually**
   ```bash
   docker run -d \
     --name mircrew-smart \
     -p 9898:9898 \
     -e MIRCREW_USERNAME=your_username \
     -e MIRCREW_PASSWORD=your_password \
     -e SONARR_URL=http://sonarr:8989 \
     -e SONARR_API_KEY=your_api_key \
     -v /opt/mircrew-smart-indexer/config:/config \
     -v /opt/mircrew-smart-indexer/logs:/logs \
     --network saltbox \
     mircrew-smart-indexer:latest
   ```

### Browser Extension Installation

#### Chrome/Chromium

1. **Download or build the extension**
   - Clone this repository
   - Navigate to `browser-extension/` directory

2. **Load as unpacked extension**
   - Open Chrome and go to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top right)
   - Click "Load unpacked"
   - Select the `browser-extension` folder

3. **Configure the extension**
   - Click the extension icon in the toolbar
   - Open extension options
   - Set the API token (obtain from indexer `/api/csrf-token` endpoint)
   - Configure Sonarr URL (usually `http://localhost:8989`)
   - Configure Indexer URL (usually `http://localhost:9898`)

4. **Grant permissions**
   - The extension will request access to Sonarr and the indexer
   - Allow these permissions for full functionality

#### Firefox

1. **Package the extension**
   - Create a ZIP file of the `browser-extension` directory
   - Change the manifest version to 2 if needed for Firefox compatibility

2. **Install as temporary add-on**
   - Go to `about:debugging`
   - Click "This Firefox" → "Load Temporary Add-on"
   - Select `manifest.json` from the browser-extension folder

3. **For permanent installation**
   - Submit to Firefox Add-ons or use `web-ext` for development

### Production Deployment

1. **Use environment variables** for all configuration
2. **Set up proper database** (PostgreSQL recommended)
3. **Configure Redis** for caching and session management
4. **Use HTTPS** in production environments
5. **Set up monitoring** for the health endpoint
6. **Configure log aggregation**

## Docker Setup and Sonarr Integration
# Docker Setup and Sonarr Integration Guide

## 1. Docker Image Building
Build the Docker image using the provided Dockerfile:
```bash
docker build -t mircrew-smart-indexer:latest .
```

## 2. Container Configuration (docker-compose.yml)
The docker-compose.yml file defines the service configuration. Key elements:

```yaml
services:
  mircrew-smart:
    image: mircrew-smart-indexer:latest
    ports:
      - "9898:9898"  # Maps host port 9898 to container port 9898
    environment:
      - MIRCREW_BASE_URL=https://mircrew-releases.org
      - MIRCREW_USERNAME=${MIRCREW_USERNAME}  # Set in your environment
      - MIRCREW_PASSWORD=${MIRCREW_PASSWORD}  # Set in your environment
      - SONARR_URL=http://sonarr:8989  # Sonarr API endpoint
      - SONARR_API_KEY=${SONARR_API_KEY}  # Sonarr API key
      - PORT=9898
    volumes:
      - /opt/mircrew-smart-indexer/config:/config
      - /opt/mircrew-smart-indexer/logs:/logs
```

## 3. Environment Variables
See the Configuration section above for complete environment variable documentation.

## 4. Obtaining Sonarr API Key
1. Open Sonarr web UI
2. Go to Settings → General
3. Copy the API Key from the "Security" section

## 5. Running the Container
Start the service using Docker Compose:
```bash
docker-compose up -d
```

Verify health status:
```bash
docker ps --filter "name=mircrew-smart"
```

## 6. Adding to Sonarr as Torznab Indexer
1. In Sonarr, go to Settings → Indexers
2. Click "+ Add Indexer" → Torznab
3. Configure with these settings:

   | Field | Value |
   |-------|-------|
   | Name | `MIRCrew Smart` |
   | URL | `http://<docker-host>:9898/api` |
   | Categories | `5000` (TV), `5070` (Anime) |

4. Test the connection and save

## 7. Torznab Endpoint Details
The indexer implements these Torznab endpoints:
- `GET /` - Capabilities (returns supported features)
- `GET /?t=search&q={query}` - Search endpoint
- `GET /?t=tvsearch&season={N}` - TV-specific search

Example search URL:
```
http://localhost:9898/?t=tvsearch&q=Breaking+Bad&season=5
```

## 7.5. New JSON API Endpoints

The indexer also provides JSON API endpoints for thread management and user interactions:

### Authentication
All write operations require authentication via MIRCrew session cookies and CSRF tokens.

- `GET /api/csrf-token` - Get CSRF token for write operations (requires read auth)

### Thread Management
- `GET /api/thread/{threadId}/status` - Get thread status and like information
- `POST /api/thread/{threadId}/like` - Like or unlike a thread (action: "like" or "unlike")
- `GET /api/thread/{threadId}/releases` - Get releases from specific thread (Torznab XML)
- `GET /api/liked-threads` - List user's liked threads with pagination
- `POST /api/search/refresh/{threadId}` - Refresh cached thread data (admin only)

### Environment Variables
Additional environment variables for database and caching:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://mircrew:password@localhost:5432/mircrew_indexer` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

## 8. Network Considerations
The compose file uses an external network `saltbox`. This network is required for communication between containers in the same Docker environment. To create it:
```bash
docker network create saltbox
```

Ensure Sonarr is on the same network for direct communication. If using a different network, update the network name in docker-compose.yml.

## 9. Volume Persistence
Configuration and logs are persisted in:
- `/opt/mircrew-smart-indexer/config` - Application configuration
- `/opt/mircrew-smart-indexer/logs` - Log files

## 10. Health Monitoring
The container includes a health check that verifies the `/health` endpoint:
```Dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9898/health', timeout=5)" || exit 1
```

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
**Symptoms**: "Authentication failed" errors, unable to access MIRCrew

**Solutions**:
- Verify `MIRCREW_USERNAME` and `MIRCREW_PASSWORD` are correct
- Check if MIRCrew changed their login mechanism
- Clear cookie cache: `rm /config/mircrew_cookies.pkl`
- Check logs for detailed error messages

#### 2. Database Connection Issues
**Symptoms**: SQL errors, application won't start

**Solutions**:
- Ensure PostgreSQL is running
- Verify `DATABASE_URL` is correct
- Run migrations: `python -c "from migrations import upgrade; upgrade()"`
- Check database permissions

#### 3. Extension Not Working
**Symptoms**: Like buttons don't appear, no notifications

**Solutions**:
- Verify extension is loaded and enabled
- Check extension permissions in browser settings
- Ensure indexer URL is accessible from browser
- Check browser console for JavaScript errors
- Verify API token is set in extension options

#### 4. WebSocket Connection Issues
**Symptoms**: Real-time updates not working

**Solutions**:
- WebSocket server is not implemented yet (known limitation)
- Extension will fall back to polling
- Check network connectivity between browser and indexer

#### 5. Sonarr Integration Issues
**Symptoms**: No episode filtering, search errors

**Solutions**:
- Verify `SONARR_URL` and `SONARR_API_KEY` are correct
- Ensure Sonarr is accessible from indexer
- Check Sonarr API version compatibility
- Verify network connectivity in Docker setup

### Debugging Steps

#### Check Application Health
```bash
# Health endpoint
curl http://localhost:9898/health

# Container logs
docker logs mircrew-smart

# Container health
docker inspect --format='{{json .State.Health}}' mircrew-smart
```

#### Check API Endpoints
```bash
# Test basic connectivity
curl http://localhost:9898/

# Test authentication
curl -H "Cookie: session_cookie_here" http://localhost:9898/api/csrf-token
```

#### Browser Extension Debugging
```javascript
// Check extension status in browser console
chrome.runtime.sendMessage({action: 'getStatus'}, response => {
  console.log('Extension status:', response);
});
```

#### Database Debugging
```sql
-- Check database connectivity
SELECT version();

-- Check table existence
\dt

-- Check recent likes
SELECT * FROM user_thread_likes ORDER BY liked_at DESC LIMIT 10;
```

### Performance Tuning

#### Cache Configuration
- Increase Redis memory if available
- Adjust TTL values based on usage patterns
- Monitor cache hit rates

#### Database Optimization
- Ensure proper indexing on frequently queried columns
- Consider read replicas for high-traffic deployments
- Monitor query performance

#### Rate Limiting
- Adjust `RATE_LIMIT_MAX_REQUESTS` based on usage
- Monitor rate limit hits in logs

### Getting Help

1. **Check Logs**: Enable debug logging with `LOG_LEVEL=DEBUG`
2. **Test Endpoints**: Use tools like Postman to test API endpoints
3. **Browser DevTools**: Check network and console tabs
4. **Community Support**: Check project issues and discussions

## Security Considerations

- **Credential Storage**: Never commit credentials to version control
- **API Keys**: Treat Sonarr API keys as sensitive data
- **Network Security**: Use HTTPS in production
- **Container Security**: Runs as non-root user (UID 1001)
- **Session Management**: Sessions expire after 6 hours by default
- **CSRF Protection**: All write operations require CSRF tokens
- **Rate Limiting**: Prevents abuse with configurable limits