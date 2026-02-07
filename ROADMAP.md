# Bill AI Machine - Feature Roadmap

**Owner:** Goff Law (Dallas, TX)
**Primary Users:** Jim (firm owner, strategic direction) and Chelsea (COO, executes marketing strategy)
**Core Purpose:** AI-powered Director of Marketing ("Super Agent") for PI law firm strategy, built from YouTube and podcast content from top legal industry voices.

---

## Super Agent Vision

**A full-time AI marketing executive that knows everything the top PI minds know — and stays current.**

Because Super Agent is built on YouTube and podcast content, it has access to the most current thinking in PI marketing. This industry changes constantly — AI, search engines, LLMs, consolidation, emerging torts, technology, market competition, price per case, tort reform, private equity — and the experts discuss these shifts on their shows in near real-time. Super Agent absorbs all of it.

**The goal is for Goff Law to be ahead of the curve.** Super Agent gives COO Chelsea (and Jim) the latest trends, reports, checklists, and strategy to implement at the firm — synthesized from 15+ industry voices, filtered through Goff Law's specific situation.

### What Super Agent does at maturity:
1. **Knows everything the top PI marketing minds know** — Ken Hardison, Bob Simon, John Morgan, Mike Morse, Ali Awad, and more. Continuously updated as new episodes drop.
2. **Thinks like a marketing executive** — synthesizes across sources, connects insights to Goff Law's market, gives actionable strategy (not just search results).
3. **Proactively surfaces intelligence** — weekly briefings, trending topics, competitive intel, content calendar ideas. Doesn't wait to be asked.
4. **Produces deliverables** — SOPs, checklists, infographics, social media content, strategy docs. Things Chelsea can hand to the team on Monday.
5. **Stays current** — the real-time knowledge advantage. Podcasts and YouTube are the fastest-moving source of PI marketing intelligence. Super Agent is always up to date.
6. **Gets smarter over time** — remembers preferences, past decisions, what worked. Tracks its own quality and improves.
7. **Is secure and reliable** — auth, audit logging, backups.

---

## Phase 1: Foundation (Complete)

**Objective:** Build the end-to-end pipeline — extract content from YouTube and podcasts, store it in a vector database, and query it through a conversational AI chatbot.

- [x] YouTube channel/video/playlist transcript extraction
- [x] Podcast RSS feed extraction with Whisper fallback
- [x] Pinecone vector ingestion (chunking, embedding, upload)
- [x] RAG chatbot with Claude (Streamlit UI)
- [x] Conversation history with PostgreSQL/SQLite
- [x] Streaming responses
- [x] Retry logic and caching
- [x] Docker/Railway deployment
- [x] Flask file server for JSON downloads

### Testing & Validation (Phase 1) — Reference

These are the checks that confirmed Phase 1 was complete. Keep them here for regression testing.

**Automated:**
- [ ] `python -m src.main extract --channel-id <test_channel> --max-videos 5` completes without errors
- [ ] `python -m src.main podcast --rss-url <test_feed> --max-episodes 3` completes without errors
- [ ] `python -m src.main validate output/<file>.json` passes validation
- [ ] `python ingest_to_pinecone.py` runs against a test JSON file and upserts vectors to Pinecone
- [ ] Streamlit app starts without errors: `streamlit run chat_app_with_history.py`
- [ ] Database tables are created on first run (check `conversations` and `messages` tables exist)

**Manual:**
- [ ] Ask the chatbot a question — confirm it returns a relevant answer with sources
- [ ] Ask a follow-up question — confirm conversation history is maintained
- [ ] Check the sidebar — confirm past conversations are listed and clickable
- [ ] Delete a conversation from the sidebar — confirm it's removed
- [ ] Verify streaming — response should appear word-by-word, not all at once
- [ ] Deploy to Railway — confirm the app is accessible at the production URL
- [ ] Download a JSON file from the Flask server — confirm it's valid JSON

---

## Phase 2: Retrieval Quality (In Progress)

**Objective:** Make the chatbot significantly better at finding the *right* content. Reduce irrelevant results, improve ranking, and enable source-specific queries. Establish a baseline for measuring retrieval quality going forward.

### 2.1 Core Retrieval Improvements (Done)

- [x] Score threshold filtering (drop irrelevant chunks)
  - `MIN_SCORE_THRESHOLD = 0.3` in `chat_app_with_history.py`
- [x] Cohere reranking (reorder results by true relevance)
  - Model: `rerank-v3.5`, keeps top 10 after reranking
- [x] Source-specific metadata filtering (better results when asking about a specific show/host)
  - Dual search: unfiltered + source-filtered, results merged and deduplicated
- [x] Externalized entity mappings (JSON config instead of hardcoded)
  - `entity_mappings.json` with `query_expansion` and `source_filters` sections

### 2.2 Threshold & Parameter Tuning

- [x] **Create a test question set** — 25 queries in `test_questions.json` covering general strategy, source-specific, niche, off-topic, and drafting categories
- [x] **Run the test set and record results** — `eval_retrieval.py` runs full pipeline and outputs `eval_results.json` with per-query metrics
- [x] **Fix source filter mismatch** — Updated `entity_mappings.json` to use actual Pinecone source values (lists), changed `$eq` to `$in` filter, `detect_source_filter()` now returns list. Source accuracy: 6/6
- [ ] **Tune `MIN_SCORE_THRESHOLD`** — Experiment with values between 0.2–0.5
  - Current value 0.3 correctly filters all 4 off-topic queries while keeping all on-topic results
  - File: `chat_app_with_history.py:45`
