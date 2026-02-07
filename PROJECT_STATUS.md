# Bill AI Machine - Project Status

**Last updated:** February 1, 2026
**Owner:** Goff Law (Personal Injury Law Firm, Dallas TX)

---

## What This Is

An AI-powered knowledge base that ingests YouTube videos and podcasts, transcribes them, and makes the content queryable through a Claude-powered chatbot. Built for personal injury law firm marketing and strategy.

---

## System Architecture

```
Content Sources          Processing              Storage              Interface
─────────────────       ──────────────          ─────────────        ──────────────
YouTube Channels  ──┐
YouTube Playlists ──┼── CLI Extractor ────────► JSON Files
YouTube Videos    ──┘   (src/main.py)               │
                                                    │
Podcast RSS Feeds ───── Podcast Extractor ──────► JSON Files
                        (src/main.py)               │
                                                    ▼
                        Ingestion Pipeline ──► Pinecone (vectors)
                        (ingest_to_pinecone.py)     │
                                                    ▼
                        RAG Chatbot ◄─────── Semantic Search
                        (chat_app_with_history.py)  │
                              │                     │
                              ▼                     │
                        Claude API ◄────────────────┘
                              │
                              ▼
                        Streamlit Web UI
                              │
                              ▼
                        PostgreSQL / SQLite
                        (conversation history)
```

---

## Components & Status

### 1. Content Extraction (Working)

| Feature | File | Status |
|---------|------|--------|
| YouTube channel extraction | `src/main.py` | Working |
| YouTube single video extraction | `src/main.py` | Working |
| YouTube playlist extraction | `src/main.py` | Working |
| Podcast RSS feed extraction | `src/main.py` | Working |
| Whisper audio fallback | `src/api/whisper_transcriber.py` | Working |
| Output validation | `src/main.py validate` | Working |

### 2. Knowledge Ingestion (Working)

| Feature | File | Status |
|---------|------|--------|
| Text chunking (800 tokens, 100 overlap) | `ingest_to_pinecone.py` | Working |
| OpenAI embeddings (text-embedding-3-small) | `ingest_to_pinecone.py` | Working |
| Pinecone upsert with metadata | `ingest_to_pinecone.py` | Working |

### 3. RAG Chatbot (Working)

| Feature | File | Status |
|---------|------|--------|
| Streamlit web UI | `chat_app_with_history.py` | Working |
| Claude responses (streaming) | `chat_app_with_history.py` | Working |
| Conversation history (PostgreSQL/SQLite) | `database.py` | Working |
| Query expansion (entity mappings) | `chat_app_with_history.py` | Working |
| Score threshold filtering (>0.3) | `chat_app_with_history.py` | Working |
| Cohere reranking (top 25 → top 10) | `chat_app_with_history.py` | Working |
| Source-specific metadata filtering ($in) | `chat_app_with_history.py` | Working |
| Dynamic entity mappings (JSON config) | `entity_mappings.json` | Working |
| Per-query retrieval logging (JSONL) | `chat_app_with_history.py` | New |
| Retrieval evaluation framework | `eval_retrieval.py` | New |
| Apple-inspired UI/CSS overhaul | `chat_app_with_history.py` | New |
| Streamlit theme config | `.streamlit/config.toml` | New |

### 4. Infrastructure (Working)

| Feature | File | Status |
|---------|------|--------|
| Flask file server | `server.py` | Working |
| Docker deployment | `Dockerfile` | Working |
| Railway startup script | `start.sh` | Working |
| Dev container (Codespaces) | `.devcontainer/` | Working |

### 5. Helper Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `transcribe_videos.py` | Batch transcribe local video files | Working |
| `transcribe_local_audio.py` | Batch transcribe local audio files | Working |
| `retry_failed_transcriptions.py` | Retry failed transcriptions with chunking | Working |
| `parse_logs.py` | Debug log parsing | Working |
| `extract_pdf.py` | Extract text from PDFs to ingestion-compatible JSON | New |
| `extract_web_article.py` | Extract web articles to ingestion-compatible JSON | New |
| `extract_youtube.py` | YouTube video extraction (Windows-safe wrapper) | New |
| `extract_trial_lawyer.py` | Magazine article classifier (Claude-powered, marketing relevance) | New |
| `ingest_new_sources.py` | Selective ingestion of specific JSON files to Pinecone | New |

