"""RAG pipeline for Legal Knowledge Base - Super Agent Marketing Director.

Extracts all retrieval-augmented generation logic from chat_app_with_history.py
with zero Streamlit dependencies. Suitable for use in any Python backend
(FastAPI, CLI, tests, etc.).
"""

import os
import json
import logging
import threading
from typing import Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
from pinecone import Pinecone
from tenacity import retry, stop_after_attempt, wait_exponential
import cohere

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1024
CLAUDE_MODEL = "claude-sonnet-4-20250514"
TOP_K = 25  # Fetch more candidates for reranking
RERANK_TOP_K = 10  # Keep top 10 after reranking
MIN_SCORE_THRESHOLD = 0.3  # Drop chunks below this relevance score
PINECONE_INDEX_NAME = "legal-docs"

# ---------------------------------------------------------------------------
# Retrieval logging
# ---------------------------------------------------------------------------
RETRIEVAL_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "retrieval_log.jsonl")
_log_lock = threading.Lock()


def log_retrieval_metrics(metrics: dict):
    """Append a metrics record to the JSONL retrieval log."""
    metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        with _log_lock:
            with open(RETRIEVAL_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write retrieval log: {e}")


# ---------------------------------------------------------------------------
# Entity mappings
# ---------------------------------------------------------------------------
MAPPINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entity_mappings.json")
try:
    with open(MAPPINGS_FILE, "r") as f:
        _mappings = json.load(f)
    ENTITY_MAPPINGS = _mappings.get("query_expansion", {})
    SOURCE_KEYWORDS_CONFIG = _mappings.get("source_filters", {})
    logger.info(f"Loaded {len(ENTITY_MAPPINGS)} entity mappings and {len(SOURCE_KEYWORDS_CONFIG)} source filters")
except FileNotFoundError:
    logger.warning(f"Entity mappings file not found at {MAPPINGS_FILE}, using empty mappings")
    ENTITY_MAPPINGS = {}
    SOURCE_KEYWORDS_CONFIG = {}

# ---------------------------------------------------------------------------
# Firm profile
# ---------------------------------------------------------------------------
PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goff_law_profile.json")
try:
    with open(PROFILE_FILE, "r") as f:
        FIRM_PROFILE = json.load(f)
    logger.info("Loaded firm profile for %s", FIRM_PROFILE.get("firm", {}).get("name", "unknown"))
except FileNotFoundError:
    logger.warning("Firm profile not found at %s, using empty profile", PROFILE_FILE)
    FIRM_PROFILE = {}

# ---------------------------------------------------------------------------
# Takeaways index
# ---------------------------------------------------------------------------
TAKEAWAYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "takeaways_index.json")
try:
    with open(TAKEAWAYS_FILE, "r") as f:
        TAKEAWAYS_INDEX = json.load(f)
    logger.info("Loaded %d episode takeaways", len(TAKEAWAYS_INDEX.get("episodes", {})))
except FileNotFoundError:
    logger.warning("Takeaways index not found at %s", TAKEAWAYS_FILE)
    TAKEAWAYS_INDEX = {"episodes": {}}

