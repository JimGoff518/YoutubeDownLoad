"""Run all PIM podcast transcriptions (Seasons 1-3) then ingest to Pinecone.
Designed to run unattended. Resume-safe — skips already-transcribed episodes."""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from transcribe_local_audio import transcribe_audio_files

BASE = r"C:\Users\jim\Downloads\PIM_extracted"
OUTPUT = r"C:\Users\jim\OneDrive\Documents\Bill AI Machine\output"

seasons = [
    {
        "name": "Season 1",
        "source": f"{BASE}\\Season 1\\Personal Injury Mastermind (PIM) Podcast (Season 1)",
        "output": f"{OUTPUT}\\PIM_Podcast_Season1.json",
    },
    {
        "name": "Season 2",
        "source": f"{BASE}\\Season 2\\Personal Injury Mastermind (PIM) Podcast (Season 2)",
        "output": f"{OUTPUT}\\PIM_Podcast_Season2.json",
    },
    {
        "name": "Season 3",
        "source": f"{BASE}\\Season 3\\Personal Injury Mastermind (PIM) Podcast (Season 3)",
        "output": f"{OUTPUT}\\PIM_Podcast_Season3.json",
    },
]

if __name__ == "__main__":
    log = Path(__file__).parent / "pim_transcription_log.txt"

    def log_msg(msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line)
        with open(log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log_msg("=== PIM Batch Transcription Started ===")

    for season in seasons:
        log_msg(f"Starting {season['name']}...")
        start = time.time()
        try:
            transcribe_audio_files(season["source"], season["output"])
            elapsed = time.time() - start
            log_msg(f"{season['name']} complete in {elapsed/60:.1f} minutes")
        except Exception as e:
            log_msg(f"ERROR in {season['name']}: {e}")

    log_msg("=== All transcriptions complete. Starting Pinecone ingestion... ===")

    try:
        from ingest_to_pinecone import process_transcript_file, get_embedding, index

        pim_files = [
            f"{OUTPUT}\\PIM_Podcast_Season1.json",
            f"{OUTPUT}\\PIM_Podcast_Season2.json",
            f"{OUTPUT}\\PIM_Podcast_Season3.json",
        ]
        total_chunks = 0
        batch = []
        batch_size = 100

        for pim_file in pim_files:
            p = Path(pim_file)
            if not p.exists():
                log_msg(f"SKIP - not found: {p.name}")
                continue
            log_msg(f"Ingesting: {p.name}")
            file_chunks = 0
            for chunk_data in process_transcript_file(p):
                try:
                    embedding = get_embedding(chunk_data["text"])
                except Exception as e:
                    log_msg(f"  Embedding error: {e}")
                    continue
                batch.append({
                    "id": chunk_data["id"],
                    "values": embedding,
                    "metadata": chunk_data["metadata"],
                })
                file_chunks += 1
                total_chunks += 1
                if len(batch) >= batch_size:
                    index.upsert(vectors=batch)
                    log_msg(f"  Upserted batch of {len(batch)} (total: {total_chunks})")
                    batch = []
            log_msg(f"  {file_chunks} chunks from {p.name}")

        if batch:
            index.upsert(vectors=batch)
            log_msg(f"  Upserted final batch of {len(batch)}")

        stats = index.describe_index_stats()
        log_msg(f"Pinecone index now has {stats.total_vector_count} vectors")
        log_msg("=== Pinecone ingestion complete ===")
    except Exception as e:
        log_msg(f"Ingestion error (run manually later): {e}")

    log_msg("=== ALL DONE ===")
