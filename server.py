"""Bill AI Machine - Flask web application with RAG chatbot API."""

import os
import json
import logging
import time
import threading
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests
from flask import Flask, render_template, request, jsonify, Response, send_file, abort, send_from_directory

from database import (
    create_conversation,
    add_message,
    get_conversation_messages,
    get_all_conversations,
    update_conversation_title,
    delete_conversation,
    generate_title_from_message,
)
from rag import search_knowledge_base, build_prompt, stream_response, SOURCE_DISPLAY_NAMES, TAKEAWAYS_INDEX

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")

OUTPUT_DIR = Path("/app/output")
REFRESH_LOG_PATH = Path("refresh_log.json")


# ============================================
# PAGE ROUTES
# ============================================

@app.route("/")
def index():
    """Serve the chat UI."""
    return render_template("index.html")


# ============================================
# EXISTING ROUTES (preserved)
# ============================================

@app.route("/files")
def list_files():
    """List available files for download."""
    if not OUTPUT_DIR.exists():
        return jsonify({"error": "Output directory not found", "files": []})

    files = []
    for f in OUTPUT_DIR.glob("*.json"):
        stat = f.stat()
        files.append({
            "name": f.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "download_url": f"/download/{f.name}"
        })

    return jsonify({
        "message": "YouTube Transcript Extractor - File Server",
        "files": files,
        "total_files": len(files)
    })


@app.route("/download/<filename>")
def download_file(filename):
    """Download a specific file."""
    if not filename.endswith(".json"):
        abort(400, "Only JSON files can be downloaded")

    if "/" in filename or "\\" in filename or ".." in filename:
        abort(400, "Invalid filename")

    file_path = OUTPUT_DIR / filename

    if not file_path.exists():
        abort(404, f"File not found: {filename}")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/json"
    )


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    """Serve static assets (header video, etc.)."""
    return send_from_directory("assets", filename)


# ============================================
# CONVERSATION API
# ============================================

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    """List all conversations."""
    conversations = get_all_conversations()
    return jsonify(conversations)


@app.route("/api/conversations", methods=["POST"])
def create_new_conversation():
    """Create a new conversation."""
    conv_id = create_conversation()
    return jsonify({"id": conv_id}), 201


@app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
def get_messages(conv_id):
    """Get all messages for a conversation."""
    messages = get_conversation_messages(conv_id)
    return jsonify(messages)


@app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
def remove_conversation(conv_id):
    """Delete a conversation."""
    delete_conversation(conv_id)
    return jsonify({"status": "deleted"}), 200


# ============================================
# SSE CHAT STREAMING
# ============================================

@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """SSE endpoint for streaming Claude responses."""
    data = request.get_json()
    query = data.get("query", "").strip()
    conversation_id = data.get("conversation_id")

    if not query:
        return jsonify({"error": "Query is required"}), 400

    # Create conversation if needed
    is_new = conversation_id is None
    if is_new:
        conversation_id = create_conversation()
        title = generate_title_from_message(query)
        update_conversation_title(conversation_id, title)

    # Save user message
    add_message(conversation_id, "user", query)

    # Get conversation history for context (exclude the message we just added)
    history = get_conversation_messages(conversation_id)
    # Remove the last user message (we include it separately in build_prompt)
    if history and history[-1]["role"] == "user" and history[-1]["content"] == query:
        history = history[:-1]
    # Limit to recent history
    history = history[-20:]

    # RAG pipeline
    chunks = search_knowledge_base(query)

    def generate():
        # Send conversation_id so client can track it
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conversation_id})}\n\n"

        if not chunks:
            logger.info(f"No results for query: {query}")
            no_results_msg = (
                "I wasn't able to find relevant information in the knowledge base for that question. "
                "This could mean the topic isn't covered in the podcasts and content I've been trained on.\n\n"
                "You could try:\n"
                "- Rephrasing your question\n"
                "- Asking about a specific source (e.g., 'What does Bob Simon say about...')\n"
                "- Broadening your topic\n\n"
                "If you think this topic should be covered, let me know so we can add relevant content."
            )
            yield f"data: {json.dumps({'type': 'text', 'content': no_results_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'sources': []})}\n\n"
            add_message(conversation_id, "assistant", no_results_msg)
            return

        system_prompt, messages, sources_text = build_prompt(query, chunks, history)

        full_response = ""
        try:
            for text_chunk in stream_response(system_prompt, messages):
                full_response += text_chunk
                yield f"data: {json.dumps({'type': 'text', 'content': text_chunk})}\n\n"
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            error_msg = f"Sorry, I encountered an error generating a response: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
            add_message(conversation_id, "assistant", error_msg)
            return

        # Send sources as structured data with display names
        sources_list = []
        seen = set()
        for match in chunks[:5]:
            meta = match.metadata
            source = meta.get("source", "Unknown")
            display_source = SOURCE_DISPLAY_NAMES.get(source, source)
            episode = meta.get("episode_title", "Unknown")
            key = f"{display_source}:{episode}"
            if key not in seen:
                seen.add(key)
                sources_list.append({"source": display_source, "episode": episode})

        yield f"data: {json.dumps({'type': 'done', 'sources': sources_list})}\n\n"

        # Save full response to database (include sources HTML for history)
        add_message(conversation_id, "assistant", full_response + sources_text)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# ============================================