### 6. Automated Tests (New)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_models.py` | 18 | Pydantic models (Transcript, Video, Channel, Podcast) |
| `tests/test_config.py` | 7 | Config parsing, env vars, validation |
| `tests/test_json_writer.py` | 6 | JSON write/validate/summary |
| `tests/test_database.py` | 9 | Conversation CRUD (in-memory SQLite) |
| `tests/test_utils.py` | 18 | chunk_text, URL parsers, duration/date parsing |
| `tests/test_youtube_client.py` | 8 | YouTube API (mocked Google client) |
| `tests/test_transcript_fetcher.py` | 5 | Transcript fetch, retry, language fallback |
| `tests/test_podcast_fetcher.py` | 5 | RSS feed parsing (mocked HTTP) |
| `tests/test_video_processor.py` | 8 | ML features, video/channel processing |
| `tests/test_ingestion.py` | 7 | Transcript file processing, chunking |
| **Total** | **107** | Run: `python -m pytest tests/ -v` |

---

## Required Services & API Keys

All keys go in `.env` file.

| Service | Env Variable | Purpose | Required? |
|---------|-------------|---------|-----------|
| YouTube Data API v3 | `YOUTUBE_API_KEY` | Video/channel metadata | For extraction |
| OpenAI | `OPENAI_API_KEY` | Embeddings + Whisper | For ingestion & chatbot |
| Anthropic | `ANTHROPIC_API_KEY` | Claude chat responses | For chatbot |
| Pinecone | `PINECONE_API_KEY` | Vector storage & search | For chatbot |
| Cohere | `COHERE_API_KEY` | Result reranking | For chatbot |
| PostgreSQL | `DATABASE_URL` | Conversation history (production) | For Railway deploy |
| LangChain | `LANGCHAIN_API_KEY` | Tracing (optional) | No |

---

## Key Configuration

| Setting | Value | Location |
|---------|-------|----------|
| Embedding model | text-embedding-3-small (1024 dims) | `chat_app_with_history.py` |
| Chat model | claude-sonnet-4-20250514 | `chat_app_with_history.py` |
| Rerank model | rerank-v3.5 | `chat_app_with_history.py` |
| Pinecone index | legal-docs | `chat_app_with_history.py` |
| Chunk size | 800 tokens (~3200 chars) | `ingest_to_pinecone.py` |
| Chunk overlap | 100 tokens (~400 chars) | `ingest_to_pinecone.py` |
| Retrieval top-k | 25 (then reranked to 10) | `chat_app_with_history.py` |
| Min score threshold | 0.3 | `chat_app_with_history.py` |
| Conversation history | Last 20 messages (10 exchanges) | `chat_app_with_history.py` |

---

## Content Sources Ingested

Entity mappings are configured in `entity_mappings.json`. Pinecone index: **10,355 vectors** (as of Jan 31, 2026).

| Source | Type | Pinecone source name | Entity mapped |
|--------|------|---------------------|---------------|
| Grow Your Law Firm Podcast (Ken Hardison) | Podcast | `GrowYourLawFirmPlaylist`, `podcast_Grow_Your_Law_Firm` | Yes |
| Bourbon of Proof Podcast (Bob Simon) | YouTube | `Burbon of Proof PlaylistJson (1)`, `BurbonofProofPlaylist` | Yes |
| John Morgan / Morgan & Morgan | YouTube | `JohnMorganInterviews` | Yes |
| Grey Sky Media Podcast | Podcast | `GreySkyMediaPodcast` | Yes |
| CEO Lawyer / Ali Awad | YouTube | `CEOLawyer_AliAwad_Playlist` | Yes |
| You Can't Teach Hungry (Mike Morse) | YouTube | `YouCantTeachHungry_2024` | Yes |
| Maximum Lawyer Podcast | YouTube | `MaximumLawyer_Playlist` | Yes |
| PIM Podcast | Podcast | `PIM_Podcast_Season1`, `PIM_Podcast_Season2` | Yes |
| Colleen Joy — Legal Intake & AI | YouTube | `ptimizing Legal Intake...` | Yes |
| Law Office YouTube Favorites | YouTube | `LawOfficeYoutubeFavorites` | No |
| Abrams Rd transcript (voice memo) | Audio | `Abrams_Rd_transcript` | No |
| Law Firm Marketing Secrets 2025 (3 videos) | YouTube | `youtube_ZBAC0BA4ux8`, `youtube_cn6zcEhH-qU`, `youtube_DQZvcjcG_cI` | Yes |
| First AML Legal Tech Trends Report 2025 | PDF | `LegalTechTrends2025` | Yes |
| CMO Survey 2025 (LMA-ATL) | PDF | `CMOSurvey2025` | Yes |
| Attorney at Work — Marketing Trends 2026 | Web | `AttorneyAtWork_MarketingTrends2026` | Yes |
| Trial Lawyer Magazine (8 issues, 2024-2025) | PDF | `TrialLawyer_Spring2024` thru `TrialLawyer_AList2025` | Yes |
| PreLitGuru Sessions | YouTube | `PreLitGuru_Sessions` | **Removed** |

