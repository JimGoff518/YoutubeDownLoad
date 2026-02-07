"""Ingest only the newly extracted JSON files into Pinecone."""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
from ingest_to_pinecone import process_transcript_file, get_embedding, index

NEW_FILES = [
    "youtube_ZBAC0BA4ux8.json",
    "youtube_cn6zcEhH-qU.json",
    "youtube_DQZvcjcG_cI.json",
    "LegalTechTrends2025.json",
    "CMOSurvey2025.json",
    "AttorneyAtWork_MarketingTrends2026.json",
    "TrialLawyer_Spring2024.json",
    "TrialLawyer_Summer2024.json",
    "TrialLawyer_Fall2024.json",
    "TrialLawyer_Spring2025.json",
    "TrialLawyer_Summer2025.json",
    "TrialLawyer_Fall2025.json",
    "TrialLawyer_Winter2025.json",
    "TrialLawyer_AList2025.json",
]

output_dir = Path(r"C:\Users\jim\OneDrive\Documents\Bill AI Machine\output")

total_chunks = 0
batch = []
batch_size = 100

for filename in NEW_FILES:
    file_path = output_dir / filename
    if not file_path.exists():
        print(f"SKIP - not found: {filename}", flush=True)
        continue

    print(f"\nProcessing: {filename}", flush=True)
    file_chunks = 0

    for chunk_data in process_transcript_file(file_path):
        try:
            embedding = get_embedding(chunk_data["text"])
        except Exception as e:
            print(f"  Error getting embedding: {e}", flush=True)
            continue

        batch.append({
            "id": chunk_data["id"],
            "values": embedding,
            "metadata": chunk_data["metadata"]
        })

        file_chunks += 1
        total_chunks += 1

        if len(batch) >= batch_size:
            index.upsert(vectors=batch)
            print(f"  Upserted batch of {len(batch)} vectors (total: {total_chunks})", flush=True)
            batch = []

    print(f"  Processed {file_chunks} chunks from {filename}", flush=True)

if batch:
    index.upsert(vectors=batch)
    print(f"  Upserted final batch of {len(batch)} vectors", flush=True)

print(f"\nIngestion Complete! Total chunks: {total_chunks}", flush=True)

stats = index.describe_index_stats()
print(f"Pinecone index now has {stats.total_vector_count} vectors", flush=True)
