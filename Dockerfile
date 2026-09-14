FROM python:3.11-slim

# ============ SETUP ============
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    gcc \
    g++ \
    make \
    python3-dev \
    libffi-dev \
    libgpiod2 \
    python3-smbus \
    i2c-tools \
    ffmpeg \
    libsdl2-dev \
    libsdl2-2.0-0 \
    libcamera-dev \
    libcap-dev \
    python3-picamera2 \
    python3-libcamera \
    libopenblas-dev \
    libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# ============ PYTHON DEPENDENCIES ============
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============ COPY APPLICATION ============
COPY . .

# ============ EXPOSE PORT ============
EXPOSE 5002

# ============ RUN ============
CMD ["python", "app.py"]