# ---------------------------------------------------------------------------
# Source display names (raw Pinecone source -> human-readable expert name)
# ---------------------------------------------------------------------------
SOURCE_DISPLAY_NAMES = {
    "Burbon of Proof PlaylistJson (1)": "Bob Simon (Bourbon of Proof)",
    "BurbonofProofPlaylist": "Bob Simon (Bourbon of Proof)",
    "GrowYourLawFirmPlaylist": "Ken Hardison (Grow Your Law Firm)",
    "podcast_Grow_Your_Law_Firm": "Ken Hardison (Grow Your Law Firm)",
    "JohnMorganInterviews": "John Morgan (Morgan & Morgan)",
    "GreySkyMediaPodcast": "Grey Sky Media Podcast",
    "CEOLawyer_AliAwad_Playlist": "Ali Awad (CEO Lawyer)",
    "YouCantTeachHungry_2024": "Mike Morse (You Can't Teach Hungry)",
    "MaximumLawyer_Playlist": "Maximum Lawyer Podcast",
    "PIM_Podcast_Season1": "PIM Podcast (Season 1)",
    "PIM_Podcast_Season2": "PIM Podcast (Season 2)",
    "PIM_Podcast_Season3": "PIM Podcast (Season 3)",
    "ptimizing Legal Intake and Client Engagement Through Al With Colleen Joy": "Colleen Joy (Legal Intake & AI)",
    "AttorneyAtWork_MarketingTrends2026": "Attorney at Work (Marketing Trends 2026)",
    "LegalTechTrends2025": "Legal Tech Trends Report 2025",
    "CMOSurvey2025": "CMO Survey 2025",
    "TipTheScales": "Bob Simon (Tip the Scales)",
    "ReferralMarketingClub_Q4": "Ken Hardison (Referral Marketing Club)",
    "TrialLawyer_Spring2024": "Trial Lawyer Magazine (Spring 2024)",
    "TrialLawyer_Summer2024": "Trial Lawyer Magazine (Summer 2024)",
    "TrialLawyer_Fall2024": "Trial Lawyer Magazine (Fall 2024)",
    "TrialLawyer_Spring2025": "Trial Lawyer Magazine (Spring 2025)",
    "TrialLawyer_Summer2025": "Trial Lawyer Magazine (Summer 2025)",
    "TrialLawyer_Fall2025": "Trial Lawyer Magazine (Fall 2025)",
    "TrialLawyer_Winter2025": "Trial Lawyer Magazine (Winter 2025)",
    "TrialLawyer_AList2025": "Trial Lawyer Magazine (A-List 2025)",
    "youtube_DQZvcjcG_cI": "Charley Mann (Law Firm Marketing)",
    "LawFirmMarketingSecrets2025": "Law Firm Marketing Secrets 2025",
    "LawOfficeYouTubeFavorites": "Law Office YouTube Favorites",
    "Abrams_Rd_voice_memo": "Jim Goff (Voice Memo)",
}


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------
def validate_environment() -> bool:
    """Validate required environment variables are set."""
    required_vars = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PINECONE_API_KEY", "COHERE_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        return False
    return True


# ---------------------------------------------------------------------------
# Lazy singleton client initialization
# ---------------------------------------------------------------------------
_clients = None


def get_clients():
    """Return (openai_client, anthropic_client, pinecone_index, cohere_client).

    Clients are created once on first call and reused thereafter.
    """
    global _clients
    if _clients is None:
        if not validate_environment():
            raise RuntimeError("Missing required API keys")
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(PINECONE_INDEX_NAME)
        cohere_client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
        _clients = (openai_client, anthropic_client, index, cohere_client)
        logger.info("All API clients initialized successfully")
    return _clients


# ---------------------------------------------------------------------------
# Embedding (dict cache replaces @st.cache_data)
# ---------------------------------------------------------------------------
_embedding_cache: dict[str, list[float]] = {}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
def get_embedding(text: str) -> Optional[list[float]]:
    """Get embedding for text using OpenAI with caching and retry."""
    if text in _embedding_cache:
        return _embedding_cache[text]
    try:
        openai_client = get_clients()[0]
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
            dimensions=EMBEDDING_DIMENSION
        )
        embedding = response.data[0].embedding
        _embedding_cache[text] = embedding
        return embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise


# ---------------------------------------------------------------------------
# Query expansion
# ---------------------------------------------------------------------------
def expand_query(query: str) -> list[str]:
    """Expand query with related terms."""
    queries = [query]
    query_lower = query.lower()

    for entity, expansions in ENTITY_MAPPINGS.items():
        if entity in query_lower:
            for exp in expansions:
                if exp not in query_lower:
                    queries.append(f"{query} {exp}")

    return queries[:3]


# ---------------------------------------------------------------------------
# Reranking
# ---------------------------------------------------------------------------
def rerank_results(query: str, matches: list, return_scores: bool = False):
    """Rerank results using Cohere for better relevance ordering."""
    if not matches:
        return (matches, []) if return_scores else matches
    try:
        cohere_client = get_clients()[3]
        documents = [m.metadata.get("text", "") for m in matches]
        response = cohere_client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=RERANK_TOP_K,
        )
        reranked = [matches[r.index] for r in response.results]
        scores = [r.relevance_score for r in response.results]
        logger.info(f"Reranked {len(matches)} chunks down to {len(reranked)}")
        return (reranked, scores) if return_scores else reranked
    except Exception as e:
        logger.warning(f"Reranking failed, using original order: {e}")
        fallback = matches[:RERANK_TOP_K]
        return (fallback, []) if return_scores else fallback


