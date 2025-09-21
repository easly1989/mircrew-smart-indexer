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