- [ ] **Tune `TOP_K` (retrieval)** — Experiment with values between 15–40
  - Goal: Fetch enough candidates for reranking without overwhelming it
  - File: `chat_app_with_history.py:43`
- [ ] **Tune `RERANK_TOP_K`** — Experiment with values between 5–15
  - Goal: Keep only the most relevant chunks for the LLM context
  - File: `chat_app_with_history.py:44`
- [ ] **Document final parameter values** — Record what you settled on and why in this file

### 2.3 Retrieval Logging & Metrics

- [x] **Add per-query logging** — JSONL logging in `search_knowledge_base()` via `log_retrieval_metrics()`, writes to `retrieval_log.jsonl` with thread-safe locking
- [x] **Choose a logging destination** — Local JSONL file (`retrieval_log.jsonl`)
- [x] **Add a "no results" handler** — Improved message with suggestions (rephrase, ask about specific source, broaden topic)
- [ ] **Review logs after 1–2 weeks of usage** — Look for:
  - Queries with zero results after filtering (threshold too aggressive?)
  - Queries with many low-score results (content gap?)
  - Source-filtered queries returning poor results (entity mapping incomplete?)

### Testing & Validation (Phase 2)

**Automated:**
- [x] Run the 25-query test set — all on-topic queries return relevant results, all off-topic queries return nothing
- [x] Confirm score threshold filtering is working: 4/4 off-topic queries correctly filtered, 0 false positives
- [x] Confirm source filtering: 6/6 source-specific queries return results from correct source
- [ ] Confirm reranking: compare answer quality with reranking enabled vs. disabled for 5 queries
- [x] Verify logging output is being written (`retrieval_log.jsonl`)

**Manual:**
- [ ] Ask 10 real questions you'd actually ask the tool — rate each answer as good/partial/bad
  - Target: 80%+ rated "good"
- [ ] Ask 3 source-specific questions — verify the right source is prioritized
- [ ] Ask 2 questions about topics NOT in the knowledge base — verify the bot doesn't hallucinate
- [ ] Review the retrieval log — confirm all fields are populated and make sense
- [ ] Compare answers before and after tuning — confirm improvement on at least 3 queries

---

## Phase 3: Knowledge Base Expansion

**Objective:** Broaden the knowledge base from the initial 4 sources to cover the major PI thought leaders, podcasts, and YouTube channels. Establish a repeatable ingestion workflow and track what's been ingested.

### 3.1 Source Discovery & Prioritization

- [ ] **Research and list target YouTube channels** — Identify 10–15 PI law firm marketing, trial strategy, and legal industry channels. For each, record:
  - Channel name, URL, channel ID
  - Approximate video count
  - Relevance (high / medium / low)
  - Priority order for ingestion
- [ ] **Research and list target podcasts** — Identify 10–15 top PI industry podcasts. For each, record:
  - Podcast name, RSS feed URL
  - Approximate episode count
  - Relevance and priority
- [ ] **Create a source tracking document** — A table or spreadsheet listing every source with:
  - Name, type (YouTube/podcast), URL
  - Status: not started / in progress / ingested / failed
  - Date ingested, number of episodes/videos, chunk count
  - Notes (any issues encountered)

### 3.1.1 New Content Type Pipelines (Session 7 — Complete)

- [x] **PDF ingestion pipeline** — `extract_pdf.py` extracts text via pdfplumber, outputs ingestion-compatible JSON
- [x] **Web article ingestion pipeline** — `extract_web_article.py` fetches/parses articles via BeautifulSoup
- [x] **Magazine article classifier** — `extract_trial_lawyer.py` uses Claude to identify marketing-relevant articles in magazine PDFs (score 1-5, ingest 3+)
- [x] **YouTube extraction wrapper** — `extract_youtube.py` bypasses Rich Unicode bug on Windows
- [x] **Batch ingestion of 14 new sources** — 3 YouTube videos, 2 industry PDFs, 1 web article, 8 Trial Lawyer magazine issues (238 chunks, 10,355 total vectors)

### 3.2 Batch Ingestion of New YouTube Channels

- [ ] **Ingest each new YouTube channel** — For each prioritized channel:
  - Run `python -m src.main extract --channel-id <id> --max-videos <n>`
  - Validate output: `python -m src.main validate output/<file>.json`
  - Run `python ingest_to_pinecone.py` for the new JSON file
  - Update `entity_mappings.json` with new source keywords and filters
  - Update source tracking document
- [ ] **Verify each channel's content is searchable** — After ingestion, ask the chatbot a question specific to that channel's content

### 3.3 Batch Ingestion of New Podcasts

- [ ] **Ingest each new podcast** — For each prioritized podcast:
  - Run `python -m src.main podcast --rss-url <url> --max-episodes <n>`
  - Validate output
  - Ingest to Pinecone
  - Update `entity_mappings.json`
  - Update source tracking document
- [ ] **Verify each podcast's content is searchable**

### 3.4 Entity Mappings Expansion

- [ ] **Add query expansion entries** for every new source — Map host names, show names, and common abbreviations to each other in `entity_mappings.json`
- [ ] **Add source filter entries** for every new source — Map keywords to the Pinecone `source` metadata value
- [ ] **Test entity mappings** — For each new source, ask a question mentioning the host/show name and verify source filtering activates

