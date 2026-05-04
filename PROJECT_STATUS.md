# Bill AI Machine - Project Status

**Last updated:** May 4, 2026
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
                        RAG Pipeline ◄─────── Semantic Search
                        (rag.py)                    │
                              │                     │
                              ▼                     │
                        Claude API ◄────────────────┘
                              │
                              ▼
                        Flask Web UI ◄─── Dashboard + Chat
                        (server.py)        (News ticker, Stats,
                              │             Quick-action prompts)
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
| Flask web UI (Dashboard + Chat) | `server.py`, `templates/`, `static/` | Working |
| Claude responses (streaming SSE) | `rag.py`, `server.py` | Working |
| Conversation history (PostgreSQL/SQLite) | `database.py` | Working |
| Query expansion (entity mappings) | `rag.py` | Working |
| Score threshold filtering (>0.3) | `rag.py` | Working |
| Cohere reranking (top 25 → top 10) | `rag.py` | Working |
| Source-specific metadata filtering ($in) | `rag.py` | Working |
| Dynamic entity mappings (JSON config) | `entity_mappings.json` | Working |
| Per-query retrieval logging (JSONL) | `rag.py` | Working |
| Retrieval evaluation framework | `eval_retrieval.py` | Working |
| Takeaways context enrichment | `rag.py` | Working |
| Episode takeaways extraction | `extract_takeaways.py` | Working |
| Dashboard stats API | `server.py` `/api/stats` | Working |
| News ticker (Google News + Reddit) | `server.py` `/api/news` | Working |
| Quick-action prompt cards | `templates/index.html` | Working |
| Dashboard "Refresh Now" button | `server.py` `/api/refresh` | Working |
| Dashboard notification banner | `templates/index.html` | Working |

### 4. Infrastructure (Working)

| Feature | File | Status |
|---------|------|--------|
| Flask web app + API | `server.py` | Working |
| Docker deployment | `Dockerfile` | Working |
| Railway startup script | `start.sh` | Working |
| Dev container (Codespaces) | `.devcontainer/` | Working |
| **Railway Production** | — | **Live** |

**Production URL:** `https://gofflawsuperagent.up.railway.app/`

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
| `auto_refresh.py` | Auto-refresh pipeline: check → extract → chunk → embed → takeaways | **New** |
| `sources_registry.json` | Source registry with known episode IDs for dedup | **New** |
| `.github/workflows/auto-refresh.yml` | Weekly cron — runs `auto_refresh.py` every Sunday 3 AM UTC, commits results back to repo | **New** |

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
| Embedding model | text-embedding-3-small (1024 dims) | `rag.py` |
| Chat model | claude-sonnet-4-20250514 | `rag.py` |
| Rerank model | rerank-v3.5 | `rag.py` |
| Pinecone index | legal-docs | `rag.py` |
| Chunk size | 800 tokens (~3200 chars) | `ingest_to_pinecone.py` |
| Chunk overlap | 100 tokens (~400 chars) | `ingest_to_pinecone.py` |
| Retrieval top-k | 25 (then reranked to 10) | `rag.py` |
| Min score threshold | 0.3 | `rag.py` |
| Conversation history | Last 20 messages (10 exchanges) | `rag.py` |

---

## Content Sources Ingested

Entity mappings are configured in `entity_mappings.json`. Takeaways: **1,442 episodes** extracted (as of Mar 23, 2026).

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
| Tip the Scales (Bob Simon) | Podcast | `TipTheScales` | Yes |
| Referral Marketing Club (Ken Hardison) | Video | `ReferralMarketingClub_Q4` | Yes |
| PreLitGuru Sessions | YouTube | `PreLitGuru_Sessions` | **Removed** (session 12) |

**New sources (Phase 9 — ingested via auto_refresh.py):**

| Source | Type | Pinecone source name | Episodes | Status |
|--------|------|---------------------|----------|--------|
| PI Wingman (Cases On Demand) | YouTube Channel | `PIWingman` | 37 | **Ingested** ✓ |
| Grey Smoke Media | YouTube Channel | `GreySmokeMedia` | 145 | **Ingested** ✓ |
| Championing Justice (Champion Firm) | YouTube Playlist | `ChampioningJustice` | 29 | **Ingested** ✓ |
| PI Playbook by Xcelerator | YouTube Playlist | `PIPlaybook` | 38 | **Ingested** ✓ |
| ExtroMarketing | YouTube Channel | `ExtroMarketing` | 13 | **Ingested** ✓ |

**Going-forward-only sources (back catalogs intentionally skipped — only new uploads from May 4, 2026 onward will be ingested):**

