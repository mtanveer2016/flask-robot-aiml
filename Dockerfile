# ============================================================
# Flask Robot AI Agent - Dockerfile
# Base: Raspberry Pi OS (Debian bookworm-based)
# Supports: arm64 only
# ============================================================

FROM debian:bookworm-slim

# ============ ARGUMENTS ============
ARG DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH=arm64

# ============ ENVIRONMENT ============
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# ============ ADD RASPBERRY PI REPOSITORY ============
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    && wget -qO - https://archive.raspberrypi.com/debian/raspberrypi.gpg.key | gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian/ bookworm main" > /etc/apt/sources.list.d/raspi.list \
    && apt-get update

# ============ INSTALL SYSTEM DEPENDENCIES ============
RUN apt-get install -y --no-install-recommends \
    # Build tools
    build-essential \
    cmake \
    git \
    wget \
    gcc \
    g++ \
    make \
    pkg-config \
    # Python
    python3 \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    # Python libraries
    libffi-dev \
    # I2C/GPIO
    libgpiod2 \
    python3-smbus \
    i2c-tools \
    # Audio/Video
    ffmpeg \
    libsdl2-dev \
    libsdl2-2.0-0 \
    # Camera (Raspberry Pi)
    libcamera-dev \
    libcap-dev \
    python3-picamera2 \
    python3-libcamera \
    # Math
    libopenblas-dev \
    libopenmpi-dev \
    libatlas-base-dev \
    # Audio
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    # Misc
    curl \
    && rm -rf /var/lib/apt/lists/*

# ============ SETUP WORKING DIRECTORY ============
WORKDIR /app

# ============ INSTALL PYTHON DEPENDENCIES ============
COPY requirements.txt .

RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel --break-system-packages && \
    pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# ============ COPY APPLICATION ============
COPY . .

# ============ EXPOSE PORT ============
EXPOSE 5002

# ============ HEALTHCHECK ============
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

# ============ RUN ============
CMD ["python3", "app.py"]
