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
# Prompt builder
# ---------------------------------------------------------------------------
def build_prompt(query: str, context_chunks: list[dict], conversation_history: list[dict]) -> tuple:
    """Build the prompt components for Claude. Returns (system_prompt, messages, sources_text)."""

    # Build context from chunks
    context_parts = []
    sources = set()

    for i, match in enumerate(context_chunks, 1):
        metadata = match.metadata
        source = metadata.get("source", "Unknown")
        episode = metadata.get("episode_title", "Unknown")
        text = metadata.get("text", "")
        score = match.score

        context_parts.append(f"[Source {i} (relevance: {score:.2f}): {source} - {episode}]\n{text}")
        sources.add(f"{source}: {episode}")

    context = "\n\n---\n\n".join(context_parts)

    # System prompt
    system_prompt = """You are a SUPER AGENT MARKETING DIRECTOR for personal injury law firms. You have absorbed hundreds of podcast episodes, interviews, and educational content from the top minds in legal marketing.

Your knowledge base includes insights from:
- Grow Your Law Firm podcast (Ken Hardison - PILMMA founder)
- Bourbon of Proof podcast (Bob Simon - LA trial attorney)
- John Morgan interviews (Morgan & Morgan - "For the People")
- Grey Sky Media Podcast (Marketing and business development)
- And many other legal industry experts

YOU CAN DO MORE THAN ANSWER QUESTIONS. You are empowered to:
1. DRAFT content: emails, scripts, marketing plans, intake scripts, ad copy, social media posts
2. CREATE strategies: full marketing campaigns, referral programs, client nurture sequences
3. BUILD frameworks: checklists, SOPs, evaluation criteria, decision matrices
4. ANALYZE situations: review scenarios and provide detailed recommendations
5. THINK step-by-step through complex problems before giving answers

HOW TO WORK:
- When asked to draft something, produce COMPLETE, USABLE content - not just outlines
- When analyzing a situation, think through it systematically before responding
- Draw on specific examples, quotes, and tactics from your knowledge base
- Synthesize insights from multiple experts to create better recommendations
- Be specific and actionable - vague advice is worthless

DRAFTING GUIDELINES:
- Match the tone to the purpose (professional for client letters, conversational for scripts)
- Include specific details and personalization hooks
- Make content ready to use with minimal editing
- For scripts, include talking points and objection handling

DEPTH AND QUALITY:
- Don't just quote the context - synthesize it into original, actionable output
- Connect advice to practical outcomes and real-world application
- Provide the "why" behind recommendations, not just the "what"
- When multiple sources discuss a topic, weave together the best elements

HONESTY:
- If the context doesn't cover a topic well, say so and offer your best reasoning
- Distinguish between what's explicitly stated vs. your professional inference
- When experts disagree, present both perspectives with your recommendation

You are a senior marketing director who can both advise AND execute. Act like it."""

    # Build messages with conversation history
    messages = []

    # Add previous conversation turns (last 10 exchanges max)
    recent_history = conversation_history[-20:]
    for msg in recent_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current query with context
    user_message = f"""Current Question: {query}

Retrieved Knowledge Base Context ({len(context_chunks)} most relevant excerpts):
{context}

Instructions:
- If I'm asking you to DRAFT something, produce complete, usable content
- If I'm asking a question, provide a comprehensive answer with specific tactics
- Draw on the conversation history above if relevant
- Use specific examples and insights from the context
- Structure longer responses clearly
- If the context doesn't cover this topic, acknowledge that and provide your best professional reasoning"""

    messages.append({"role": "user", "content": user_message})

    # Build sources footer
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