# ---------------------------------------------------------------------------
# Source filter detection
# ---------------------------------------------------------------------------
def detect_source_filter(query: str) -> list[str] | None:
    """Detect if the query mentions a known source and return its Pinecone source names."""
    query_lower = query.lower()
    for keyword, source_names in SOURCE_KEYWORDS_CONFIG.items():
        if keyword in query_lower:
            if isinstance(source_names, str):
                return [source_names]
            return source_names
    return None


# ---------------------------------------------------------------------------
# Knowledge-base search
# ---------------------------------------------------------------------------
def search_knowledge_base(query: str, top_k: int = TOP_K) -> list[dict]:
    """Search Pinecone with query expansion, metadata filtering, and deduplication."""
    pinecone_index = get_clients()[2]
    queries = expand_query(query)
    all_matches = {}
    source_filter = detect_source_filter(query)

    for q in queries:
        try:
            query_embedding = get_embedding(q)
        except Exception as e:
            logger.warning(f"Failed to get embedding for query after retries: {e}")
            continue

        try:
            # Unfiltered search
            results = pinecone_index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )

            for match in results.matches:
                if match.id not in all_matches or match.score > all_matches[match.id].score:
                    all_matches[match.id] = match

            # Source-filtered search if a source was detected
            if source_filter:
                filtered_results = pinecone_index.query(
                    vector=query_embedding,
                    top_k=top_k,
                    include_metadata=True,
                    filter={"source": {"$in": source_filter}}
                )
                for match in filtered_results.matches:
                    if match.id not in all_matches or match.score > all_matches[match.id].score:
                        all_matches[match.id] = match

        except Exception as e:
            logger.error(f"Pinecone query error: {e}")
            continue

    sorted_matches = sorted(all_matches.values(), key=lambda x: x.score, reverse=True)

    # Capture pre-filter metrics
    pinecone_total = len(sorted_matches)
    pinecone_score_range = (
        (round(sorted_matches[-1].score, 4), round(sorted_matches[0].score, 4))
        if sorted_matches else (None, None)
    )

    # Filter out low-relevance chunks
    sorted_matches = [m for m in sorted_matches if m.score >= MIN_SCORE_THRESHOLD]
    after_threshold = len(sorted_matches)

    # Rerank for better relevance ordering
    reranked, cohere_scores = rerank_results(query, sorted_matches[:top_k], return_scores=True)
    cohere_score_range = (
        (round(min(cohere_scores), 4), round(max(cohere_scores), 4))
        if cohere_scores else (None, None)
    )

    # Log retrieval metrics
    log_retrieval_metrics({
        "query": query,
        "source_filter": source_filter,
        "num_expanded_queries": len(queries),
        "pinecone_results_total": pinecone_total,
        "pinecone_score_min": pinecone_score_range[0],
        "pinecone_score_max": pinecone_score_range[1],
        "after_threshold_filter": after_threshold,
        "threshold": MIN_SCORE_THRESHOLD,
        "after_rerank": len(reranked),
        "cohere_score_min": cohere_score_range[0],
        "cohere_score_max": cohere_score_range[1],
    })

    return reranked


