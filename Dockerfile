# ============================================================
# Flask Robot AI Agent - Dockerfile
# Base: Debian Bookworm (matches Raspberry Pi OS)
# Supports: arm64 only (Raspberry Pi 5)
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
    swig \
    unzip \
    # Python
    python3 \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    python3-venv \
    # Python libraries
    libffi-dev \
    # I2C/GPIO
    libgpiod2 \
    python3-smbus \
    i2c-tools \
    python3-lgpio \
    python3-rgpio \
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

# ============ CREATE VIRTUAL ENVIRONMENT ============
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ============ COPY LGPIO/RGPIO MODULES INTO VENV ============
RUN cp /usr/lib/python3/dist-packages/lgpio.py /opt/venv/lib/python3.*/site-packages/ 2>/dev/null || true && \
    cp /usr/lib/python3/dist-packages/rgpio.py /opt/venv/lib/python3.*/site-packages/ 2>/dev/null || true && \
    cp /usr/lib/python3/dist-packages/_lgpio*.so /opt/venv/lib/python3.*/site-packages/ 2>/dev/null || true && \
    cp /usr/lib/python3/dist-packages/_rgpio*.so /opt/venv/lib/python3.*/site-packages/ 2>/dev/null || true

# ============ INSTALL PYTHON DEPENDENCIES ============
COPY requirements.txt .

# Upgrade pip and install dependencies INCLUDING the Pi 5 beta wheel for rpi_ws281x
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir https://github.com/rpi-ws281x/rpi-ws281x-python/releases/download/pi5-beta2/rpi_ws281x-6.0.0-cp311-cp311-linux_aarch64.whl

# ============ COPY APPLICATION ============
COPY . .

# ============ EXPOSE PORT ============
EXPOSE 5002

# ============ HEALTHCHECK ============
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

# ============ RUN ============
CMD ["python3", "app.py"]
