"""Ingest transcript JSON files into Pinecone for RAG chatbot"""

import json
import os
import hashlib
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("legal-docs")

# Configuration
CHUNK_SIZE = 800  # tokens (roughly 4 chars per token)
CHUNK_OVERLAP = 100  # tokens overlap between chunks
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1024  # Match existing index


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks"""
    # Rough token estimate: 4 chars per token
    char_chunk_size = chunk_size * 4
    char_overlap = overlap * 4

    chunks = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = start + char_chunk_size
        chunk_text = text[start:end]

        # Try to end at a sentence boundary
        if end < len(text):
            # Look for sentence endings
            for sep in ['. ', '? ', '! ', '\n\n', '\n']:
                last_sep = chunk_text.rfind(sep)
                if last_sep > char_chunk_size * 0.5:  # Only if we're past halfway
                    chunk_text = chunk_text[:last_sep + len(sep)]
                    break

        if chunk_text.strip():
            chunks.append({
                "text": chunk_text.strip(),
                "chunk_index": chunk_idx,
                "char_start": start,
                "char_end": start + len(chunk_text)
            })
            chunk_idx += 1

        # Move forward with overlap
        start = start + len(chunk_text) - char_overlap
        if start <= chunks[-1]["char_start"] if chunks else 0:
            start = end  # Prevent infinite loop

    return chunks


def get_embedding(text: str) -> list[float]:
    """Get embedding for text using OpenAI"""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSION
    )
    return response.data[0].embedding


def generate_chunk_id(source: str, episode_title: str, chunk_index: int) -> str:
    """Generate unique ID for a chunk"""
    content = f"{source}:{episode_title}:{chunk_index}"
    return hashlib.md5(content.encode()).hexdigest()


def process_transcript_file(file_path: Path) -> Generator[dict, None, None]:
    """Process a transcript JSON file and yield chunks with metadata"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Determine source name
    source_name = file_path.stem

    # Handle different JSON structures
    if 'episodes' in data:
        episodes = data['episodes']
    elif 'videos' in data:
        episodes = data['videos']
    else:
        print(f"  Unknown structure in {file_path.name}, skipping")
        return

    for episode in episodes:
        # Get transcript
        transcript_data = episode.get('transcript', {})

        if not transcript_data.get('available', False):
            continue

        # Get full text
        full_text = transcript_data.get('full_text', '')
        if not full_text:
            # Try to build from segments
            segments = transcript_data.get('segments', [])
            if segments:
                full_text = ' '.join(seg.get('text', '') for seg in segments)

        if not full_text or len(full_text) < 100:
            continue

        # Get episode metadata
        episode_title = episode.get('title', episode.get('filename', 'Unknown'))
        episode_number = episode.get('episode_number')

        # Chunk the transcript
        chunks = chunk_text(full_text)

        for chunk in chunks:
            # Create enriched text that includes source context for better search
            enriched_text = f"[Source: {source_name}] [Episode: {episode_title}]\n\n{chunk['text']}"

            # Build metadata - only include non-null values
            metadata = {
                "source": source_name,
                "episode_title": episode_title,
                "chunk_index": chunk["chunk_index"],
                "total_chunks": len(chunks),
                "text": chunk["text"]  # Store full text for display
            }
            if episode_number is not None:
                metadata["episode_number"] = episode_number

            yield {
                "id": generate_chunk_id(source_name, episode_title, chunk["chunk_index"]),
                "text": enriched_text,  # Embed the enriched version
                "metadata": metadata
            }


def ingest_all_transcripts(output_dir: str):
    """Ingest all transcript files into Pinecone"""
    output_path = Path(output_dir)
    json_files = list(output_path.glob("*.json"))

    print(f"Found {len(json_files)} JSON files to process")

    total_chunks = 0
    batch = []
    batch_size = 100  # Upsert in batches

    for file_path in json_files:
        print(f"\nProcessing: {file_path.name}")
        file_chunks = 0

        for chunk_data in process_transcript_file(file_path):
            # Get embedding
            try:
                embedding = get_embedding(chunk_data["text"])
            except Exception as e:
                print(f"  Error getting embedding: {e}")
                continue

            # Add to batch
            batch.append({
                "id": chunk_data["id"],
                "values": embedding,
                "metadata": chunk_data["metadata"]
            })

            file_chunks += 1
            total_chunks += 1

            # Upsert batch when full
            if len(batch) >= batch_size:
                index.upsert(vectors=batch)
                print(f"  Upserted batch of {len(batch)} vectors (total: {total_chunks})")
                batch = []

        print(f"  Processed {file_chunks} chunks from {file_path.name}")

    # Upsert remaining
    if batch:
        index.upsert(vectors=batch)
        print(f"  Upserted final batch of {len(batch)} vectors")

    print(f"\n{'='*60}")
    print(f"Ingestion Complete!")
    print(f"Total chunks ingested: {total_chunks}")
    print(f"{'='*60}")

    # Verify
    stats = index.describe_index_stats()
    print(f"Pinecone index now has {stats.total_vector_count} vectors")


if __name__ == "__main__":
    output_dir = r"C:\Users\jim\OneDrive\Documents\Bill AI Machine\output"
    ingest_all_transcripts(output_dir)