### 3.5 Ingestion Dashboard / Log

- [ ] **Create an ingestion tracking file or database table** — Track:
  - Source name, type, URL
  - Date of last ingestion
  - Total episodes/videos ingested
  - Total chunks in Pinecone for this source
  - Any errors or skipped episodes
- [ ] **Add a summary command or script** that prints ingestion status for all sources
- [ ] **Document the ingestion workflow** — Step-by-step instructions so you can repeat this process for any new source

### 3.6 CLE / Training Recordings (Optional)

- [ ] **Identify CLE recordings or training videos** available for ingestion
- [ ] **Determine format** — Are these YouTube videos, audio files, or something else?
- [ ] **Ingest using the appropriate pipeline** (YouTube extraction or podcast/Whisper pipeline)

### Testing & Validation (Phase 3)

**Automated:**
- [ ] Run `python -m src.main validate` on every new JSON output file — all pass
- [ ] Run a Pinecone index stats query — confirm chunk count increased by the expected amount
- [ ] Run the Phase 2 test question set again — confirm no regression (existing answers still good)
- [ ] Run 5 new questions targeting newly ingested sources — confirm relevant answers

**Manual:**
- [ ] For each new source, ask 2–3 questions specific to that source's content — confirm relevant answers
- [ ] Ask a cross-source question ("What do the top PI marketers say about intake?") — confirm the answer draws from multiple sources
- [ ] Verify entity mappings: ask a question mentioning each new host/show name — confirm source filtering activates
- [ ] Review source tracking document — confirm all sources are accounted for with correct status
- [ ] Spot-check 3 random episodes from new sources in Pinecone — verify chunks have correct metadata (source, episode_title, chunk_index)

---

## Phase 4: Industry Trend Intelligence

**Objective:** Move beyond Q&A into proactive intelligence. Surface recurring themes, track how topics evolve over time, and alert when new topics emerge across the knowledge base.

### 4.1 Data Foundation for Trends

- [ ] **Add `published_at` to Pinecone metadata** — During ingestion, include the episode/video publish date in chunk metadata so trend queries can filter by time range
  - File: `ingest_to_pinecone.py` — update metadata dict in `process_transcript_file()`
  - Requires re-ingestion of existing content (or a backfill script)
- [ ] **Add `topics` to Pinecone metadata (optional)** — Auto-tag each chunk with 2–5 topic labels using an LLM classification step during ingestion
  - This is optional but makes trend queries much faster
  - Trade-off: adds cost per chunk (one LLM call per chunk for tagging)
- [ ] **Backfill existing data** — Re-ingest existing sources with the new metadata fields, or write a script to update metadata in place

### 4.2 Trend Detection

- [ ] **Build a topic extraction pipeline** — Given a time range (e.g., last 30 days), pull all chunks published in that window and use an LLM to identify the top recurring topics
  - Input: chunks from Pinecone filtered by `published_at`
  - Output: list of topics with frequency counts and representative quotes
- [ ] **Build a topic frequency tracker** — For a given topic (e.g., "mass torts"), count how many chunks mention it per month over the full dataset
  - Output: time series data (month → count)
  - Visualization: simple chart in Streamlit or a data export

### 4.3 Expert Opinion Summaries

