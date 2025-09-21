FROM python:3.11-slim

# Metadata
LABEL maintainer="mircrew-smart-indexer"
LABEL description="MIRCrew Smart Indexer for Sonarr/Prowlarr"
LABEL version="1.0.0"

# Crea user non-root con ID Saltbox
RUN groupadd -g 1001 python && \
    useradd -u 1001 -g 1001 -m -s /bin/bash python

# Install dipendenze Python
RUN pip install --no-cache-dir \
    flask==2.3.3 \
    requests==2.31.0 \
    beautifulsoup4==4.12.2 \
    lxml==4.9.3

# Crea directory
RUN mkdir -p /app /config && \
    chown -R python:python /app /config

# Copia codice applicazione
COPY --chown=python:python mircrew_smart_indexer.py /app/

# Switch a user non-root
USER python:python

# Working directory
WORKDIR /app

# Esponi porta
EXPOSE 9898

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9898/health', timeout=5)" || exit 1

# Comando di avvio
CMD ["python", "mircrew_smart_indexer.py"]