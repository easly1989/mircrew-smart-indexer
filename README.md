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

Set the following environment variables:

- `MIRCREW_USERNAME`: Your MIRCrew username
- `MIRCREW_PASSWORD`: Your MIRCrew password
- `SONARR_URL`: Sonarr URL (optional)
- `SONARR_API_KEY`: Sonarr API key (optional)
- `PORT`: Port to run on (default: 9898)

## Installation

### Local Development

```bash
pip install -r requirements.txt
python app.py
```

### Docker

```bash
docker build -t mircrew-indexer .
docker run -p 9898:9898 -v /path/to/config:/config mircrew-indexer



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
Required environment variables (set in your shell or .env file):

| Variable | Purpose | Example |
|----------|---------|---------|
| `MIRCREW_USERNAME` | MIRCrew forum username | `your_username` |
| `MIRCREW_PASSWORD` | MIRCrew forum password | `your_password` |
| `SONARR_API_KEY` | Sonarr API key | `a1b2c3d4e5f6g7h8i9j0` |
| `SONARR_URL` | Sonarr API URL | `http://sonarr:8989` |
| `RUNNING_IN_DOCKER` | Indicates the application is running in a Docker container (set to `true`). Used to adjust configuration paths. | `true` |

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

## 11. Troubleshooting
Check container logs:
```bash
docker logs mircrew-smart
```

Verify health status:
```bash
docker inspect --format='{{json .State.Health}}' mircrew-smart
```

## 12. Security Notes
- Runs as non-root user (UID 1001)
- Uses separate volumes for config and logs
- Requires valid MIRCrew credentials
- API key should be treated as sensitive data