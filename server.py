"""Bill AI Machine - Flask web application with RAG chatbot API."""

import os
import json
import logging
from pathlib import Path
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
from rag import search_knowledge_base, build_prompt, stream_response, SOURCE_DISPLAY_NAMES

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")

OUTPUT_DIR = Path("/app/output")


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
