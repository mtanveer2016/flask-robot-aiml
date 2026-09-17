# ============================================================
# Flask Robot AI Agent - Dockerfile
# Base: Debian Bookworm (matches Raspberry Pi OS)
# ============================================================

FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# ============ ADD RASPBERRY PI REPOSITORY ============
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget gnupg \
    && wget -qO - https://archive.raspberrypi.com/debian/raspberrypi.gpg.key | gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian/ bookworm main" > /etc/apt/sources.list.d/raspi.list \
    && apt-get update

# ============ INSTALL SYSTEM DEPENDENCIES ============
RUN apt-get install -y --no-install-recommends \
    # Build tools
    build-essential cmake git wget gcc g++ make pkg-config swig unzip \
    # Python
    python3 python3-pip python3-dev python3-setuptools python3-wheel python3-venv \
    libffi-dev \
    # GPIO / I2C / SPI
    libgpiod2 python3-smbus i2c-tools python3-lgpio python3-rgpio python3-spidev \
    # Camera
    libcamera-dev libcap-dev python3-picamera2 python3-libcamera \
    # Audio / Video
    ffmpeg libsdl2-dev libsdl2-2.0-0 portaudio19-dev python3-pyaudio alsa-utils \
    # Math
    libopenblas-dev libopenmpi-dev libatlas-base-dev \
    # Utils
    curl \
    && rm -rf /var/lib/apt/lists/*

# ============ BUILD LGPIO/RGPIO FROM SOURCE ============
RUN cd /tmp && \
    wget https://github.com/joan2937/lg/archive/master.zip && \
    unzip master.zip && \
    cd lg-master && \
    make && \
    make install && \
    ldconfig && \
    cd /tmp && rm -rf lg-master master.zip

# ============ BUILD WHISPER.CPP INSIDE THE IMAGE ============
# Compile against container's glibc to avoid GLIBC_2.38 mismatch
# Use -j2 to avoid OOM during build
RUN cd /tmp && \
    git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git && \
    cd whisper.cpp && \
    mkdir -p build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF && \
    make -j2 && \
    mkdir -p /opt/whisper && \
    cp bin/whisper-cli /opt/whisper/ && \
    cp bin/libwhisper.so* /opt/whisper/ 2>/dev/null || true && \
    cp bin/libggml*.so* /opt/whisper/ 2>/dev/null || true && \
    cd /tmp && rm -rf whisper.cpp && \
    echo "=== whisper.cpp installed ===" && \
    ls -la /opt/whisper/

# ============ WORKDIR ============
WORKDIR /app

# ============ VENV WITH SYSTEM SITE PACKAGES ============
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/whisper:/usr/local/lib"

# ============ COPY SYSTEM MODULES INTO VENV ============
RUN PYVER=$(ls /opt/venv/lib/ | grep python3) && \
    SITE="/opt/venv/lib/${PYVER}/site-packages" && \
    SYS="/usr/lib/python3/dist-packages" && \
    echo "Copying to: $SITE" && \
    cp -r $SYS/lgpio.py $SITE/ 2>/dev/null || true && \
    cp -r $SYS/rgpio.py $SITE/ 2>/dev/null || true && \
    cp -r $SYS/_lgpio*.so $SITE/ 2>/dev/null || true && \
    cp -r $SYS/_rgpio*.so $SITE/ 2>/dev/null || true && \
    cp -r $SYS/spidev* $SITE/ 2>/dev/null || true && \
    cp -r $SYS/smbus* $SITE/ 2>/dev/null || true && \
    echo "=== Files copied to venv ===" && \
    ls -la $SITE/ | grep -E "spidev|lgpio|rgpio|smbus"

# ============ INSTALL PIP PACKAGES ============
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --force-reinstall "numpy<2" && \
    pip install --no-cache-dir spidev smbus2 && \
    pip install --no-cache-dir https://github.com/rpi-ws281x/rpi-ws281x-python/releases/download/pi5-beta2/rpi_ws281x-6.0.0-cp311-cp311-linux_aarch64.whl

# ============ COPY APP ============
COPY . .

EXPOSE 5002

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

CMD ["python3", "app.py"]
