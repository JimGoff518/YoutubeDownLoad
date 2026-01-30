# Bill AI Machine - Project Status

**Last updated:** January 30, 2026
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

Entity mappings are configured in `entity_mappings.json`:

| Source | Pinecone source name |
|--------|---------------------|
| Grow Your Law Firm Podcast (Ken Hardison) | `grow_your_law_firm` |
| Bourbon of Proof Podcast (Bob Simon) | `bourbon_of_proof` |
| John Morgan / Morgan & Morgan | `john_morgan` |
| Grey Sky Media Podcast | `grey_sky_media` |

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
├── chat_app_with_history.py      # Main RAG chatbot (Streamlit)
├── chat_app.py                   # Basic chatbot (no history)
├── database.py                   # Conversation persistence
├── ingest_to_pinecone.py         # Transcript → Pinecone pipeline
├── entity_mappings.json          # Query expansion & source filter config
├── PROJECT_STATUS.md             # Current system status & architecture
├── ROADMAP.md                    # Phased feature roadmap
├── eval_retrieval.py             # Retrieval quality evaluation script
├── test_questions.json           # 25 test queries for eval framework
├── eval_results.json             # Latest eval run output
├── DOCUMENTATION.md              # Technical reference (extraction APIs & models)
├── server.py                     # Flask file server
├── Dockerfile                    # Container definition
├── start.sh                      # Container startup
├── requirements.txt              # Python dependencies
├── .env                          # API keys (not committed)
├── output/                       # Extracted JSON files
└── .devcontainer/                # GitHub Codespaces config
```