| Source | Type | Pinecone source name | Known IDs | Notes |
|--------|------|---------------------|-----------|-------|
| WEBRIS: Legal Marketing | YouTube Channel | `WEBRIS` | 211 | Back catalog skipped to avoid ~$3 spend |
| Juris Digital | YouTube Channel | `JurisDigital` | 1,145 | Back catalog skipped to avoid ~$17 spend |
| Personal Injury Mastermind (Chris Dreyer) | YouTube Channel | `PIMPodcast` | 1,559 | Back catalog already in Pinecone as `PIM_Podcast_Season1/2/3` (from local m4a ingestion) |
| Tip the Scales (Bob Simon) | YouTube Channel | `TipTheScalesYT` | 752 | Back catalog already in Pinecone as `TipTheScales` (from local m4a ingestion) |
| Grow Law Podcast | YouTube Playlist | `GrowLawPodcast` | — | Disabled — duplicate of Grow Your Law Firm |

**Auto-refresh schedule:** Weekly via GitHub Actions (`.github/workflows/auto-refresh.yml`). Fires every Sunday at 3 AM UTC (Saturday 10 PM CT). Cron commits updated `sources_registry.json`, `takeaways_index.json`, `refresh_log.json`, and new `output/<source>.json` files back to the repo; Railway auto-redeploys with fresh data.

---

## How to Run

