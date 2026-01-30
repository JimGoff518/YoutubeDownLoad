# YouTube Channel Transcript Extractor

Extract transcripts from all videos in a YouTube channel with rich metadata optimized for machine learning and agent knowledge applications.

> **Full Technical Reference:** See [DOCUMENTATION.md](DOCUMENTATION.md) for complete API calls, data models, and configuration details.
> **Current Project Status:** See [PROJECT_STATUS.md](PROJECT_STATUS.md) for architecture, components, and configuration.
> **Feature Roadmap:** See [ROADMAP.md](ROADMAP.md) for planned phases and future features.

## Features

- Extract transcripts from entire YouTube channels
- Rich metadata including video details, engagement metrics, and channel information
- ML-optimized JSON output with token counts and engagement rates
- Timestamp-preserved transcript segments for temporal analysis
- Graceful error handling for missing transcripts
- Progress tracking with visual progress bars
- No transcript API quota usage (uses scraping-based extraction)

## Prerequisites

- Python 3.9 or higher
- YouTube Data API v3 key

## Getting a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3:
   - Navigate to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy your API key
5. (Optional but recommended) Restrict your API key:
   - Click on your API key
   - Under "API restrictions", select "Restrict key"
   - Choose "YouTube Data API v3"

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Edit `.env` and add your YouTube API key:
```
YOUTUBE_API_KEY=your_actual_api_key_here
```

## Usage

### Extract from a Single Video

Extract transcript from a single YouTube video:

```bash
# Using video URL
python -m src.main video --video-url "https://www.youtube.com/watch?v=DIC-E6W4QBw"

# Using video ID
python -m src.main video --video-id DIC-E6W4QBw

# With custom output path
python -m src.main video --video-url "https://www.youtube.com/watch?v=DIC-E6W4QBw" --output my_video.json
```

### Extract from a Channel

Extract transcripts from all videos in a channel:

```bash
# Using channel ID
python -m src.main extract --channel-id UCxxxxxx

# Using channel URL
python -m src.main extract --channel-url https://www.youtube.com/@channelname

# With custom output path
python -m src.main extract --channel-id UCxxxxxx --output my_transcripts.json

# Limit number of videos (for testing)
python -m src.main extract --channel-id UCxxxxxx --max-videos 10
```

## Output Format

### Single Video Output

For single video extraction, the output is simplified:

```json
{
  "extraction_metadata": {
    "extracted_at": "2026-01-23T15:30:00Z",
    "extractor_version": "1.0.0",
    "video_id": "DIC-E6W4QBw"
  },
  "video": {
    "id": "DIC-E6W4QBw",
    "title": "Video Title",
    "description": "Video description...",
    "published_at": "2023-01-15T10:00:00Z",
    "duration_seconds": 600,
    "view_count": 10000,
    "like_count": 500,
    "comment_count": 50,
    "tags": ["tag1", "tag2"],
    "transcript": {
      "available": true,
      "language": "en",
      "is_auto_generated": false,
      "segments": [
        {
          "text": "Hello everyone",
          "start": 0.0,
          "duration": 2.5
        }
      ],
      "full_text": "Complete transcript...",
      "word_count": 1500
    },
    "ml_features": {
      "transcript_token_count": 1500,
      "engagement_rate": 0.055,
      "views_per_day": 50.25
    }
  }
}
```

### Channel Extraction Output

For channel extraction, the output includes multiple videos:

```json
{
  "extraction_metadata": {
    "extracted_at": "2026-01-23T15:30:00Z",
    "channel_id": "UCxxxxxx",
    "total_videos_processed": 150,
    "successful_extractions": 145
  },
  "channel": {
    "id": "UCxxxxxx",
    "title": "Channel Name",
    "description": "Channel description",
    "subscriber_count": 1000000,
    "video_count": 150,
    "published_at": "2015-01-01T00:00:00Z"
  },
  "videos": [
    {
      "id": "video_id",
      "title": "Video Title",
      "published_at": "2023-01-15T10:00:00Z",
      "duration_seconds": 600,
      "view_count": 10000,
      "like_count": 500,
      "comment_count": 50,
      "tags": ["tag1", "tag2"],
      "transcript": {
        "available": true,
        "language": "en",
        "segments": [
          {
            "text": "Hello everyone",
            "start": 0.0,
            "duration": 2.5
          }
        ],
        "full_text": "Complete transcript...",
        "word_count": 1500
      },
      "ml_features": {
        "transcript_token_count": 1500,
        "engagement_rate": 0.055
      }
    }
  ],
  "errors": [
    {
      "video_id": "xxx",
      "error_type": "TranscriptNotAvailable",
      "error_message": "No transcript available for this video"
    }
  ]
}
```

## Troubleshooting

### API Quota Exceeded
The YouTube Data API has a quota of 10,000 units per day. Each video detail request costs about 4 units, so you can process approximately 2,500 videos per day. The transcript extraction uses a separate scraping-based API with no quota limits.

If you exceed your quota:
- Wait 24 hours for quota reset
- Process in smaller batches using `--max-videos`
- Request a quota increase from Google Cloud Console

### Missing Transcripts
Some videos may not have transcripts available:
- Transcripts disabled by the creator
- Very recent videos (transcripts not yet generated)
- Private or unlisted videos

These videos will be logged in the `errors` array but won't stop the extraction process.

### Invalid Channel ID
Make sure you're using the correct channel ID format:
- Channel ID: `UCxxxxxx` (starts with UC)
- Channel URL: `https://www.youtube.com/@channelname` or `https://www.youtube.com/channel/UCxxxxxx`

## API Quota Usage

- **Channel info**: 1 unit
- **Video list** (per 50 videos): 1 unit
- **Video details** (per 50 videos): 1 unit
- **Total for 100 videos**: ~5 units
- **Transcript extraction**: 0 units (no quota usage)

## Performance

- Processing speed: ~500ms per video
- With 5 concurrent requests: ~100 videos per minute
- Output size: ~5-10KB per video with transcript

## License

MIT License - Feel free to use this for your machine learning and AI projects!
