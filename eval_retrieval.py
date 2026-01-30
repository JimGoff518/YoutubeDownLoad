"""
Retrieval evaluation script for Phase 2.2.
Runs test questions through the search pipeline and records detailed metrics.

Usage:
    python eval_retrieval.py
    python eval_retrieval.py --output my_results.json
    python eval_retrieval.py --questions my_questions.json
"""

import os
import json
import time
import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone
import cohere

# Configuration (mirrors chat_app_with_history.py)
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1024
TOP_K = 25
RERANK_TOP_K = 10
MIN_SCORE_THRESHOLD = 0.3
PINECONE_INDEX_NAME = "legal-docs"

# Load entity mappings
MAPPINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entity_mappings.json")
try:
    with open(MAPPINGS_FILE, "r") as f:
        _mappings = json.load(f)
    ENTITY_MAPPINGS = _mappings.get("query_expansion", {})
    SOURCE_KEYWORDS_CONFIG = _mappings.get("source_filters", {})
except FileNotFoundError:
    ENTITY_MAPPINGS = {}
    SOURCE_KEYWORDS_CONFIG = {}

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index(PINECONE_INDEX_NAME)
cohere_client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))


def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL, input=text, dimensions=EMBEDDING_DIMENSION
    )
    return response.data[0].embedding


def expand_query(query: str) -> list[str]:
    queries = [query]
    query_lower = query.lower()
    for entity, expansions in ENTITY_MAPPINGS.items():
        if entity in query_lower:
            for exp in expansions:
                if exp not in query_lower:
                    queries.append(f"{query} {exp}")
    return queries[:3]


def detect_source_filter(query: str):
    query_lower = query.lower()
    for keyword, source_names in SOURCE_KEYWORDS_CONFIG.items():
        if keyword in query_lower:
            if isinstance(source_names, str):
                return [source_names]
            return source_names
    return None


def evaluate_query(query_obj: dict) -> dict:
    """Run a single query through the full retrieval pipeline and record metrics."""
    query = query_obj["query"]
    source_filter = detect_source_filter(query)
    queries = expand_query(query)

    all_matches = {}

    for q in queries:
        try:
            embedding = get_embedding(q)
        except Exception as e:
            print(f"  Embedding error for '{q[:50]}': {e}")
            continue

        try:
            results = pinecone_index.query(
                vector=embedding, top_k=TOP_K, include_metadata=True
            )
            for match in results.matches:
                if match.id not in all_matches or match.score > all_matches[match.id].score:
                    all_matches[match.id] = match

            if source_filter:
                filtered_results = pinecone_index.query(
                    vector=embedding,
                    top_k=TOP_K,
                    include_metadata=True,
                    filter={"source": {"$in": source_filter}},
                )
                for match in filtered_results.matches:
                    if match.id not in all_matches or match.score > all_matches[match.id].score:
                        all_matches[match.id] = match
        except Exception as e:
            print(f"  Pinecone error: {e}")
            continue

    sorted_matches = sorted(all_matches.values(), key=lambda x: x.score, reverse=True)

    pinecone_total = len(sorted_matches)
    pinecone_scores = [m.score for m in sorted_matches]

    # Threshold filter
    after_threshold_matches = [m for m in sorted_matches if m.score >= MIN_SCORE_THRESHOLD]
    after_threshold = len(after_threshold_matches)

    # Rerank
    cohere_scores = []
    reranked = []
    if after_threshold_matches:
        try:
            documents = [m.metadata.get("text", "") for m in after_threshold_matches[:TOP_K]]
            response = cohere_client.rerank(
                model="rerank-v3.5",
                query=query,
                documents=documents,
                top_n=RERANK_TOP_K,
            )
            reranked = [after_threshold_matches[r.index] for r in response.results]
            cohere_scores = [r.relevance_score for r in response.results]
        except Exception as e:
            print(f"  Rerank error: {e}")
            reranked = after_threshold_matches[:RERANK_TOP_K]

    # Check source filter accuracy
    source_match = None
    if query_obj.get("expected_sources") and reranked:
        top_sources = [m.metadata.get("source") for m in reranked[:3]]
        expected = set(query_obj["expected_sources"])
        source_match = any(s in expected for s in top_sources)

    return {
        "id": query_obj["id"],
        "category": query_obj["category"],
        "query": query,
        "should_return_results": query_obj["should_return_results"],
        "actually_returned_results": len(reranked) > 0,
        "source_filter_detected": source_filter,
        "expected_sources": query_obj.get("expected_sources"),
        "source_filter_correct": source_match,
        "num_expanded_queries": len(queries),
        "pinecone_results_total": pinecone_total,
        "pinecone_score_min": round(min(pinecone_scores), 4) if pinecone_scores else None,
        "pinecone_score_max": round(max(pinecone_scores), 4) if pinecone_scores else None,
        "pinecone_score_avg": round(sum(pinecone_scores) / len(pinecone_scores), 4) if pinecone_scores else None,
        "after_threshold_filter": after_threshold,
        "threshold_used": MIN_SCORE_THRESHOLD,
        "after_rerank": len(reranked),
        "cohere_score_min": round(min(cohere_scores), 4) if cohere_scores else None,
        "cohere_score_max": round(max(cohere_scores), 4) if cohere_scores else None,
        "top_3_chunks": [
            {
                "source": m.metadata.get("source"),
                "episode": m.metadata.get("episode_title"),
                "pinecone_score": round(m.score, 4),
                "text_preview": m.metadata.get("text", "")[:200],
            }
            for m in reranked[:3]
        ],
        "manual_relevance": None,
    }


