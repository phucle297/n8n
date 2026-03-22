# Build on a known Debian base (node:20-bookworm) so apt-get is available.
# We install n8n globally via npm, giving us full control over system packages.
FROM node:20-bookworm-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python runtime
    python3 \
    python3-pip \
    python3-dev \
    # Video / audio
    ffmpeg \
    # ImageMagick — required by MoviePy TextClip
    imagemagick \
    # Build tools for pip packages that compile C extensions (Pillow, etc.)
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install n8n (pin major version for reproducibility)
RUN npm install -g n8n@latest

# Create non-root user that n8n expects
RUN useradd -m -u 1000 node 2>/dev/null || true

# Install Python pipeline dependencies
COPY python/requirements.txt /app/python/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages \
    -r /app/python/requirements.txt

# Copy pipeline source
COPY python/ /app/python/
COPY data/  /app/data/

# Runtime directories
RUN mkdir -p /app/output /app/logs /tmp/science_narrator /home/node/.n8n \
    && chown -R node:node /app /tmp/science_narrator /home/node

USER node
WORKDIR /app

EXPOSE 5678

CMD ["n8n", "start"]
