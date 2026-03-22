FROM n8nio/n8n:latest

USER root

# System dependencies: Python 3, ffmpeg, ImageMagick (required by MoviePy TextClip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    imagemagick \
    libmagickwand-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY python/requirements.txt /app/python/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/python/requirements.txt

# Copy pipeline source
COPY python/ /app/python/
COPY data/ /app/data/

# Ensure output and logs directories exist with correct permissions
RUN mkdir -p /app/output /app/logs /tmp/science_narrator \
    && chown -R node:node /app /tmp/science_narrator

USER node

WORKDIR /app