- [ ] **Build a "what are experts saying about X?" query mode** — Given a topic and optional time range:
  - Search Pinecone for chunks matching the topic
  - Group results by source (so each expert's view is separate)
  - Use Claude to summarize each expert's position
  - Output: structured summary with expert name, key points, and source citations

### 4.4 New Topic Alerts

- [ ] **Build a "new topics" detection script** — Compare topics from the most recent ingestion batch against all previously seen topics
  - Flag any topic that appears for the first time
  - Output: list of new topics with the episodes they appeared in
- [ ] **Define a notification mechanism** — How should you be alerted? Options:
  - A section in the Streamlit UI ("New topics this week")
  - An email or Slack notification
  - A log file

### 4.5 Timeline View

- [ ] **Build a topic timeline** — For a set of key topics, show when they were discussed and by whom
  - X-axis: time (months)
  - Y-axis: topic mentions, colored by source
  - Implementation: Streamlit chart component or a static report

### 4.6 Trend Query Mode in Chatbot

- [ ] **Add a trend-aware mode to the chatbot** — Detect when the user is asking a trend question (e.g., "What's the latest thinking on...?" or "What trends are emerging in...?")
  - Use time-filtered Pinecone queries to prioritize recent content
  - Adjust the system prompt to encourage trend-style answers
  - File: `chat_app_with_history.py` — add trend detection logic and alternate prompt

### Testing & Validation (Phase 4)

**Automated:**
- [ ] Verify `published_at` is present in Pinecone metadata for newly ingested chunks
- [ ] Run the topic extraction pipeline on a known time range — confirm it returns plausible topics
- [ ] Run the frequency tracker for "mass torts" — confirm it returns non-zero counts for months where that topic is discussed
- [ ] Run the "new topics" script after ingesting a fresh batch — confirm it identifies at least one new topic

**Manual:**
- [ ] Ask "What are experts saying about intake optimization?" — confirm the answer groups insights by expert/source
- [ ] Ask "What trends are emerging in PI marketing?" — confirm the answer references recent content and identifies trends
- [ ] Review the topic timeline for 3 key topics — confirm the data looks plausible
- [ ] Trigger a new topic alert by ingesting an episode on a novel subject — confirm the alert fires
- [ ] Compare a trend query answer to a regular Q&A answer on the same topic — confirm the trend answer is more time-aware

---

## Phase 5: Content & Workflow Improvements

**Objective:** Polish the daily chatbot experience. Make it easier to trace answers back to original sources, find past conversations, and reuse common queries.

### 5.1 Source Citations in Responses

- [ ] **Add inline source citations** — Modify the Claude prompt to instruct it to cite sources using numbered references (e.g., [1], [2])
  - File: `chat_app_with_history.py` — update the system prompt and context formatting
- [ ] **Add a sources footer** — Below each response, list the cited sources with episode title, source name, and chunk score
  - Currently shows top 5 sources; enhance with more detail
- [ ] **Deduplicate sources** — If multiple chunks come from the same episode, list that episode once

### 5.2 Clickable Links to Original Content

- [ ] **Store source URLs in Pinecone metadata** — During ingestion, include the YouTube video URL or podcast episode URL in chunk metadata
  - File: `ingest_to_pinecone.py` — add `source_url` to metadata dict
  - For YouTube: `https://youtube.com/watch?v=<video_id>`
  - For podcasts: episode URL from RSS feed (if available)
- [ ] **Backfill existing data** with source URLs (re-ingest or update script)
- [ ] **Display clickable links** in the Streamlit sources footer
  - File: `chat_app_with_history.py` — render URLs as markdown links in the sources section

### 5.3 Conversation Search

- [ ] **Add a search box to the conversation sidebar** — Filter past conversations by keyword
  - Search across conversation titles and message content
  - File: `chat_app_with_history.py` — add `st.text_input` to sidebar, filter conversation list
  - File: `database.py` — add a `search_conversations(keyword)` function using SQL `LIKE` or full-text search

### 5.4 Conversation Export

- [ ] **Add an export button** to each conversation — Download as plain text or PDF
  - Text export: concatenate all messages with role labels and timestamps
  - PDF export (optional): use a library like `fpdf2` or `reportlab`
  - File: `chat_app_with_history.py` — add `st.download_button` with formatted content

### 5.5 Saved Prompts / Templates

- [ ] **Create a prompt library** — Predefined queries stored in a JSON file or database table
  - Examples: "What are the top 5 strategies for increasing PI case volume?", "Summarize the latest episode of [show]"
- [ ] **Add a prompt selector to the UI** — Dropdown or button group to insert a saved prompt into the chat input
  - File: `chat_app_with_history.py` — add `st.selectbox` or button group above the chat input
- [ ] **Allow adding/editing saved prompts** — Simple UI to manage the prompt library

### 5.6 Mobile Experience

- [ ] **Test on mobile devices** — Open the Streamlit app on a phone and note layout issues
- [ ] **Fix layout issues** — Common Streamlit mobile fixes:
  - Reduce sidebar width or make it collapsible
  - Ensure chat messages don't overflow
  - Make buttons and inputs touch-friendly
  - File: `chat_app_with_history.py` — add custom CSS via `st.markdown` with `unsafe_allow_html=True`

### Testing & Validation (Phase 5)

**Automated:**
- [ ] Verify source citations appear in responses — ask 5 questions and confirm each response includes numbered citations
- [ ] Verify clickable links — ask a question and confirm the sources footer contains valid URLs
- [ ] Verify conversation search — create 3 conversations with known keywords, search for each keyword, confirm correct conversations appear
- [ ] Verify export — export a conversation as text, open the file, confirm content is complete and formatted

**Manual:**
- [ ] Ask a question and click a source link — confirm it opens the correct YouTube video or podcast episode
- [ ] Search for a past conversation by keyword — confirm it's found quickly
- [ ] Export a long conversation (10+ messages) — confirm the export is readable and complete
- [ ] Use a saved prompt — confirm it populates the chat input correctly
- [ ] Open the app on a mobile phone — confirm the layout is usable (no overlapping elements, text is readable, buttons are tappable)
- [ ] Test on both iOS Safari and Android Chrome

---

## Phase 5.7: Hosting Migration (Urgent)

**Objective:** Get the Streamlit app back online after Streamlit Community Cloud suspension. Find reliable paid hosting.

- [ ] **Evaluate hosting options** — Railway (~$5-20/mo), Render, AWS Free Tier, fly.io. Key criteria: easy deploy, custom domain, persistent DB, reasonable cost.
- [ ] **Set up new hosting** — Deploy the Streamlit app + PostgreSQL conversation DB to chosen platform
- [ ] **Verify full functionality** — Chat, conversation history, source filtering, streaming all work on new host
- [ ] **Update DNS / share new URL** — Point any bookmarks or links to the new deployment
- [ ] **Update Dockerfile / start.sh if needed** — Adapt deployment config for the new platform
- [ ] **Document the new hosting setup** — Update PROJECT_STATUS.md and README.md with new deploy instructions

---

## Phase 6: Data Quality & Operations

**Objective:** Keep the system healthy, reliable, and cost-effective as the dataset grows. Prevent duplicate content, monitor costs, and establish a backup strategy.

### 6.1 Ingestion Monitoring

- [ ] **Track ingestion metrics** — After each ingestion run, log:
  - Source name, date, episodes/videos processed
  - Chunks created, chunks upserted to Pinecone
  - Embedding cost (tokens used × price per token)
  - Errors and skipped items
  - File: `ingest_to_pinecone.py` — add summary logging at end of ingestion
- [ ] **Create an ingestion history log** — Append to `ingestion_log.jsonl` or a database table after each run
- [ ] **Build a simple dashboard or report** — Script that reads the ingestion log and prints:
  - Total chunks in Pinecone (by source)
  - Last ingestion date per source
  - Error rate per source

### 6.2 Duplicate Detection

- [ ] **Detect duplicates before ingestion** — Before upserting a chunk, check if its ID already exists in Pinecone
  - Current ID strategy (MD5 of source:title:chunk_index) already prevents exact duplicates
  - Add a check for near-duplicate episodes (same title, different source name due to typo)
  - File: `ingest_to_pinecone.py` — add pre-check logic
- [ ] **Log duplicates** — When a duplicate is detected, log it rather than silently skipping
- [ ] **Handle re-ingestion gracefully** — If you re-run ingestion for a source, existing vectors should be overwritten (not duplicated). Verify this works correctly.

### 6.3 Stale Content Cleanup

- [ ] **Define "stale"** — What makes content stale? Options:
  - Published more than N years ago
  - From a source that no longer publishes
  - Superseded by newer content on the same topic
- [ ] **Build a stale content report** — Query Pinecone for chunks older than the stale threshold and list them
- [ ] **Build a cleanup script** — Delete stale chunks from Pinecone by ID
  - Include a dry-run mode that lists what would be deleted without actually deleting

### 6.4 Backup Strategy

- [ ] **Pinecone index backup** — Options:
  - Export all vectors to a local file (Pinecone collections or custom export script)
  - Keep the extraction JSON files as the source of truth (can always re-ingest)
  - Document which approach you're using
- [ ] **Conversation database backup** — Options:
  - For PostgreSQL (Railway): set up automated backups via Railway or `pg_dump` on a schedule
  - For SQLite: copy the `.db` file to a backup location
  - Document the backup frequency and retention policy
- [ ] **Test restore** — Actually restore from a backup to verify it works
  - Restore Pinecone from JSON files (re-ingest)
  - Restore conversations from database backup

### 6.5 Cost Tracking

- [ ] **Track API costs per service** — Monitor monthly spend on:
  - OpenAI (embeddings + Whisper transcription)
  - Anthropic (Claude chatbot responses)
  - Cohere (reranking)
  - Pinecone (index hosting + queries)
- [ ] **Create a cost log** — After each ingestion or monthly, log:
  - Tokens used per service
  - Estimated cost
  - File: create `cost_tracking.jsonl` or a database table
- [ ] **Set up billing alerts** — Configure alerts on each API provider's dashboard for unexpected spikes
- [ ] **Identify cost optimization opportunities** — Review:
  - Are there cheaper embedding models that maintain quality?
  - Can you cache more aggressively to reduce API calls?
  - Is the chunk size optimal for cost vs. quality?

### 6.6 Automated Tests

- [x] **Set up test infrastructure** — pytest, pytest-cov, pytest-mock in `requirements.txt`, `pytest.ini`, `tests/conftest.py` with shared fixtures
- [x] **Pydantic model tests** (18 tests) — Transcript, Video, Channel, Podcast models, computed fields, validation, serialization. File: `tests/test_models.py`
- [x] **Config & storage tests** (13 tests) — Env parsing, bool/language parsing, validation, JSON write/read/validate. Files: `tests/test_config.py`, `tests/test_json_writer.py`
- [x] **Database tests** (9 tests) — Full CRUD on conversations and messages using in-memory SQLite. File: `tests/test_database.py`
- [x] **Utility function tests** (18 tests) — chunk_text, generate_chunk_id, parse_duration, parse_pub_date, YouTube URL extractors (channel, video, playlist). File: `tests/test_utils.py`
- [x] **API client tests** (18 tests) — YouTubeClient, TranscriptFetcher, PodcastFetcher with mocked external APIs. Files: `tests/test_youtube_client.py`, `tests/test_transcript_fetcher.py`, `tests/test_podcast_fetcher.py`
- [x] **Processor & pipeline tests** (15 tests) — VideoProcessor ML features, video/channel processing, ingestion file parsing. Files: `tests/test_video_processor.py`, `tests/test_ingestion.py`
- [x] **Set up a test runner** — `pytest.ini` configured, run with `python -m pytest tests/ -v`
- [ ] **RAG pipeline tests** — Full query pipeline (embed → search → rerank → generate), source citations, off-topic filtering. File: create `tests/test_rag.py`
- [ ] **Add tests to CI** (optional) — Run tests on every commit via GitHub Actions

### Testing & Validation (Phase 6)

**Automated:**
- [x] Run `pytest tests/` — all 107 tests pass (0 failures)
- [ ] Run the ingestion pipeline on a test file — verify ingestion log is written with correct metrics
- [ ] Run duplicate detection — ingest the same file twice and verify no duplicate chunks in Pinecone
- [ ] Run the stale content report — verify it returns results for old content
- [ ] Run the cost tracking script — verify it outputs plausible cost estimates

**Manual:**
- [ ] Review the ingestion dashboard — confirm all sources are listed with correct stats
- [ ] Trigger a backup and restore cycle — verify data is intact after restore
- [ ] Review cost tracking for the past month — confirm costs are within expected range
- [ ] Review API billing dashboards — confirm they roughly match your cost log
- [ ] Run the stale content cleanup in dry-run mode — review the list and confirm it makes sense
- [ ] Run the full test suite on a clean environment (fresh clone, fresh DB) — confirm everything passes

---

## Phase 7: Super Agent — Director of Marketing

**Objective:** Evolve the system from a passive Q&A tool into an active "Director of Marketing" agent for Goff Law. The agent's sole mission: use all ingested data to continuously improve the firm's marketing — making it the best PI law firm marketing department in America.

### 7.1 Agent Persona & Goal Framework

- [ ] **Define the Super Agent persona** — The agent operates as the Director of Marketing for Goff Law (Dallas PI firm). Every analysis, recommendation, and insight is filtered through this lens: "How does this help Goff Law's marketing?"
- [ ] **Build a goal-oriented system prompt** — Replace the generic RAG prompt with a marketing director prompt that:
  - Knows the firm's identity, practice areas, market, and competitive position
  - Proactively connects podcast/YouTube insights to actionable marketing strategies
  - Thinks in terms of campaigns, channels, content strategy, and ROI
- [ ] **Create a firm profile config** — A JSON/YAML file with firm-specific context (name, location, practice areas, current marketing channels, goals) that gets injected into every agent interaction

### 7.2 Episode Key Takeaways Extraction

- [ ] **Build a key takeaways pipeline** — Process every episode/playlist/document and extract structured metadata:
  - Key takeaways (3–5 bullet points per episode)
  - Subject area (e.g., "intake optimization", "Google LSAs", "mass tort marketing")
  - Topics covered (tags)
  - Unique insights (things only this episode/source mentions)
  - Potential new ideas for the firm (actionable items)
- [ ] **Store takeaways in a structured format** — JSON file or database table, indexed by episode, searchable by topic/tag
- [ ] **Keep takeaways front-and-center** — The Super Agent should always have access to the full takeaways index when answering questions or making recommendations
- [ ] **Build a takeaways review UI** — Streamlit page or section to browse, search, and filter episode takeaways by topic, source, or date
- [ ] **Auto-generate takeaways on ingestion** — When new episodes are ingested, automatically run the takeaways extraction pipeline

### 7.3 Proactive Marketing Intelligence

- [ ] **Weekly briefing mode** — The agent generates a weekly marketing briefing summarizing new insights from recently ingested content, mapped to firm priorities
- [ ] **Competitive intelligence** — When experts discuss what top firms are doing, flag it as competitive intel with recommended actions
- [ ] **Content calendar suggestions** — Based on trending topics and expert advice, suggest content ideas for the firm's marketing channels

### Testing & Validation (Phase 7)

**Automated:**
- [ ] Run the key takeaways pipeline on 10 existing episodes — verify structured output is generated for each
- [ ] Verify the Super Agent prompt produces marketing-focused answers vs. generic answers for the same query
- [ ] Verify takeaways are searchable by topic and source

**Manual:**
- [ ] Ask "What should we do about our Google LSA strategy?" — confirm the answer is firm-specific, actionable, and cites relevant expert opinions
- [ ] Review takeaways for 5 episodes — confirm they capture the key points accurately
- [ ] Run a weekly briefing — confirm it surfaces relevant new insights and maps them to firm priorities

---

## Phase 8: Document Upload, Content Drafting & UI Overhaul

**Objective:** Expand the knowledge base beyond YouTube/podcasts by allowing direct document uploads, add content drafting capabilities (SOPs, checklists), and redesign the UI to be clean, professional, and polished — Apple-product quality.

### 8.1 Document Upload

- [ ] **Build a document upload UI** — Streamlit file uploader supporting PDF, DOCX, TXT, and markdown files
  - File: `chat_app_with_history.py` — add upload widget (sidebar or dedicated page)
- [ ] **Parse uploaded documents** — Extract text from each format:
  - PDF: use `pymupdf` or `pdfplumber`
  - DOCX: use `python-docx`
  - TXT/MD: read directly
- [ ] **Chunk and ingest uploaded documents** — Run the same chunking → embedding → Pinecone upsert pipeline used for transcripts
  - Reuse logic from `ingest_to_pinecone.py`
  - Tag with `source` metadata (e.g., filename or user-provided label)
- [ ] **Track uploaded documents** — Store upload metadata (filename, date, chunk count, source label) in the database or a tracking file
- [ ] **Allow deleting uploaded documents** — Remove all associated chunks from Pinecone by source filter

### 8.2 Content Drafting (SOPs & Checklists)

- [ ] **Add a drafting mode to the chatbot** — Detect or allow the user to select "draft" mode for generating structured content
- [ ] **SOP drafting** — Given a topic (e.g., "new client intake process"), generate a structured SOP using knowledge base content as reference
  - Numbered steps, responsible parties, expected outcomes
  - Cite relevant expert advice from the knowledge base
- [ ] **Checklist drafting** — Given a topic (e.g., "pre-trial preparation checklist"), generate an actionable checklist
  - Checkbox-style output, grouped by category
  - Pull best practices from ingested content
- [ ] **Export drafts** — Allow downloading drafted SOPs/checklists as DOCX, PDF, or plain text
- [ ] **Save drafts** — Store drafts in the conversation history or a separate drafts table for later editing

### 8.3 UI Overhaul — Professional Design

- [x] **Define the design system** — Clean, minimal aesthetic inspired by Apple products:
  - Muted color palette (whites, light grays, subtle accent color)
  - Consistent spacing and alignment
  - Professional typography (system fonts, clear hierarchy)
  - Crisp borders, no visual clutter
- [x] **Redesign the chat interface** — Clean message bubbles, clear user/assistant distinction, proper spacing
  - File: `chat_app_with_history.py` — custom CSS via `st.markdown` with `unsafe_allow_html=True`
- [x] **Redesign the sidebar** — Organized conversation list, clean navigation, collapsible sections
- [x] **Add a header/branding bar** — Firm name or tool name, minimal and professional
- [x] **Polish the sources section** — Clean card-style layout for cited sources instead of raw text
- [ ] **Responsive layout** — Ensure it looks good on desktop, tablet, and mobile
- [ ] **Loading states** — Elegant loading indicators instead of default Streamlit spinners
- [ ] **Dark mode support** (optional) — Toggle between light and dark themes

### Testing & Validation (Phase 8)

**Automated:**
- [ ] Upload a PDF, DOCX, and TXT file — verify each is parsed, chunked, and searchable in the chatbot
- [ ] Delete an uploaded document — verify its chunks are removed from Pinecone
- [ ] Generate an SOP and a checklist — verify structured output with citations
- [ ] Export a draft as DOCX — verify the file is valid and formatted

**Manual:**
- [ ] Upload a real firm document — ask a question about its content and verify relevant answers
- [ ] Draft an SOP for "new client intake" — review for completeness and usefulness
- [ ] Review the UI on desktop and mobile — confirm clean, professional appearance with no layout issues
- [ ] Compare before/after screenshots — confirm the redesign is a visible improvement
- [ ] Show the UI to a non-technical user — confirm it feels intuitive and polished

---

## Phase 9: Auto-Refresh Pipeline

**Objective:** Automate the ingestion of new content so Super Agent stays current without manual intervention. This is critical infrastructure for the "stays current" promise.

- [ ] **Automated monitoring** — Check YouTube channels and podcast RSS feeds for new episodes on a schedule (daily or weekly)
- [ ] **Auto-extract and ingest** — On detection of new content: extract transcript, chunk, embed, upsert to Pinecone
- [ ] **Auto-update entity mappings** — If a new source is added, prompt for entity mapping updates
- [ ] **Scheduling** — Cron job, task scheduler, or cloud-based scheduler to run checks automatically
- [ ] **Ingestion notifications** — Notify when new content is ingested ("3 new episodes ingested this week")
- [ ] **Error handling and retry** — Graceful handling of failed extractions/ingestions with retry logic
- [ ] **Ingestion log** — Append to `ingestion_log.jsonl` after each auto-run

### Testing & Validation (Phase 9)

**Automated:**
- [ ] Trigger the auto-refresh pipeline manually — confirm it detects a known new episode and ingests it
- [ ] Verify notification is sent after ingestion
- [ ] Verify ingestion log is updated

**Manual:**
- [ ] Let the pipeline run on schedule for one week — confirm new episodes are ingested without intervention
- [ ] Verify no duplicate ingestion of already-processed episodes

---

## Phase 10: Security

**Objective:** Lock down the application with authentication, audit logging, and hardened secrets management.

- [ ] **User authentication** — Add login/password for the Streamlit app (e.g., Streamlit Authenticator or custom auth)
- [ ] **Audit logging** — Track who accessed what, when (logins, queries, actions)
- [ ] **Review and harden secrets handling** — Ensure API keys are not exposed in logs, error messages, or client-side code

### Testing & Validation (Phase 10)

**Automated:**
- [ ] Verify unauthenticated users cannot access the app
- [ ] Verify audit log captures login events and queries

**Manual:**
- [ ] Attempt to access the app without credentials — confirm access is denied
- [ ] Review audit log after a day of usage — confirm all access is logged

---

## Phase 11: Memory Retention

**Objective:** Give Super Agent persistent memory across sessions so it remembers user preferences, past decisions, firm context, and strategic direction.

- [ ] **Cross-session memory store** — Database or file-based storage for agent memory (not just conversation history)
- [ ] **Preference tracking** — Remember user preferences (e.g., "Jim prefers bullet-point summaries," "Chelsea wants action items")
- [ ] **Decision history** — Track past strategic decisions and their outcomes (e.g., "Decided to focus on mass tort marketing in Q1")
- [ ] **Firm context persistence** — Maintain an evolving profile of Goff Law's current marketing state, priorities, and goals
- [ ] **Memory retrieval in prompts** — Inject relevant memories into the system prompt for each conversation

### Testing & Validation (Phase 11)

**Automated:**
- [ ] Set a preference in one conversation, start a new conversation — verify the agent remembers it
- [ ] Verify firm context is included in agent responses

**Manual:**
- [ ] Have a conversation about mass tort strategy, then in a new session ask "what did we decide about mass torts?" — confirm accurate recall

---

## Phase 12: Image Generation

**Objective:** Enable Super Agent to produce visual marketing assets from knowledge base content.

- [ ] **Image generation integration** — Connect to Banana Pro, Gemini, or equivalent image generation API
- [ ] **Infographics** — Generate visual summaries of key strategies (e.g., "5 Intake Optimization Tips from Top PI Firms")
- [ ] **Checklist graphics** — Shareable SOP visuals for staff
- [ ] **Social media graphics** — Key quotes and stats from the knowledge base, formatted for social channels
- [ ] **Presentation slides** — Strategy meeting-ready slides for internal use
- [ ] **Template system** — Reusable templates for each asset type with Goff Law branding

### Testing & Validation (Phase 12)

**Automated:**
- [ ] Generate an infographic from a known topic — verify image is produced and readable
- [ ] Generate a checklist graphic — verify formatting and content accuracy

**Manual:**
- [ ] Review 5 generated assets — rate each for visual quality and content accuracy
- [ ] Share a generated checklist with the team — confirm it's usable as-is

---

## Phase 13: Chelsea's Dashboard & Notifications

**Objective:** Build a task-oriented interface for Chelsea (COO) with push notifications, so she gets actionable intelligence without having to dig through chat.

- [ ] **Dashboard UI** — Streamlit page or separate app with:
  - "This week's briefing" — auto-generated summary of new insights from recently ingested content
  - "Pending action items" — recommendations from Super Agent awaiting implementation
  - "New content ingested" — what's new in the knowledge base
- [ ] **Push delivery** — Email digest or Slack notifications for weekly briefings, new trend alerts, and action items
- [ ] **Role-based views** — Jim sees strategic/vision content, Chelsea sees tactical/actionable content
- [ ] **Mobile-friendly** — Responsive design for on-the-go access

### Testing & Validation (Phase 13)

**Automated:**
- [ ] Verify dashboard loads with current week's briefing
- [ ] Verify email/Slack notification is delivered on schedule

**Manual:**
- [ ] Chelsea reviews the dashboard for one week — confirm it surfaces useful, actionable content
- [ ] Verify mobile layout is usable on phone

---

## Phase 14: Customer Satisfaction

**Objective:** Track and improve the quality of Super Agent's output over time through user feedback and quality metrics.

- [ ] **Per-response rating** — Thumbs up/down or 1-5 star rating on each agent response
- [ ] **Feedback storage** — Store ratings with query, response, and context for analysis
- [ ] **Quality metrics dashboard** — Track answer quality trends, identify weak areas
- [ ] **Knowledge gap identification** — Flag topics where responses consistently rate poorly (content gap in KB)
- [ ] **Improvement tracking** — Compare quality metrics month-over-month to verify the system is getting better

### Testing & Validation (Phase 14)

**Automated:**
- [ ] Verify rating widget appears on each response
- [ ] Verify ratings are stored and retrievable

**Manual:**
- [ ] Rate 20 responses over a week — review the quality dashboard and confirm trends are visible
- [ ] Identify one knowledge gap from low ratings — verify it corresponds to a real content gap

---

## Not Planned (Decided Against)

These were considered and explicitly excluded for now.

- ~~Client-facing chatbot~~ — This is a personal tool, not client-facing
- ~~Case research mode~~ — Not needed at this stage
- ~~Content planning mode~~ — Not needed at this stage
- ~~Client intake helper~~ — Not needed at this stage
- ~~Multi-user access~~ — Moved to Phase 10 (Security) and Phase 13 (Chelsea's Dashboard). Jim + Chelsea are key users.

---

## Under Consideration (Maybe / Someday)

Ideas that are interesting but not committed to. May move into a phase above if they prove valuable, or get dropped entirely.

### Additional Content Sources

| Idea | What it would involve | Why I'm unsure |
|------|----------------------|----------------|
| **Legal blogs & articles** | Web scraper to pull blog posts from top PI marketing sites, legal news outlets, thought leader blogs. Parse HTML → text → chunk → embed. | Need to figure out which sites matter most. Copyright/TOS questions. Keeping it fresh as new posts come out. |
| **Social media (LinkedIn, X)** | Ingest posts/threads from PI thought leaders. Would need API access or scraping. | Content is short-form and noisy. May not chunk well. API access can be expensive or restricted. Signal-to-noise ratio. |
| **Books / ebooks (PDF, epub)** | PDF/epub parser → text extraction → chunk → embed. PI marketing books, trial strategy guides. | OCR quality varies. Long-form content may need different chunking strategy. Licensing concerns for copyrighted books. |
| **Competitor firm websites** | Scrape practice area pages, attorney bios, blog posts, case results from other PI firms. | Ethical considerations. Content may be thin or boilerplate. Keeping scraped data current. |

### Feature Ideas

| Idea | What it would do | Why I'm unsure |
|------|-----------------|----------------|
| ~~**Auto-refresh pipeline**~~ | Moved to Phase 9 (committed). |  |
| **Topic tagging on ingestion** | Auto-tag each chunk with topics (e.g., "mass torts," "intake optimization," "Google LSAs") during ingestion so you can filter by topic in the chatbot. | Need a reliable tagging approach. Could use LLM classification but adds cost per chunk. |
| **Knowledge gap analysis** | Compare what's in the knowledge base against a list of important PI topics to identify what's NOT covered. | Requires defining the "ideal" topic list first. Unclear how to measure coverage meaningfully. |
| **Digest / summary reports** | Weekly or monthly summary of what's new in the knowledge base -- new episodes ingested, trending topics, notable insights. | Nice to have but unclear if the effort to build it is worth it at current scale. |

---

## How to Read This Document

- **Phases are sequential** — each builds on the previous, but individual items within a phase can be done in any order
- **[x] = done, [ ] = not started**
- **"Under Consideration"** items are not committed — they're here so they don't get lost
- **Every phase ends with a Testing & Validation gate** — complete all automated and manual tests before moving to the next phase
- **Update this document** as features are completed or priorities change
