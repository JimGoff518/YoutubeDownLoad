# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Create necessary directories
RUN mkdir -p output temp/audio

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden in railway.json)
CMD ["python", "-m", "src.main", "playlist", "--playlist-url", "${PLAYLIST_URL}"]
