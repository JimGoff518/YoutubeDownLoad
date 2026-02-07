// =============================================================================
// app.js - Client-side JavaScript for the Bill AI Machine chatbot
// Manages state, API calls, SSE streaming, and DOM rendering
// =============================================================================

// -----------------------------------------------------------------------------
// Markdown Configuration
// -----------------------------------------------------------------------------
marked.setOptions({
    breaks: true,
    gfm: true
});

// -----------------------------------------------------------------------------
// State Management
// -----------------------------------------------------------------------------
const state = {
    currentConversationId: null,
    conversations: [],
    messages: [],
    isStreaming: false
};

// Restore last conversation from localStorage on page load
(function init() {
    const saved = localStorage.getItem('currentConversationId');
    if (saved) state.currentConversationId = parseInt(saved);
    fetchConversations().then(() => {
        if (state.currentConversationId) {
            loadConversation(state.currentConversationId);
        }
    });
})();

// -----------------------------------------------------------------------------
// API Helpers
// -----------------------------------------------------------------------------

async function fetchConversations() {
    const res = await fetch('/api/conversations');
    state.conversations = await res.json();
    renderSidebar();
}

async function loadConversation(id) {
    state.currentConversationId = id;
    localStorage.setItem('currentConversationId', id);
    const res = await fetch(`/api/conversations/${id}/messages`);
    state.messages = await res.json();
    renderMessages();
    renderSidebar();
}

async function deleteConversation(id, event) {
    event.stopPropagation();
    await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
    if (state.currentConversationId === id) {
        startNewConversation();
    }
    fetchConversations();
}

function startNewConversation() {
    state.currentConversationId = null;
    state.messages = [];
    localStorage.removeItem('currentConversationId');
    renderMessages();
    renderSidebar();
}

// -----------------------------------------------------------------------------
// SSE Streaming (POST-based using fetch + getReader)
// -----------------------------------------------------------------------------

async function sendMessage(query) {
    if (state.isStreaming || !query.trim()) return;
    state.isStreaming = true;
    updateSendButton();

    // Add user message to UI immediately
    state.messages.push({ role: 'user', content: query });
    appendMessage('user', query);

    // Show loading indicator
    const loadingEl = showLoadingIndicator();

    // Create assistant message placeholder
    const assistantEl = appendMessage('assistant', '');
    const contentEl = assistantEl.querySelector('.message-content');

    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                conversation_id: state.currentConversationId
            })
        });

        // Remove loading indicator
        loadingEl.remove();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));

                    if (data.type === 'meta') {
                        state.currentConversationId = data.conversation_id;
                        localStorage.setItem('currentConversationId', data.conversation_id);
                        fetchConversations();
                    } else if (data.type === 'text') {
                        fullText += data.content;
                        contentEl.innerHTML = marked.parse(fullText);
                        scrollToBottom();
                    } else if (data.type === 'done') {
                        if (data.sources && data.sources.length > 0) {
                            appendSources(assistantEl, data.sources);
                        }
                    } else if (data.type === 'error') {
                        contentEl.textContent = data.content;
                    }
                } catch (e) {
                    // Skip unparseable lines
                }
            }
        }

        state.messages.push({ role: 'assistant', content: fullText });

    } catch (error) {
        loadingEl.remove();
        contentEl.textContent = 'Sorry, there was an error connecting to the server.';
    }

    state.isStreaming = false;
    updateSendButton();
}

// -----------------------------------------------------------------------------
// DOM Rendering Functions
// -----------------------------------------------------------------------------

function renderSidebar() {
    const list = document.getElementById('conversation-list');
    list.innerHTML = '';

    if (state.conversations.length === 0) {
        list.innerHTML = '<p class="conv-meta" style="padding: 8px 10px;">No conversations yet. Start chatting!</p>';
        return;
    }

    for (const conv of state.conversations) {
        const item = document.createElement('div');
        item.className = 'conv-item' + (conv.id === state.currentConversationId ? ' active' : '');

        const dateStr = formatDate(conv.updated_at);

        item.innerHTML = `
            <div class="conv-row">
                <button class="conv-title" onclick="loadConversation(${conv.id})">${escapeHtml(conv.title.substring(0, 30))}</button>
                <button class="conv-delete" onclick="deleteConversation(${conv.id}, event)" title="Delete">&times;</button>
            </div>
            <span class="conv-meta">${conv.message_count} messages &bull; ${dateStr}</span>
        `;
        list.appendChild(item);
    }
}

function renderMessages() {
    const container = document.getElementById('messages-container');
    container.innerHTML = '';

    if (state.messages.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No messages yet</p>
                <p style="font-size: 0.85rem;">Ask a question to get started</p>
            </div>
        `;
        return;
    }

    for (const msg of state.messages) {
        appendMessage(msg.role, msg.content);
    }
    scrollToBottom();
}

function appendMessage(role, content) {
    const container = document.getElementById('messages-container');

    // Remove empty state if present
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.className = `message message-${role}`;

    const renderedContent = content ? marked.parse(content) : '';

    div.innerHTML = `
        <div class="message-role">${role === 'user' ? 'You' : 'Super Agent'}</div>
        <div class="message-content">${renderedContent}</div>
    `;
    container.appendChild(div);
    scrollToBottom();
    return div;
}

function appendSources(messageEl, sources) {
    // Deduplicate sources
    const seen = new Set();
    const unique = sources.filter(s => {
        const key = `${s.source}: ${s.episode}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });

    const sourcesHtml = `
        <div class="sources-card">
            <div class="sources-title">Sources consulted</div>
            ${unique.map(s => `<div class="source-item">${escapeHtml(s.source)}: ${escapeHtml(s.episode)}</div>`).join('')}
        </div>
    `;
    messageEl.querySelector('.message-content').insertAdjacentHTML('beforeend', sourcesHtml);
}

function showLoadingIndicator() {
    const container = document.getElementById('messages-container');
    const div = document.createElement('div');
    div.className = 'loading-indicator';
    div.innerHTML = `
        <div class="loading-dots">
            <span></span><span></span><span></span>
        </div>
        Searching knowledge base...
    `;
    container.appendChild(div);
    scrollToBottom();
    return div;
}

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}

function updateSendButton() {
    const btn = document.getElementById('send-btn');
    btn.disabled = state.isStreaming;
}

// -----------------------------------------------------------------------------
// Event Listeners
// -----------------------------------------------------------------------------

// Form submit
document.getElementById('chat-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    if (query) {
        input.value = '';
        input.style.height = 'auto';
        sendMessage(query);
    }
});

// New conversation button
document.getElementById('new-conversation-btn').addEventListener('click', startNewConversation);

// Textarea auto-resize and Enter-to-send
const chatInput = document.getElementById('chat-input');
chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('chat-form').dispatchEvent(new Event('submit'));
    }
});
