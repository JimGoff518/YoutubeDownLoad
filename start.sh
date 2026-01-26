#!/bin/bash
set -e

echo "Starting YouTube Transcript Extractor..."

# Debug: Check youtube-transcript-api version and test it
echo "=== DEBUG: Checking youtube-transcript-api ==="
python -c "
import pkg_resources
version = pkg_resources.get_distribution('youtube-transcript-api').version
print(f'youtube-transcript-api version: {version}')

from youtube_transcript_api import YouTubeTranscriptApi
print(f'API methods: {[m for m in dir(YouTubeTranscriptApi) if not m.startswith(\"_\")]}')

# Quick test
api = YouTubeTranscriptApi()
try:
    result = api.fetch('dQ0aazXCHw4')
    print(f'API test: SUCCESS - got {len(list(result))} segments')
except Exception as e:
    print(f'API test: FAILED - {e}')
"
echo "=== END DEBUG ==="

# Run the playlist extraction if PLAYLIST_URL is set
if [ -n "$PLAYLIST_URL" ]; then
    echo "Processing playlist: $PLAYLIST_URL"
    python -m src.main playlist --playlist-url "$PLAYLIST_URL" || true
    echo ""
    echo "Playlist processing complete!"
else
    echo "No PLAYLIST_URL set, skipping extraction."
fi

echo ""
echo "Starting file server on port ${PORT:-8080}..."
echo "Visit the root URL to see available files for download."
echo ""

# Start the web server
python server.py
