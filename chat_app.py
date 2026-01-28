"""RAG Chatbot for Legal Knowledge Base - Streamlit App (Claude-powered)"""

import os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# Initialize clients
@st.cache_resource
def init_clients():
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("legal-docs")
    return openai_client, anthropic_client, index

openai_client, anthropic_client, pinecone_index = init_clients()

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1024
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Using Claude Sonnet
TOP_K = 25  # Get more chunks for richer context

# Known entity mappings for query expansion
ENTITY_MAPPINGS = {
    "bob simon": ["bourbon of proof", "bob simon"],
    "bourbon of proof": ["bob simon", "bourbon of proof"],
    "john morgan": ["john morgan", "morgan & morgan"],
    "grow your law firm": ["grow your law firm", "ken hardison"],
}


def get_embedding(text: str) -> list[float]:
    """Get embedding for text using OpenAI"""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSION
    )
    return response.data[0].embedding


def expand_query(query: str) -> list[str]:
    """Expand query with related terms"""
    queries = [query]
    query_lower = query.lower()

    # Add entity-based expansions
    for entity, expansions in ENTITY_MAPPINGS.items():
        if entity in query_lower:
            for exp in expansions:
                if exp not in query_lower:
                    queries.append(f"{query} {exp}")

    return queries[:3]  # Limit to 3 queries


def search_knowledge_base(query: str, top_k: int = TOP_K) -> list[dict]:
    """Search Pinecone with query expansion and deduplication"""

    # Expand query
    queries = expand_query(query)

    all_matches = {}

    for q in queries:
        query_embedding = get_embedding(q)

        results = pinecone_index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )

        # Deduplicate by ID, keeping highest score
        for match in results.matches:
            if match.id not in all_matches or match.score > all_matches[match.id].score:
                all_matches[match.id] = match

    # Sort by score and return top results
    sorted_matches = sorted(all_matches.values(), key=lambda x: x.score, reverse=True)
    return sorted_matches[:top_k]


def generate_response(query: str, context_chunks: list[dict]) -> str:
    """Generate response using Claude with retrieved context"""

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

    # System prompt for Claude
    system_prompt = """You are an expert legal practice consultant with deep knowledge from hundreds of podcast episodes, interviews, and educational content about running successful personal injury law firms.

Your knowledge base includes insights from:
- Grow Your Law Firm podcast (Ken Hardison)
- Bourbon of Proof podcast (Bob Simon - LA trial attorney)
- John Morgan interviews (Morgan & Morgan)
- And many other legal industry experts

HOW TO RESPOND:
1. Synthesize insights across multiple sources to provide comprehensive, actionable answers
2. Draw connections between different experts' perspectives when relevant
3. Provide specific strategies, tactics, and real examples from the content
4. When multiple sources discuss a topic, compare and contrast their approaches
5. Organize longer answers with clear structure (bullet points, numbered lists, headers)

DEPTH AND QUALITY:
- Don't just quote the context - analyze it, explain the reasoning behind recommendations
- Connect advice to practical outcomes and real-world application
- If a topic is covered from multiple angles, present a complete picture
- Provide the "why" behind recommendations, not just the "what"

HONESTY:
- If the context doesn't cover a topic, say so clearly
- Distinguish between what's explicitly stated vs. reasonable inferences
- When experts disagree, present both perspectives

Your goal is to be as helpful as a senior consultant who has absorbed all this content and can provide expert-level guidance."""

    # User message with context
    user_message = f"""Question: {query}

Context from knowledge base (25 most relevant excerpts, ranked by relevance):
{context}

Instructions:
- Provide a comprehensive, insightful answer that synthesizes the information above
- Go beyond surface-level summaries - explain strategies, reasoning, and practical applications
- If multiple sources discuss this topic, weave together their insights
- Use specific examples and quotes when they strengthen the answer
- Structure longer answers clearly with bullets or sections
- If the context doesn't adequately cover this topic, acknowledge that honestly"""

    # Generate response using Claude
    response = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    answer = response.content[0].text

    # Add sources
    sources_list = sorted(sources)[:5]  # Limit to top 5 sources
    sources_text = "\n\n**Sources consulted:**\n" + "\n".join(f"- {s}" for s in sources_list)

    return answer + sources_text


# Streamlit UI
st.set_page_config(
    page_title="Legal Knowledge Chatbot",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ Legal Knowledge Chatbot")
st.markdown("*Powered by Claude - Ask questions about law firm management, marketing, client intake, and more!*")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question about running a successful law firm..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge base..."):
            # Search for relevant chunks
            chunks = search_knowledge_base(prompt)

            if not chunks:
                response = "I couldn't find any relevant information in the knowledge base. Try rephrasing your question."
            else:
                response = generate_response(prompt, chunks)

        st.markdown(response)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Sidebar with info
with st.sidebar:
    st.header("About")
    st.markdown("""
    This chatbot searches through **535+ transcripts** from:
    - Grow Your Law Firm Podcast
    - John Morgan Interviews
    - Law Office YouTube Favorites
    - Bourbon of Proof (Bob Simon)
    - And more!

    **7,127 knowledge chunks** ready to answer your questions.

    *Powered by Claude (Anthropic)*
    """)

    st.header("Sample Questions")
    st.markdown("""
    - What are best practices for client intake?
    - How should I handle TV advertising?
    - What advice does John Morgan give?
    - How do successful firms handle case management?
    - What marketing strategies work for PI firms?
    """)

    st.header("Tips")
    st.markdown("""
    - Be specific in your questions
    - Ask about topics, not trivia
    - The system works best for "how to" and strategy questions
    """)

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
