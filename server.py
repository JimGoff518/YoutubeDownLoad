"""Simple web server for downloading output files"""

import os
from pathlib import Path
from flask import Flask, send_file, jsonify, abort

app = Flask(__name__)

OUTPUT_DIR = Path("/app/output")


@app.route("/")
def index():
    """List available files for download"""
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
    """Download a specific file"""
    # Security: only allow .json files from output directory
    if not filename.endswith(".json"):
        abort(400, "Only JSON files can be downloaded")

    # Prevent directory traversal
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
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
