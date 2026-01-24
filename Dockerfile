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

# Make start script executable
RUN chmod +x start.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the web server port
EXPOSE 8080

# Run the start script
CMD ["./start.sh"]
