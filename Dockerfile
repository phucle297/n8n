# node:22 satisfies n8n's engine requirement (>=22.16).
# bookworm-slim is Debian Bookworm — apt-get is available.
FROM node:22-bookworm-slim

# System dependencies in one layer to minimise image size.
# build-essential includes make + g++, required by n8n's isolated-vm native module.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # --- build tools (required by n8n native modules) ---
    build-essential \
    # --- Python runtime ---
    python3 \
    python3-pip \
    python3-dev \
    python-is-python3 \
    # --- video / audio ---
    ffmpeg \
    # --- ImageMagick + fonts (required by MoviePy TextClip) ---
    imagemagick \
    gsfonts \
    fonts-dejavu-core \
    # --- C extension deps for Pillow etc. ---
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/* \
    # MoviePy TextClip uses ImageMagick's @file syntax; Debian's default policy blocks it.
    && sed -i 's|<policy domain="path" rights="none" pattern="@\*"/>|<!-- removed: blocked MoviePy TextClip -->|' /etc/ImageMagick-6/policy.xml

# Install n8n. --legacy-peer-deps silences peer-conflict warnings without breaking anything.
RUN npm install -g n8n@latest --legacy-peer-deps

# node:22 already has a 'node' user (uid 1000). Nothing to create.

# Install Python pipeline dependencies (cached layer — only rebuilds on requirements change)
COPY python/requirements.txt /app/python/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages \
    -r /app/python/requirements.txt

# Copy pipeline source
COPY python/ /app/python/
COPY data/   /app/data/

# Runtime directories with correct ownership
RUN mkdir -p /app/output /app/logs /tmp/science_narrator /home/node/.n8n \
    && chown -R node:node /app /tmp/science_narrator /home/node

USER node
WORKDIR /app

EXPOSE 5678
CMD ["n8n", "start"]