def print_summary(results: list):
    """Print a console summary of evaluation results."""
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "with_results": 0, "correct_no_results": 0}
        categories[cat]["total"] += 1
        if r["actually_returned_results"]:
            categories[cat]["with_results"] += 1
        if not r["should_return_results"] and not r["actually_returned_results"]:
            categories[cat]["correct_no_results"] += 1

    print("\n" + "=" * 70)
    print("RETRIEVAL EVALUATION SUMMARY")
    print("=" * 70)
    print(f"{'Category':<25} {'Total':>6} {'Got Results':>12} {'Correct':>10}")
    print("-" * 70)

    for cat, stats in sorted(categories.items()):
        print(f"{cat:<25} {stats['total']:>6} {stats['with_results']:>12}", end="")
        if cat == "should_return_nothing":
            print(f" {stats['correct_no_results']}/{stats['total']:>8}")
        else:
            print()

    # Source filter accuracy
    src_queries = [r for r in results if r["expected_sources"]]
    if src_queries:
        correct = sum(1 for r in src_queries if r["source_filter_correct"])
        print(f"\nSource filter accuracy: {correct}/{len(src_queries)}")

    # Score ranges
    all_pinecone_maxes = [r["pinecone_score_max"] for r in results if r["pinecone_score_max"]]
    all_pinecone_mins = [r["pinecone_score_min"] for r in results if r["pinecone_score_min"]]
    if all_pinecone_maxes:
        print(f"\nPinecone score range across all queries: {min(all_pinecone_mins):.4f} - {max(all_pinecone_maxes):.4f}")

    all_cohere_maxes = [r["cohere_score_max"] for r in results if r["cohere_score_max"]]
    all_cohere_mins = [r["cohere_score_min"] for r in results if r["cohere_score_min"]]
    if all_cohere_maxes:
        print(f"Cohere score range across all queries:   {min(all_cohere_mins):.4f} - {max(all_cohere_maxes):.4f}")

    # False positives (off-topic queries that returned results)
    null_queries = [r for r in results if not r["should_return_results"]]
    false_positives = [r for r in null_queries if r["actually_returned_results"]]
    if null_queries:
        print(f"\nFalse positives (off-topic with results): {len(false_positives)}/{len(null_queries)}")
        for fp in false_positives:
            print(f"  - {fp['query']} (top score: {fp['pinecone_score_max']})")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Evaluate retrieval pipeline quality")
    parser.add_argument(
        "--questions",
        default="test_questions.json",
        help="Path to test questions JSON file",
    )
    parser.add_argument(
        "--output",
        default="eval_results.json",
        help="Path to output results JSON file",
    )
    args = parser.parse_args()

    # Load questions
    with open(args.questions, "r", encoding="utf-8") as f:
        data = json.load(f)

    queries = data["queries"]
    print(f"Loaded {len(queries)} test queries from {args.questions}")
    print(f"Config: TOP_K={TOP_K}, RERANK_TOP_K={RERANK_TOP_K}, MIN_SCORE_THRESHOLD={MIN_SCORE_THRESHOLD}")
    print()

    # Evaluate each query
    results = []
    for i, q in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] {q['id']}: {q['query'][:60]}...")
        result = evaluate_query(q)
        results.append(result)
        print(f"  Pinecone: {result['pinecone_results_total']} -> Threshold: {result['after_threshold_filter']} -> Rerank: {result['after_rerank']}")
        if i < len(queries):
            time.sleep(7)  # Cohere trial key: 10 calls/min

    # Write results
    output_data = {
        "evaluation_metadata": {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "questions_file": args.questions,
            "total_queries": len(queries),
            "config": {
                "TOP_K": TOP_K,
                "RERANK_TOP_K": RERANK_TOP_K,
                "MIN_SCORE_THRESHOLD": MIN_SCORE_THRESHOLD,
                "EMBEDDING_MODEL": EMBEDDING_MODEL,
            },
        },
        "results": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {args.output}")
    print_summary(results)


if __name__ == "__main__":
    main()