# DASHBOARD STATS API
# ============================================

@app.route("/api/stats")
def get_stats():
    """Return knowledge base and conversation stats for the dashboard."""
    episodes = TAKEAWAYS_INDEX.get("episodes", {})
    total_episodes = TAKEAWAYS_INDEX.get("total_episodes", len(episodes))

    # Count unique sources
    sources = set()
    for ep in episodes.values():
        src = ep.get("source", "")
        if src:
            sources.add(src)

    # Count unique topics
    topics = set()
    for ep in episodes.values():
        for topic in ep.get("topics", []):
            topics.add(topic.lower().strip())
        sa = ep.get("subject_area", "")
        if sa:
            topics.add(sa.lower().strip())

    # Count conversations
    conversations = get_all_conversations()

    return jsonify({
        "episodes": total_episodes,
        "sources": len(SOURCE_DISPLAY_NAMES),
        "topics": len(topics),
        "conversations": len(conversations),
    })


# ============================================
# NEWS TICKER API
# ============================================

_news_cache = {"data": [], "fetched_at": 0}
NEWS_CACHE_SECONDS = 1800  # 30 minutes


def _time_ago(published_parsed):
    """Convert a feedparser time struct to a 'time ago' string."""
    if not published_parsed:
        return ""
    try:
        pub_ts = time.mktime(published_parsed)
        diff = time.time() - pub_ts
        if diff < 3600:
            mins = int(diff / 60)
            return f"{mins}m ago"
        elif diff < 86400:
            hours = int(diff / 3600)
            return f"{hours}h ago"
        else:
            days = int(diff / 86400)
            return f"{days}d ago"
    except Exception:
        return ""


def _fetch_google_news(query, max_items=8):
    """Fetch headlines from Google News RSS for a query."""
    items = []
    try:
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            items.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "source": "Google News",
                "published_ago": _time_ago(entry.get("published_parsed")),
            })
    except Exception as e:
        logger.warning(f"Google News fetch failed for '{query}': {e}")
    return items


def _fetch_reddit(subreddit, max_items=5):
    """Fetch top posts from a subreddit using the public JSON API."""
    items = []
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={max_items}"
        headers = {"User-Agent": "BillAIMachine/1.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            if d.get("stickied"):
                continue
            created = d.get("created_utc", 0)
            diff = time.time() - created
            if diff < 3600:
                ago = f"{int(diff/60)}m ago"
            elif diff < 86400:
                ago = f"{int(diff/3600)}h ago"
            else:
                ago = f"{int(diff/86400)}d ago"
            items.append({
                "title": d.get("title", ""),
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "source": f"r/{subreddit}",
                "published_ago": ago,
            })
    except Exception as e:
        logger.warning(f"Reddit fetch failed for r/{subreddit}: {e}")
    return items


def _fetch_all_news():
    """Fetch news from all sources and return combined list."""
    items = []
    items.extend(_fetch_google_news("personal injury law firm", max_items=6))
    items.extend(_fetch_google_news("mass tort litigation", max_items=6))
    items.extend(_fetch_reddit("law", max_items=4))
    # Deduplicate by title
    seen = set()
    deduped = []
    for item in items:
        key = item["title"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


@app.route("/api/news")
def get_news():
    """Return cached PI/mass tort news headlines."""
    now = time.time()
    if now - _news_cache["fetched_at"] > NEWS_CACHE_SECONDS or not _news_cache["data"]:
        logger.info("Refreshing news cache...")
        _news_cache["data"] = _fetch_all_news()
        _news_cache["fetched_at"] = now
        logger.info(f"Cached {len(_news_cache['data'])} news items")
    return jsonify(_news_cache["data"])


# ============================================
# REFRESH PIPELINE API
# ============================================

_refresh_status = {"running": False, "last_result": None}


@app.route("/api/refresh", methods=["POST"])
def trigger_refresh():
    """Trigger the auto-refresh pipeline."""
    if _refresh_status["running"]:
        return jsonify({"error": "Refresh already running"}), 409

    def run_in_background():
        _refresh_status["running"] = True
        try:
            from auto_refresh import run_refresh
            result = run_refresh()
            _refresh_status["last_result"] = result
        except Exception as e:
            _refresh_status["last_result"] = {"error": str(e)}
        finally:
            _refresh_status["running"] = False

    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/refresh/status")
def refresh_status():
    """Check refresh pipeline status."""
    return jsonify(_refresh_status)


@app.route("/api/refresh/latest")
def refresh_latest():
    """Get the latest refresh result for the notification banner."""
    try:
        if REFRESH_LOG_PATH.exists():
            with open(REFRESH_LOG_PATH, encoding="utf-8") as f:
                log = json.load(f)
            if log:
                return jsonify(log[-1])
        return jsonify(None)
    except Exception:
        return jsonify(None)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
