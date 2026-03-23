# Bill AI Machine - Technical Documentation

Complete reference for all API calls, data models, and operations in this YouTube transcript extraction system.

> See also: [PROJECT_STATUS.md](PROJECT_STATUS.md) for current system status | [ROADMAP.md](ROADMAP.md) for planned features

---

## Table of Contents

1. [System Overview](#system-overview)
2. [API Calls Reference](#api-calls-reference)
3. [Data Models Reference](#data-models-reference)
4. [CLI Commands Reference](#cli-commands-reference)
5. [Configuration Reference](#configuration-reference)
6. [Workflow Diagrams](#workflow-diagrams)

---

## System Overview

### Purpose

Extract transcripts and metadata from YouTube videos, channels, and playlists for machine learning and AI applications.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (main.py)                           │
│              Commands: extract, video, playlist, validate       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VideoProcessor                               │
│              Orchestrates the extraction pipeline               │
└───────┬─────────────────────┬───────────────────────┬───────────┘
        │                     │                       │
        ▼                     ▼                       ▼
┌───────────────┐   ┌─────────────────┐   ┌────────────────────┐
│ YouTubeClient │   │TranscriptFetcher│   │    JSONWriter      │
│ (YouTube API) │   │ (Transcripts)   │   │  (Output Files)    │
└───────────────┘   └────────┬────────┘   └────────────────────┘
                             │
                    ┌────────┴────────┐
                    │  Fallback Path  │
                    ▼                 ▼
            ┌──────────────┐  ┌─────────────────┐
            │AudioDownloader│  │WhisperTranscriber│
            │  (yt-dlp)     │  │  (Whisper AI)    │
            └──────────────┘  └─────────────────┘
```

### Technology Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| YouTube API | google-api-python-client | Fetch video/channel metadata |
| Transcripts | youtube-transcript-api | Extract video transcripts (free, no quota) |
| Data Models | pydantic | Validate and serialize data |
| CLI | typer | Command-line interface |
| Audio Download | yt-dlp | Download audio when transcript unavailable |
| Speech-to-Text | openai-whisper | Transcribe audio to text |
| Progress Bars | tqdm | Visual progress tracking |

---

## API Calls Reference

### YouTube Data API v3

These calls use your YouTube API key and consume quota.

| Call | Code Location | Purpose | Quota Cost |
|------|---------------|---------|------------|
| Get Channel Info | `youtube_client.py:60` | Fetch channel metadata (title, description, subscriber count, topics) | 1 unit |
| Get Uploads Playlist | `youtube_client.py:134` | Get the playlist ID containing all channel uploads | 1 unit |
| Get Playlist Items | `youtube_client.py:146` | Retrieve video IDs from a playlist (50 per page) | 1 unit per 50 videos |
| Get Video Details | `youtube_client.py:193` | Fetch full video metadata (title, duration, view/like counts, tags) | 1 unit per 50 videos |

**Daily Quota Limit:** 10,000 units

**Example: Extracting 100 videos from a channel**
- Channel info: 1 unit
- Get uploads playlist: 1 unit
- Get video IDs (2 pages): 2 units
- Get video details (2 batches): 2 units
- **Total: ~6 units**

### youtube-transcript-api

These calls are free and have no quota limits.

| Call | Code Location | Purpose | Quota Cost |
|------|---------------|---------|------------|
| Get Transcript | `transcript_fetcher.py:47` | Extract transcript in preferred language | Free |
| Get Transcript (fallback) | `transcript_fetcher.py:58` | Extract transcript in any available language | Free |

**Possible Errors:**
- `TranscriptsDisabled` - Creator disabled transcripts for this video
- `NoTranscriptFound` - No transcript exists (rare for recent videos)
- `VideoUnavailable` - Video is private, deleted, or age-restricted

### yt-dlp (Audio Fallback)

Only used when `ENABLE_AUDIO_FALLBACK=true` and no transcript is available.

| Call | Code Location | Purpose |
|------|---------------|---------|
| Download Audio | `audio_downloader.py` | Download video audio as MP3/WebM/M4A for transcription |

### OpenAI Whisper (Audio Fallback)

Only used when audio fallback is enabled.

| Call | Code Location | Purpose |
|------|---------------|---------|
| Load Model | `whisper_transcriber.py` | Load Whisper model into memory (once per session) |
| Transcribe Audio | `whisper_transcriber.py` | Convert audio file to text with timestamps |

**Model Sizes:** tiny, base, small, medium, large (larger = more accurate but slower)

---

## Data Models Reference

All models are defined in `src/models/` and use Pydantic for validation.

### TranscriptSegment

A single timed segment of transcript text.

| Field | Type | Purpose |
|-------|------|---------|
| `text` | str | The spoken words in this segment |
| `start` | float | When this segment begins (seconds from video start) |
| `duration` | float | How long this segment lasts (seconds) |
| `end` | float (computed) | When this segment ends (`start + duration`) |

**File:** [transcript.py:7](src/models/transcript.py#L7)

### Transcript

Complete transcript with all segments and metadata.

| Field | Type | Purpose |
|-------|------|---------|
| `available` | bool | Whether a transcript was found for this video |
| `language` | str | Language code (e.g., "en", "es", "unknown") |
| `is_auto_generated` | bool | True if YouTube auto-generated the transcript |
| `segments` | list | All TranscriptSegment objects in order |
| `full_text` | str (computed) | All segment text joined together for NLP |
| `word_count` | int (computed) | Approximate word count for token estimation |
| `character_count` | int (computed) | Total characters in transcript |

**File:** [transcript.py:21](src/models/transcript.py#L21)

### Video

Complete video record with metadata and transcript.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | str | YouTube video ID (11 characters) |
| `title` | str | Video title for indexing and search |
| `description` | str | Full description for NLP/topic analysis |
| `published_at` | datetime | When video was published (for time-series) |
| `duration_seconds` | int | Video length for filtering short/long content |
| `duration_iso` | str | ISO 8601 duration (e.g., "PT10M30S") |
| `view_count` | int | Total views for popularity metrics |
| `like_count` | int | Total likes for engagement metrics |
| `comment_count` | int | Total comments for engagement metrics |
| `thumbnail_url` | str | High-quality thumbnail URL |
| `tags` | list | Creator-defined keywords for topic classification |
| `category_id` | str | YouTube category ID (e.g., "27" = Education) |
| `category_name` | str | Human-readable category name |
| `default_language` | str | Video's default language setting |
| `default_audio_language` | str | Audio language (useful for multi-language content) |
| `license` | str | "youtube" or "creativeCommon" |
| `privacy_status` | str | "public", "unlisted", or "private" |
| `made_for_kids` | bool | Whether video is marked as kids content |
| `transcript` | Transcript | The extracted transcript data |
| `ml_features` | MLFeatures | Pre-computed ML metrics |

**File:** [video.py:21](src/models/video.py#L21)

### MLFeatures

Pre-computed metrics optimized for machine learning pipelines.

| Field | Type | Purpose |
|-------|------|---------|
| `title_token_count` | int | Approximate tokens in title (for model input sizing) |
| `description_token_count` | int | Approximate tokens in description |
| `transcript_token_count` | int | Approximate tokens in transcript (for context window planning) |
| `total_engagement` | int | Sum of likes + comments |
| `engagement_rate` | float | (likes + comments) / views - normalized comparison metric |
| `views_per_day` | float | views / days_since_published - velocity/trending metric |

**File:** [video.py:10](src/models/video.py#L10)

### Channel

YouTube channel metadata.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | str | Channel ID (starts with "UC", 24 characters) |
| `title` | str | Channel name |
| `description` | str | Channel description/about text |
| `custom_url` | str | Custom URL (e.g., "@channelname") |
| `published_at` | datetime | When channel was created |
| `subscriber_count` | int | Total subscribers |
| `video_count` | int | Total videos on channel |
| `view_count` | int | Total views across all videos |
| `thumbnail_url` | str | Channel avatar image URL |
| `country` | str | Country code if set |
| `topics` | list | Wikipedia topic URLs for content classification |

**File:** [video.py:46](src/models/video.py#L46)

### ExtractionMetadata

Audit trail for the extraction process.

| Field | Type | Purpose |
|-------|------|---------|
| `extracted_at` | datetime | When extraction was performed |
| `extractor_version` | str | Version of this tool (for schema compatibility) |
| `channel_id` | str | Source channel ID |
| `total_videos_processed` | int | How many videos were attempted |
| `successful_extractions` | int | How many transcripts were successfully extracted |
| `failed_extractions` | int | How many videos failed (logged in errors array) |

**File:** [video.py:62](src/models/video.py#L62)

### ErrorEntry

Details about failed video extractions.

| Field | Type | Purpose |
|-------|------|---------|
| `video_id` | str | ID of the video that failed |
| `video_title` | str | Title (if available) for easier identification |
| `error_type` | str | Category of error (e.g., "TranscriptsDisabled") |
| `error_message` | str | Detailed error message |
| `timestamp` | datetime | When the error occurred |

**File:** [video.py:73](src/models/video.py#L73)

### ExtractionResult

Complete output structure for channel/playlist extractions.

| Field | Type | Purpose |
|-------|------|---------|
| `schema_version` | str | Output format version for future compatibility |
| `extraction_metadata` | ExtractionMetadata | Processing audit trail |
| `channel` | Channel | Source channel information |
| `videos` | list | Array of successfully extracted Video objects |
| `errors` | list | Array of ErrorEntry for failed extractions |

**File:** [video.py:83](src/models/video.py#L83)

---

## CLI Commands Reference

All commands are run with `python -m src.main <command>`.

### extract

Extract all videos from a YouTube channel.

```bash
# Using channel ID
python -m src.main extract --channel-id UCxxxxxx

# Using channel URL
python -m src.main extract --channel-url https://www.youtube.com/@channelname

# With options
python -m src.main extract --channel-id UCxxxxxx --output my_data.json --max-videos 50
```

| Option | Purpose |
|--------|---------|
| `--channel-id` | YouTube channel ID (starts with UC) |
| `--channel-url` | Channel URL (will be converted to ID) |
| `--output` | Custom output file path |
| `--max-videos` | Limit number of videos to process |

### video

Extract a single video.

```bash
# Using video ID
python -m src.main video --video-id DIC-E6W4QBw

# Using video URL
python -m src.main video --video-url "https://www.youtube.com/watch?v=DIC-E6W4QBw"

# With custom output
python -m src.main video --video-id DIC-E6W4QBw --output single_video.json
```

| Option | Purpose |
|--------|---------|
| `--video-id` | YouTube video ID (11 characters) |
| `--video-url` | Video URL (any YouTube URL format) |
| `--output` | Custom output file path |

### playlist

Extract all videos from a playlist.

```bash
# Using playlist ID
python -m src.main playlist --playlist-id PLxxxxxx

# Using playlist URL
python -m src.main playlist --playlist-url "https://www.youtube.com/playlist?list=PLxxxxxx"
```

| Option | Purpose |
|--------|---------|
| `--playlist-id` | YouTube playlist ID (starts with PL) |
| `--playlist-url` | Playlist URL with list= parameter |
| `--output` | Custom output file path |
| `--max-videos` | Limit number of videos to process |

### validate

Verify an output file is valid.

```bash
python -m src.main validate output/channel_transcripts.json
```

| Option | Purpose |
|--------|---------|
| File path | Path to JSON file to validate |

---

## Configuration Reference

Set these in your `.env` file or as environment variables.

### Required

| Variable | Purpose | Example |
|----------|---------|---------|
| `YOUTUBE_API_KEY` | Your YouTube Data API v3 key | `AIzaSy...` |

### Processing

| Variable | Purpose | Default |
|----------|---------|---------|
| `MAX_CONCURRENT_VIDEOS` | How many videos to process in parallel | `5` |
| `OUTPUT_DIR` | Where to save output files | `./output` |

### Transcript Settings

| Variable | Purpose | Default |
|----------|---------|---------|
| `PREFERRED_LANGUAGES` | Language priority (comma-separated) | `en,en-US,en-GB` |
| `FALLBACK_TO_AUTO_GENERATED` | Use auto-generated if manual unavailable | `true` |

### Retry Settings

| Variable | Purpose | Default |
|----------|---------|---------|
| `RETRY_ATTEMPTS` | How many times to retry failed API calls | `3` |
| `RETRY_DELAY_SECONDS` | Seconds to wait between retries | `2` |
| `TIMEOUT_SECONDS` | API call timeout | `30` |

### Audio Fallback (Optional)

| Variable | Purpose | Default |
|----------|---------|---------|
| `ENABLE_AUDIO_FALLBACK` | Download and transcribe audio when no transcript | `false` |
| `WHISPER_MODEL` | Whisper model size (tiny/base/small/medium/large) | `base` |
| `CLEANUP_AUDIO` | Delete audio files after transcription | `true` |

---

## Workflow Diagrams

### Channel Extraction Flow

```
1. INPUT: Channel ID or URL
   └── Validate and extract channel ID

2. FETCH CHANNEL INFO (1 API call)
   └── Get channel metadata (title, stats, topics)

3. GET VIDEO LIST (1+ API calls)
   └── Paginate through uploads playlist
   └── Collect all video IDs

4. FETCH VIDEO DETAILS (batched, 50 per call)
   └── Get metadata for each video

5. FOR EACH VIDEO:
   ├── Try preferred language transcript (free)
   ├── Try any available transcript (free)
   ├── If ENABLE_AUDIO_FALLBACK:
   │   ├── Download audio
   │   └── Transcribe with Whisper
   └── Calculate ML features

6. OUTPUT: Write JSON file
   ├── extraction_metadata
   ├── channel info
   ├── videos array
   └── errors array
```

### Single Video Flow

```
1. INPUT: Video ID or URL
   └── Validate and extract video ID

2. FETCH VIDEO DETAILS (1 API call)
   └── Get full video metadata

3. FETCH TRANSCRIPT (free)
   ├── Try preferred languages
   ├── Try any available
   └── Fallback to audio if enabled

4. CALCULATE ML FEATURES
   └── Token counts, engagement rate, views/day

5. OUTPUT: Write JSON file
   ├── extraction_metadata
   └── video object
```

### Audio Fallback Flow

```
1. TRIGGER: No YouTube transcript available

2. DOWNLOAD AUDIO (yt-dlp)
   └── Save as MP3/WebM/M4A

3. LOAD WHISPER MODEL (once per session)
   └── Model size based on WHISPER_MODEL setting

4. TRANSCRIBE
   └── Generate segments with timestamps

5. CLEANUP (if CLEANUP_AUDIO=true)
   └── Delete audio file

6. RETURN: Transcript object
```

---

## Quick Reference

### File Structure

```
src/
├── api/
│   ├── youtube_client.py      # YouTube Data API wrapper
│   ├── transcript_fetcher.py  # Transcript extraction
│   ├── audio_downloader.py    # yt-dlp wrapper
│   └── whisper_transcriber.py # Whisper integration
├── models/
│   ├── video.py               # Video, Channel, MLFeatures models
│   └── transcript.py          # Transcript, TranscriptSegment models
├── processors/
│   └── video_processor.py     # Main processing logic
├── storage/
│   └── json_writer.py         # Output file handling
├── config.py                  # Configuration management
└── main.py                    # CLI entry point
```

### Common Tasks

| Task | Command |
|------|---------|
| Extract channel | `python -m src.main extract --channel-id UCxxxxxx` |
| Extract single video | `python -m src.main video --video-id xxxxxxxxxxx` |
| Extract playlist | `python -m src.main playlist --playlist-id PLxxxxxx` |
| Validate output | `python -m src.main validate output/file.json` |
| Run retrieval eval | `python eval_retrieval.py` |
| Run eval with options | `python eval_retrieval.py --output my_results.json --questions my_questions.json` |

---

## Retrieval Evaluation

### eval_retrieval.py

Standalone script that runs test queries through the full retrieval pipeline (expand → embed → search → threshold filter → rerank) and records per-query metrics.

**Output:** `eval_results.json` with per-query metrics and a console summary.

**Metrics recorded per query:**
- Pinecone results count, score min/max
- After threshold filter count
- After rerank count, Cohere score min/max
- Source filter detection and accuracy
- Top 3 chunk previews with sources

**Rate limiting:** 7-second delay between queries for Cohere trial key (10 calls/min).

### test_questions.json

25 categorized test queries:
- **general_strategy** (6) — broad PI marketing/firm growth
- **source_specific** (6) — mention specific hosts/shows, with `expected_sources`
- **niche** (6) — narrow topics (mass torts, CRMs, LSAs, etc.)
- **should_return_nothing** (4) — off-topic queries
- **drafting** (3) — content creation requests

### Retrieval Logging

Every chatbot query logs metrics to `retrieval_log.jsonl` via `log_retrieval_metrics()` in `rag.py`. Fields: timestamp, query, source_filter, pinecone counts/scores, threshold filter count, rerank count, Cohere scores.

### Source Filtering

`entity_mappings.json` `source_filters` maps keywords to lists of Pinecone source values. The Pinecone filter uses `$in` to match any of the source values. Source values in Pinecone include: `Burbon of Proof PlaylistJson (1)`, `BurbonofProofPlaylist`, `GrowYourLawFirmPlaylist`, `podcast_Grow_Your_Law_Firm`, `JohnMorganInterviews`, `GreySkyMediaPodcast`, `CEOLawyer_AliAwad_Playlist`, `LawOfficeYoutubeFavorites`, `MaximumLawyer_Playlist`, `YouCantTeachHungry_2024`.

---

## Super Agent Configuration (Phase 7)

### goff_law_profile.json

Firm-specific context injected into the Super Agent system prompt. The chatbot loads this file on startup and uses it to personalize all responses.

```json
{
  "firm": {
    "name": "Goff Law",
    "location": "Dallas, TX",
    "market": "Dallas-Fort Worth metroplex",
    "practice_areas": ["Personal Injury", "Car Accidents", "Truck Accidents", ...]
  },
  "team": {
    "owner": { "name": "Jim", "role": "Firm Owner / Managing Attorney" },
    "coo": { "name": "Chelsea", "role": "Chief Operating Officer" }
  },
  "marketing": {
    "current_channels": ["Google (organic + LSAs)", "Referrals", "Social media"],
    "growth_priorities": ["Increase case volume", "Improve intake conversion", ...],
    "competitive_landscape": "Competing against large PI advertisers (Jim Adler, etc.)"
  },
  "super_agent": {
    "role": "Director of Marketing",
    "mission": "Make Goff Law the best-marketed PI firm in Dallas..."
  }
}
```

The system prompt in `rag.py` references `FIRM_PROFILE` to include firm name, location, team members, growth priorities, and competitive context in every response.

---

## Key Takeaways Extraction (Phase 7)

### extract_takeaways.py

Processes episode transcripts using Claude to extract structured metadata. Run from the command line.

**Usage:**
```bash
# Extract takeaways from all episodes (skips already processed)
python extract_takeaways.py

# Force re-extraction of all episodes
python extract_takeaways.py --force

# Limit to first N episodes
python extract_takeaways.py --limit 10

# Show summary of existing takeaways
python extract_takeaways.py --summary

# Search takeaways by keyword
python extract_takeaways.py --search "intake"

# List takeaways by subject area
python extract_takeaways.py --category "Digital Marketing"
```

**Extraction output per episode:**
| Field | Type | Purpose |
|-------|------|---------|
| `key_takeaways` | list | 3-5 actionable bullet points |
| `subject_area` | str | Primary category (e.g., "Intake Optimization", "Digital Marketing") |
| `topics` | list | 3-7 specific topic tags |
| `unique_insights` | str | Novel/contrarian ideas or "None identified" |
| `action_items` | list | 1-3 implementable actions |
| `notable_quotes` | list | 1-2 memorable quotes |

### takeaways_index.json

Stores all extracted takeaways, indexed by episode ID.

```json
{
  "version": "1.0",
  "updated_at": "2026-02-10T...",
  "total_episodes": 1442,
  "episodes": {
    "abc123def456": {
      "source": "Burbon of Proof PlaylistJson (1)",
      "title": "Episode Title...",
      "content_type": "video",
      "extracted_at": "2026-02-08T15:55:00+00:00",
      "key_takeaways": ["..."],
      "subject_area": "Intake Optimization",
      "topics": ["AI intake", "call monitoring", ...],
      "unique_insights": "...",
      "action_items": ["..."],
      "notable_quotes": ["..."]
    }
  }
}
```

The pipeline skips episodes with insufficient transcript (< 500 chars) and saves progress after each extraction for resume-safe operation.

### Takeaways Integration in Chatbot

The RAG pipeline (`rag.py`) loads `takeaways_index.json` at startup and builds two lookup structures:

| Structure | Key | Purpose |
|-----------|-----|---------|
| `TAKEAWAYS_BY_SOURCE_TITLE` | `(source, title)` tuple | O(1) episode matching against Pinecone chunk metadata |
| `TAKEAWAYS_BY_TOPIC` | lowercase topic string | Inverted index for keyword-based topic matching |

**Retrieval strategy** (`get_relevant_takeaways()`):
1. **Episode-matched (primary):** For each Pinecone result chunk, look up `(source, episode_title)` in the takeaways index
2. **Topic-matched (supplementary):** If fewer than 5 matches found, scan query keywords against the topics inverted index
3. **Cap:** Maximum 5 takeaways per query (~600-1,200 extra tokens)

**Prompt injection** (`format_takeaways_for_prompt()`):
- Formatted as structured text blocks between the context chunks and instructions in the user message
- Each block includes: source, title, category, bullet-point takeaways, and action items
- System prompt HOW TO WORK section instructs Claude to use Episode Takeaways for synthesis

---

## Auto-Refresh Pipeline (Phase 9)

### auto_refresh.py

Automated ingestion pipeline that checks monitored YouTube sources for new episodes, transcribes them via Whisper, chunks/embeds/upserts to Pinecone, and extracts takeaways via Claude.

**Usage:**
```bash
# Refresh all enabled sources
python auto_refresh.py

# Refresh a single source by name
python auto_refresh.py --source "PI Wingman"

# Dry run (check for new episodes without ingesting)
python auto_refresh.py --dry-run
```

**Pipeline steps per episode:**
1. YouTube API check for new videos (not in `known_video_ids`)
2. yt-dlp audio download → ffmpeg compression
3. OpenAI Whisper transcription (splits >25MB files into 15-min chunks)
4. Text chunking (800 tokens, 100 overlap)
5. OpenAI embeddings → Pinecone upsert
6. Claude takeaways extraction
7. Update `sources_registry.json` with new video IDs
8. Log results to `refresh_log.json`

### sources_registry.json

Config file tracking all monitored YouTube sources and their ingestion state.

```json
{
  "version": "1.0",
  "sources": [
    {
      "name": "PI Wingman",
      "type": "youtube_channel",
      "channel_id": "UCFlV9DM5dSwE2SG_6QxlEQA",
      "output_source_name": "PIWingman",
      "display_name": "PI Wingman (Cases On Demand)",
      "enabled": true,
      "known_video_ids": ["video_id_1", "video_id_2", ...]
    }
  ]
}
```

| Field | Purpose |
|-------|---------|
| `name` | Human-readable source name (used with `--source` flag) |
| `type` | `youtube_channel` or `youtube_playlist` |
| `channel_id` / `playlist_id` | YouTube identifier for the source |
| `output_source_name` | Pinecone `source` metadata value and output JSON filename |
| `display_name` | Full display name for UI |
| `enabled` | Whether auto-refresh includes this source |
| `known_video_ids` | List of already-ingested video IDs (prevents duplicates) |

---

## Dashboard Command Center (Phase 8.3)

### Architecture

The UI is a Flask-served vanilla HTML/CSS/JS app with two views (Dashboard and Chat) controlled by SPA-style tab switching. No frameworks, no build step.

| File | Purpose |
|------|---------|
| `server.py` | Flask backend — page routes, conversation API, chat SSE, stats API, news API |
| `rag.py` | RAG pipeline — search, rerank, takeaways, prompt builder, streaming |
| `templates/index.html` | HTML template — Dashboard + Chat views, tab nav, sidebar |
| `static/style.css` | CSS — Apple-inspired design system, responsive breakpoints |
| `static/app.js` | Client JS — view switching, stats fetch, news fetch, SSE streaming |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve the main HTML page |
| `/api/conversations` | GET | List all conversations |
| `/api/conversations` | POST | Create a new conversation |
| `/api/conversations/<id>/messages` | GET | Get messages for a conversation |
| `/api/conversations/<id>` | DELETE | Delete a conversation |
| `/api/chat/stream` | POST | SSE streaming chat (query + conversation_id) |
| `/api/stats` | GET | Dashboard stats (episodes, sources, topics, conversations) |
| `/api/news` | GET | PI/mass tort news headlines (cached 30 min) |

### News Ticker

Fetches from two sources:
- **Google News RSS** — queries: "personal injury law firm", "mass tort litigation" (via `feedparser`)
- **Reddit JSON API** — r/law hot posts (public, no auth, `User-Agent: BillAIMachine/1.0`)

Cache: 30 minutes (`NEWS_CACHE_SECONDS = 1800`). Deduplicates by title. Returns `[{title, url, source, published_ago}]`.

### Stats API

Reads from `TAKEAWAYS_INDEX` (loaded at startup in `rag.py`):
- `episodes`: total_episodes count
- `sources`: count of `SOURCE_DISPLAY_NAMES`
- `topics`: unique topics + subject areas across all episodes
- `conversations`: count from `get_all_conversations()`