---

## How to Run

### Chatbot (main app)
```bash
pip install -r requirements.txt
streamlit run chat_app_with_history.py
```

### Extract content
```bash
# YouTube channel
python -m src.main extract --channel-url https://www.youtube.com/@channelname

# Podcast
python -m src.main podcast --rss-url "https://feed.url"
```

### Ingest to Pinecone
```bash
python ingest_to_pinecone.py
```

### Deploy (Docker/Railway)
```bash
docker build -t bill-ai-machine .
docker run -p 8080:8080 --env-file .env bill-ai-machine
```

---

## Recent Changes

- **Feb 1, 2026 (session 8):** Status check & continued transcription — Reviewed project status and roadmap. Resumed PIM podcast batch transcription (Season 2 remaining 32 episodes completed, Season 3 in progress). Attempted MaxLawCon 2022 zip extraction from Box — file was empty/corrupt (202 bytes), needs re-download. Created `COMMANDS.md` cheat sheet for MARVIN CLI commands.
- **Jan 31, 2026 (session 7):** New content ingestion — Built PDF extraction (`extract_pdf.py`), web article extraction (`extract_web_article.py`), YouTube wrapper (`extract_youtube.py`), and Trial Lawyer magazine article classifier (`extract_trial_lawyer.py`). Ingested 14 new sources: 3 YouTube videos (law firm marketing 2025), 2 industry report PDFs (Legal Tech Trends, CMO Survey), 1 web article (Attorney at Work 2026 trends), 8 Trial Lawyer magazine issues (marketing articles only, LLM-filtered). 238 new chunks added to Pinecone (10,355 total vectors). Updated entity mappings for all new sources. Added pdfplumber, beautifulsoup4, lxml, requests to requirements.txt.
- **Jan 31, 2026 (session 6):** Batch transcription round 2 — Discovered Box zip downloads contain significantly more episodes than originally processed (S1: 92 vs 43, S2: 97 vs 28, S3: 150 vs 4). Extracted 6 zip files to temp directory. Started transcription of 264 missing episodes across all 3 PIM seasons. Transcription running via Whisper API (resume-safe). Streamlit Community Cloud account confirmed suspended/app deleted — hosting migration needed. Updated entity mappings for 9 previously unmapped sources.
- **Jan 30, 2026 (session 5):** Planning session — Defined Super Agent vision statement (AI Director of Marketing for Goff Law). Audited output folder: 14 JSON files exist, only 4 have entity mappings. Decisions: remove PreLitGuru from Pinecone, add entity mappings for 9 unmapped sources, build episode relevance classifier to filter non-marketing content, add ingestion exclude list. Added 6 new roadmap phases: Phase 9 (Auto-Refresh Pipeline), Phase 10 (Security), Phase 11 (Memory Retention), Phase 12 (Image Generation), Phase 13 (Chelsea's Dashboard & Notifications), Phase 14 (Customer Satisfaction). Identified Chelsea (COO) as key user alongside Jim. Updated ROADMAP.md with vision and all new phases.
- **Jan 30, 2026 (session 4):** Discussion-only session — Diagnosed Streamlit Community Cloud rate limit block. Researched hosting alternatives (Railway, AWS Free Tier, Render, Reflex, Dash Enterprise). Decision pending: likely migrate Streamlit app to Railway for reliable paid hosting (~$5-20/month) to avoid free-tier limits.
- **Jan 30, 2026 (session 3):** Phase 6.6 Automated Tests — Built full pytest test suite from scratch (107 tests across 10 test files). Covers models, config, JSON storage, database CRUD, text chunking, URL parsing, YouTube API, transcript fetcher, podcast fetcher, video processor, ingestion pipeline. All external APIs mocked. Fixed bug in `chunk_text()` (infinite loop on whitespace-only input). Added pytest/pytest-cov/pytest-mock to requirements.txt, `pytest.ini`, `tests/` directory.
- **Jan 29, 2026 (session 2):** Phase 8.3 UI Overhaul — Added Apple-inspired custom CSS (~140 lines), `.streamlit/config.toml` theme, redesigned sidebar (compact conversation list, uppercase headers, clean buttons), pill-shaped chat input with blue focus ring, sources card component, removed all emojis, hidden Streamlit chrome. Added Phase 8 to ROADMAP.md.
- **Jan 30, 2026:** Implemented Phase 2.2 and 2.3 — retrieval evaluation framework (`eval_retrieval.py`, `test_questions.json`), per-query JSONL logging, improved no-results handler, fixed source filter bug (mapped to actual Pinecone source values, `$eq` → `$in`). Eval results: 6/6 source accuracy, 4/4 off-topic filtering, 0 false positives. Added Cohere API key.
- **Jan 29, 2026:** Transcribed voice memo (Abrams Rd.m4a) with project vision for Super Agent. Added Phase 7 (Super Agent — Director of Marketing) to ROADMAP.md with episode key takeaways extraction pipeline and proactive marketing intelligence features.
- **Jan 2026:** Added Cohere reranking, score threshold filtering, metadata-based source filtering, externalized entity mappings to JSON config. Created PROJECT_STATUS.md, ROADMAP.md. Added doc cross-references in README.md and DOCUMENTATION.md.
- **Earlier:** Added streaming responses, caching, retry logic, pinned dependencies, conversation history with PostgreSQL, fixed API key leak

---

## File Structure

```
Bill AI Machine/
├── src/                          # Core extraction library
│   ├── main.py                   # CLI entry point
│   ├── config.py                 # Configuration
│   ├── api/                      # API clients
│   │   ├── youtube_client.py
│   │   ├── transcript_fetcher.py
│   │   ├── audio_downloader.py
│   │   ├── whisper_transcriber.py
│   │   └── podcast_fetcher.py
│   ├── models/                   # Pydantic data models
│   │   ├── transcript.py
│   │   ├── video.py
│   │   └── podcast.py
│   ├── processors/
│   │   └── video_processor.py
│   └── storage/
│       └── json_writer.py
├── .streamlit/config.toml        # Streamlit theme (Apple-inspired colors)
├── chat_app_with_history.py      # Main RAG chatbot (Streamlit)
├── chat_app.py                   # Basic chatbot (no history)
├── database.py                   # Conversation persistence
├── ingest_to_pinecone.py         # Transcript → Pinecone pipeline
├── entity_mappings.json          # Query expansion & source filter config
├── COMMANDS.md                   # MARVIN CLI commands cheat sheet
├── PROJECT_STATUS.md             # Current system status & architecture
├── ROADMAP.md                    # Phased feature roadmap
├── extract_pdf.py                # PDF → ingestion JSON extractor
├── extract_web_article.py        # Web article → ingestion JSON extractor
├── extract_youtube.py            # YouTube video extractor (Windows-safe)
├── extract_trial_lawyer.py       # Magazine article classifier (Claude LLM)
├── ingest_new_sources.py         # Selective Pinecone ingestion script
├── eval_retrieval.py             # Retrieval quality evaluation script
├── test_questions.json           # 25 test queries for eval framework
├── eval_results.json             # Latest eval run output
├── DOCUMENTATION.md              # Technical reference (extraction APIs & models)
├── server.py                     # Flask file server
├── Dockerfile                    # Container definition
├── start.sh                      # Container startup
├── requirements.txt              # Python dependencies
├── .env                          # API keys (not committed)
├── pytest.ini                    # pytest configuration
├── tests/                        # Automated test suite (107 tests)
│   ├── conftest.py               # Shared fixtures
│   ├── test_models.py            # Pydantic model tests
│   ├── test_config.py            # Config parsing tests
│   ├── test_json_writer.py       # JSON storage tests
│   ├── test_database.py          # Database CRUD tests
│   ├── test_utils.py             # Utility function tests
│   ├── test_youtube_client.py    # YouTube API tests (mocked)
│   ├── test_transcript_fetcher.py # Transcript fetcher tests (mocked)
│   ├── test_podcast_fetcher.py   # Podcast fetcher tests (mocked)
│   ├── test_video_processor.py   # Video processor tests (mocked)
│   └── test_ingestion.py         # Ingestion pipeline tests
├── output/                       # Extracted JSON files
└── .devcontainer/                # GitHub Codespaces config
```