### Chatbot (main app — Flask)
```bash
pip install -r requirements.txt
python server.py
# Open http://127.0.0.1:8080
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

- **May 4, 2026 (session 16):** Phase 9 weekly cron is now LIVE + 4 new sources added to monitoring. Pushed `.github/workflows/auto-refresh.yml` to GitHub (was previously committed but never pushed). Installed GitHub CLI via winget, authenticated, configured 5 repository secrets (debugged a leading-`=` paste error across all keys), verified end-to-end with a manual `gh workflow run` (run reached Pinecone init successfully, then cancelled before Juris Digital backlog ingestion). Added Personal Injury Mastermind / Chris Dreyer (`UC0Sn0QLAUhKD8l3w98LBJ_A`, 1,559 IDs) and Tip the Scales Podcast (`UC1Crd3dEEToLsnP_UOW5fAA`, 752 IDs) to `sources_registry.json` with all current video IDs pre-loaded ("going-forward only" approach). Pre-filled Juris Digital (1,145 IDs) and WEBRIS (211 IDs) the same way to prevent the cron from spending ~$30 on back-catalog ingestion. Updated `entity_mappings.json` so PIM/Chris Dreyer queries route to both old (`PIM_Podcast_Season1/2/3`) and new (`PIMPodcast`) source names; same pattern for Tip the Scales. Added `PIMPodcast` and `TipTheScalesYT` display names to `rag.py`. Total monitored sources: 11 with 4,127 known IDs. Cron fires next at Sun May 10 3 AM UTC. Outstanding: rotate exposed Anthropic API key, backfill ~12 existing sources (CEO Lawyer, John Morgan, Maximum Lawyer, etc.) into registry.
- **Mar 23, 2026 (session 15):** Grey Smoke Media + PI Wingman ingestion — Ingested 145 Grey Smoke Media episodes (143 takeaways) and 37 PI Wingman episodes (35 takeaways) via `auto_refresh.py --source`. Backfilled 8 Grey Smoke Media episodes that failed during initial run using `extract_takeaways.py`. Both committed and deployed to Railway. Total: 1,442 episodes, 5,634 topics, 38 sources. WEBRIS and Juris Digital remain paused. Phase 9 auto-refresh pipeline now 5 of 8 new sources complete.
- **Feb 22, 2026 (session 14):** Auto-refresh pipeline implementation + initial ingestion — Built `auto_refresh.py` (single-source and full pipeline modes), `sources_registry.json` (10 monitored sources with known_video_ids), Dashboard "Refresh Now" button (`/api/refresh`), and notification banner. Ingested 5 initial sources: Championing Justice (29 eps), PI Playbook (38 eps), ExtroMarketing (13 eps), plus updates to Bourbon of Proof and Grow Your Law Firm. Added 8 new source configs to registry.
- **Feb 22, 2026 (session 13):** Production deployment verified + Auto-Refresh Pipeline design — Confirmed Dashboard Command Center is live on `gofflawsuperagent.up.railway.app` (health check passing, stats API returning 1,167 episodes / 30 sources / 4,952 topics, news ticker loading). Designed Phase 9 Auto-Refresh Pipeline: weekly Railway cron + Dashboard "Refresh Now" button, dashboard banner notifications. Finalized 20 monitored sources (12 existing + 8 new). New sources: PI Wingman (36 vids), Grey Smoke Media (150 vids), Juris Digital (1,054 vids), Grow Law Podcast (137 vids), Championing Justice (29 vids), PI Playbook by Xcelerator (38 vids), ExtroMarketing (14 vids), WEBRIS Legal Marketing (204 vids). Removed Pre-Lit Guru (deprioritized) and rejected Andy Stickel/Bill Hauser (2,173 vids — too expensive). No code written this session — design/planning only.
- **Feb 19-20, 2026 (session 12):** Dashboard Command Center UI — Built a two-view Marketing Command Center (Dashboard + Chat) replacing the old Streamlit-only interface. Dashboard features: stats cards (episodes, sources, topics, conversations), 6 quick-action prompt cards for Chelsea (Weekly Briefing, Content Calendar, Competitive Intel, Intake Optimization, SEO Strategy, Draft SOP). Added PI/mass tort news ticker in sidebar pulling from Google News RSS and Reddit, cached for 30 minutes. New API endpoints: `/api/stats` (knowledge base metrics from takeaways_index.json) and `/api/news` (aggregated news feed). Tab navigation switches between Dashboard and Chat views (SPA-style, no page reloads). Conversations list shows in sidebar only when in Chat view. Added `feedparser==6.0.12` dependency. Fixed UTF-8 encoding bug in `rag.py` for takeaways_index.json. Completed takeaways extraction: 871 → 1,167 episodes (Phase 7.2 complete). Design doc: `docs/plans/2026-02-19-dashboard-command-center-design.md`.
- **Feb 10, 2026 (session 11):** Phase 7.2 Takeaways Integration — Injected takeaways into chatbot context: added startup loading of `takeaways_index.json` with dual lookup structures (`TAKEAWAYS_BY_SOURCE_TITLE` for episode matching, `TAKEAWAYS_BY_TOPIC` for keyword matching). Built `get_relevant_takeaways()` with two strategies: (1) episode-matched via Pinecone chunk metadata, (2) topic-matched via query keyword scan against inverted index. Added `format_takeaways_for_prompt()` to inject up to 5 episode takeaways (~600-1,200 tokens) into each query. Updated `build_prompt()` and system prompt HOW TO WORK section. Kicked off full extraction run — processing all remaining episodes across 32 JSON files. Extraction is resume-safe (saves after each episode). Progress: 246+ episodes extracted and growing (up from 41). Extraction still running for large files (Grow Your Law Firm ~445 eps, PIM Podcast ~339 eps).
- **Feb 8, 2026 (session 10):** Phase 2 Complete + Phase 7 Started — Finished Phase 2 (Retrieval Quality): documented final parameter values (TOP_K=25, RERANK_TOP_K=10, MIN_SCORE_THRESHOLD=0.3) based on eval results (6/6 source accuracy, 4/4 off-topic filtering, 0 false positives). Started Phase 7 (Super Agent): created `goff_law_profile.json` with firm-specific context (Goff Law, Dallas, DFW market, practice areas, team info for Jim and Chelsea). Updated system prompt in `chat_app_with_history.py` to inject firm profile dynamically. Built key takeaways extraction pipeline (`extract_takeaways.py`) that uses Claude to extract structured metadata from episodes: key takeaways, subject area, topics, unique insights, action items, notable quotes. Tested on 41 episodes from Bourbon of Proof — all extracted successfully. Takeaways searchable via CLI (`--search`, `--category`, `--summary`). Stored in `takeaways_index.json`.
- **Feb 7, 2026 (session 9):** Railway deployment complete + content expansion — Super Agent Marketing Director is now live at `https://gofflawsuperagent.up.railway.app/`. Fixed environment variable typo (ANTHR0PIC_API_KEY → ANTHROPIC_API_KEY). Verified full functionality: streaming SSE, RAG pipeline (Pinecone → Cohere → Claude), PostgreSQL conversation history. Phase 5.7 (Hosting Migration) marked complete. Also processed remaining audio/video: 24 new Tip the Scales episodes (103-151, 1,308 chunks) and Referral Marketing Club Q4 session (23 chunks). Pinecone now at 14,103 vectors. Updated entity mappings for new sources.
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
├── server.py                     # Flask web app (Dashboard + Chat API)
├── rag.py                        # RAG pipeline (search, rerank, prompt, stream)
├── templates/index.html          # HTML template (Dashboard + Chat views)
├── static/style.css              # CSS (Apple-inspired, responsive)
├── static/app.js                 # Client-side JS (views, stats, news, chat)
├── chat_app_with_history.py      # Legacy Streamlit chatbot (deprecated)
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
├── goff_law_profile.json         # Firm-specific context for Super Agent (Phase 7)
├── extract_takeaways.py          # Episode takeaways extraction pipeline (Phase 7)
├── takeaways_index.json          # Structured takeaways index (1,442 episodes)
├── auto_refresh.py               # Auto-refresh pipeline (Phase 9)
├── sources_registry.json         # Source registry with known video IDs
├── .github/workflows/auto-refresh.yml  # Weekly cron (GitHub Actions, Sun 3 AM UTC)
├── DOCUMENTATION.md              # Technical reference (extraction APIs & models)
├── docs/plans/                   # Design documents
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
