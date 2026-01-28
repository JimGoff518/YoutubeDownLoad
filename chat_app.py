"""RAG Chatbot for Legal Knowledge Base - Super Agent Marketing Director (Claude-powered)"""

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
TOP_K = 15  # Fewer but complete chunks for better context

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


def generate_response(query: str, context_chunks: list[dict], conversation_history: list[dict]) -> str:
    """Generate response using Claude with retrieved context and conversation history"""

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

    # System prompt for Super Agent Marketing Director
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

    # Add previous conversation turns (last 10 exchanges max for context)
    recent_history = conversation_history[-20:]  # Last 10 exchanges (20 messages)
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

    # Generate response using Claude
    response = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages
    )

    answer = response.content[0].text

    # Add sources (small text)
    sources_list = sorted(sources)[:5]  # Limit to top 5 sources
    sources_items = "<br>".join(f"• {s}" for s in sources_list)
    sources_text = f"\n\n<sub><sup>**Sources consulted:**<br>{sources_items}</sup></sub>"

    return answer + sources_text


# Streamlit UI
st.set_page_config(
    page_title="Super Agent Marketing Director",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Super Agent Marketing Director")
st.markdown("*Your AI marketing director for PI law firms - Ask questions OR request drafts of emails, scripts, plans & more!*")

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
                # Pass conversation history for context
                response = generate_response(prompt, chunks, st.session_state.messages)

        st.markdown(response)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Sidebar with info
with st.sidebar:
    st.header("About")
    st.markdown("""
    Your **Super Agent Marketing Director** with knowledge from:
    - Grow Your Law Firm Podcast (Ken Hardison)
    - Bourbon of Proof (Bob Simon)
    - John Morgan Interviews
    - Grey Sky Media Podcast
    - And 500+ more episodes!

    **I can DRAFT content, not just answer questions!**

    *Powered by Claude (Anthropic)*
    """)

    st.header("Try These Prompts")
    st.markdown("""
    **Ask Questions:**
    - What are best practices for client intake?
    - How does John Morgan approach TV advertising?

    **Request Drafts:**
    - Draft a follow-up email for a lead who went cold
    - Write a script for intake specialists
    - Create a 90-day marketing plan for a new PI firm
    - Draft social media posts about client testimonials
    """)

    st.header("Tips")
    st.markdown("""
    - Ask me to **draft** emails, scripts, plans
    - Be specific about what you need
    - Follow up - I remember our conversation!
    """)

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
