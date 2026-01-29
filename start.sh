#!/bin/bash
set -e

echo "Starting YouTube Transcript Extractor..."

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