# ---------------------------------------------------------------------------
# Takeaways search
# ---------------------------------------------------------------------------
def search_takeaways(query: str, limit: int = 5) -> list[dict]:
    """Search takeaways index by keyword matching against titles, topics,
    takeaways, action items, unique insights, and notable quotes."""
    query_lower = query.lower()
    query_words = {w for w in query_lower.split() if len(w) > 3}
    results = []

    for episode_id, ep in TAKEAWAYS_INDEX.get("episodes", {}).items():
        score = 0

        # Full phrase match in title (highest weight)
        if query_lower in ep.get("title", "").lower():
            score += 5

        # Subject area match
        if query_lower in ep.get("subject_area", "").lower():
            score += 4

        # Topic matches
        for topic in ep.get("topics", []):
            topic_lower = topic.lower()
            if query_lower in topic_lower:
                score += 3
            elif any(w in topic_lower for w in query_words):
                score += 1

        # Takeaway content matches
        for takeaway in ep.get("key_takeaways", []):
            if any(w in takeaway.lower() for w in query_words):
                score += 1

        # Action item matches
        for action in ep.get("action_items", []):
            if any(w in action.lower() for w in query_words):
                score += 1

        # Unique insights match
        insights = ep.get("unique_insights", "")
        if isinstance(insights, str) and any(w in insights.lower() for w in query_words):
            score += 1

        if score > 0:
            results.append({"episode_id": episode_id, "score": score, **ep})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def build_prompt(query: str, context_chunks: list[dict], conversation_history: list[dict]) -> tuple:
    """Build the prompt components for Claude. Returns (system_prompt, messages, sources_text)."""

    # --- Extract firm profile data ---
    firm = FIRM_PROFILE.get("firm", {})
    team = FIRM_PROFILE.get("team", {})
    marketing = FIRM_PROFILE.get("marketing", {})
    agent_cfg = FIRM_PROFILE.get("super_agent", {})

    firm_name = firm.get("name", "the firm")
    firm_size = firm.get("firm_size", "PI firm")
    location = firm.get("location", "")
    market = firm.get("market", location)
    owner = team.get("owner", {})
    owner_name = owner.get("name", "the owner")
    owner_focus = owner.get("focus", "")
    coo = team.get("coo", {})
    coo_name = coo.get("name", "the COO")
    coo_focus = coo.get("focus", "")
    practice_areas = ", ".join(firm.get("practice_areas", []))
    channels = ", ".join(marketing.get("current_channels", []))
    priorities = ", ".join(marketing.get("growth_priorities", []))
    competitive = marketing.get("competitive_landscape", "")

    # --- Build context from chunks with display names ---
    context_parts = []
    sources = set()

    for i, match in enumerate(context_chunks, 1):
        metadata = match.metadata
        source = metadata.get("source", "Unknown")
        episode = metadata.get("episode_title", "Unknown")
        text = metadata.get("text", "")
        display_source = SOURCE_DISPLAY_NAMES.get(source, source)

        context_parts.append(f"[Source {i}: {display_source} - \"{episode}\"]\n{text}")
        sources.add(f"{display_source}: {episode}")

    context = "\n\n---\n\n".join(context_parts)

    # --- Search takeaways ---
    takeaway_matches = search_takeaways(query, limit=5)
    takeaways_context = ""

    if takeaway_matches:
        takeaway_parts = []
        for t in takeaway_matches:
            raw_source = t.get("source", "")
            display_source = SOURCE_DISPLAY_NAMES.get(raw_source, raw_source)
            parts = [f"[{display_source} - \"{t.get('title', 'Unknown')}\"]"]
            parts.append(f"  Subject: {t.get('subject_area', 'N/A')}")
            parts.append("  Key Takeaways:")
            for kt in t.get("key_takeaways", []):
                parts.append(f"    - {kt}")
            insights = t.get("unique_insights", "")
            if insights and insights != "None identified":
                parts.append(f"  Unique Insight: {insights}")
            if t.get("action_items"):
                parts.append("  Action Items:")
                for ai in t["action_items"]:
                    parts.append(f"    - {ai}")
            if t.get("notable_quotes"):
                parts.append("  Notable Quotes:")
                for q in t["notable_quotes"]:
                    parts.append(f"    \"{q}\"")
            takeaway_parts.append("\n".join(parts))

        takeaways_context = "\n\n---\n\n".join(takeaway_parts)

    # --- System prompt ---
    system_prompt = f"""You are the SUPER AGENT MARKETING DIRECTOR for {firm_name}, a {firm_size} in {location}.

YOUR FIRM:
- Owner: {owner_name} — {owner_focus}
- COO: {coo_name} — {coo_focus}
- Practice areas: {practice_areas}
- Current marketing: {channels}
- Growth priorities: {priorities}
- Competitive landscape: {competitive}

YOUR KNOWLEDGE BASE:
You have absorbed hundreds of podcast episodes and articles from the top minds in legal marketing, including:
- Ken Hardison (PILMMA founder, Grow Your Law Firm podcast)
- Bob Simon (trial attorney, Bourbon of Proof podcast)
- John Morgan (Morgan & Morgan, "For the People")
- Ali Awad (CEO Lawyer)
- Mike Morse (You Can't Teach Hungry)
- Trial Lawyer Magazine, PIM Podcast, Attorney at Work, and many more

HOW TO CITE AND SYNTHESIZE:
- ALWAYS attribute insights to specific experts by name: "Ken Hardison emphasizes..." or "As Bob Simon puts it..."
- When multiple experts discuss the same topic, compare and synthesize: "Both Morgan and Hardison advocate X, while Morse takes a different approach with Y"
- Include direct quotes from your knowledge base when they are powerful and relevant
- Reference specific episodes or sources so {owner_name} and {coo_name} can go deeper if interested
- When the takeaways intelligence provides action items, present them as tested recommendations from named experts

HOW TO PERSONALIZE FOR {firm_name.upper()}:
- Frame every recommendation in terms of {firm_name}'s {market} market
- Acknowledge the competitive reality ({competitive}) and position advice accordingly
- Consider the firm's current channels ({channels}) and growth priorities when recommending next steps
- Think about what both {owner_name} (strategic direction) and {coo_name} (execution) need to hear

WHAT YOU CAN DO:
1. DRAFT content: emails, scripts, marketing plans, intake scripts, ad copy, social media posts
2. CREATE strategies: full marketing campaigns, referral programs, client nurture sequences
3. BUILD frameworks: checklists, SOPs, evaluation criteria, decision matrices
4. ANALYZE situations: review scenarios and provide detailed recommendations
5. SYNTHESIZE: connect insights across multiple experts into original, actionable guidance

QUALITY STANDARDS:
- Be specific and actionable — vague advice is worthless
- When asked to draft, produce COMPLETE, USABLE content, not outlines
- Connect advice to practical outcomes for a firm of {firm_name}'s size
- Provide the "why" behind recommendations, not just the "what"
- If the knowledge base doesn't cover a topic well, say so honestly
- When experts disagree, present both sides with your recommendation

You are a senior marketing director who knows this firm inside and out. Act like it."""

    # --- Build messages with conversation history ---
    messages = []

    recent_history = conversation_history[-20:]
    for msg in recent_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # --- User message with both context layers ---
    takeaways_block = ""
    if takeaways_context:
        takeaways_block = f"""

Pre-Extracted Episode Intelligence ({len(takeaway_matches)} relevant episodes):
{takeaways_context}"""

    user_message = f"""Current Question: {query}

Retrieved Knowledge Base Context ({len(context_chunks)} most relevant excerpts):
{context}{takeaways_block}

Instructions:
- ALWAYS cite specific experts by name when their insights are relevant (e.g., "Bob Simon recommends...", "Ken Hardison's approach is...")
- When multiple experts discuss the same topic, SYNTHESIZE their perspectives — compare, contrast, and recommend
- Reference specific episodes and quotes when they strengthen your point
- Tailor all advice to {firm_name}'s specific situation in {market}
- If I'm asking you to DRAFT something, produce complete, usable content
- If I'm asking a question, provide a comprehensive answer with specific tactics
- Draw on the conversation history above if relevant
- Structure longer responses clearly
- If the context doesn't cover this topic, acknowledge that and provide your best professional reasoning"""

    messages.append({"role": "user", "content": user_message})

    # --- Build sources footer ---
    sources_list = sorted(sources)[:5]
    sources_items = "".join(f'<div class="source-item">{s}</div>' for s in sources_list)
    sources_text = f'\n\n<div class="sources-card"><div class="sources-title">Sources consulted</div>{sources_items}</div>'

    return system_prompt, messages, sources_text


# ---------------------------------------------------------------------------
# Streaming response generator
# ---------------------------------------------------------------------------
def stream_response(system_prompt: str, messages: list[dict]):
    """Generator that yields text chunks from Claude streaming API."""
    anthropic_client = get_clients()[1]
    with anthropic_client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages
    ) as stream:
        for text in stream.text_stream:
            yield text
