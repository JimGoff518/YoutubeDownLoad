// =============================================================================
// app.js - Bill AI Machine: Marketing Command Center
// Dashboard + Chat with news ticker, stats, and quick-action prompts
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
    isStreaming: false,
    currentView: 'dashboard' // 'dashboard' or 'chat'
};

// -----------------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------------
(function init() {
    const saved = localStorage.getItem('currentConversationId');
    if (saved) state.currentConversationId = parseInt(saved);

    // Set up tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.dataset.view));
    });

    // Set up quick-action cards
    document.querySelectorAll('.action-card').forEach(card => {
        card.addEventListener('click', () => {
            const prompt = card.dataset.prompt;
            if (prompt) {
                switchView('chat');
                startNewConversation();
                // Small delay to let the view switch render
                setTimeout(() => sendMessage(prompt), 100);
            }
        });
    });

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

    // Load initial data
    fetchConversations().then(() => {
        if (state.currentConversationId) {
            loadConversation(state.currentConversationId);
        }
    });
    fetchStats();
    fetchNews();
    loadRefreshBanner();

    // Refresh news every 30 minutes
    setInterval(fetchNews, 30 * 60 * 1000);
})();


// -----------------------------------------------------------------------------
// View Switching
// -----------------------------------------------------------------------------

function switchView(viewName) {
    state.currentView = viewName;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`${viewName}-view`).classList.add('active');

    // Show/hide conversations section in sidebar
    const convSection = document.getElementById('conversations-section');
    convSection.style.display = viewName === 'chat' ? 'block' : 'none';
}


// -----------------------------------------------------------------------------
// Dashboard: Stats
// -----------------------------------------------------------------------------

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        animateNumber('stat-episodes', data.episodes);
        animateNumber('stat-sources', data.sources);
        animateNumber('stat-topics', data.topics);
        animateNumber('stat-conversations', data.conversations);
    } catch (e) {
        console.error('Failed to fetch stats:', e);
    }
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const duration = 600;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * eased);
        el.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}


// -----------------------------------------------------------------------------
// Sidebar: News Ticker
// -----------------------------------------------------------------------------

async function fetchNews() {
    const container = document.getElementById('news-ticker');
    try {
        const res = await fetch('/api/news');
        const items = await res.json();

        if (items.length === 0) {
            container.innerHTML = '<div class="news-loading">No news available</div>';
            return;
        }

        container.innerHTML = items.map(item => `
            <a class="news-item" href="${escapeAttr(item.url)}" target="_blank" rel="noopener">
                <div class="news-title">${escapeHtml(item.title)}</div>
                <div class="news-meta">${escapeHtml(item.source)} ${item.published_ago ? '&bull; ' + escapeHtml(item.published_ago) : ''}</div>
            </a>
        `).join('');
    } catch (e) {
        console.error('Failed to fetch news:', e);
        container.innerHTML = '<div class="news-loading">Unable to load news</div>';
    }
}


// -----------------------------------------------------------------------------
// Conversation API Helpers
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

    // Make sure we're in chat view
    if (state.currentView !== 'chat') {
        switchView('chat');
    }

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
                <h2>What can I help with?</h2>
                <p class="empty-state-subtitle">Type your question below, or go to the Dashboard for quick actions.</p>
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

function escapeAttr(text) {
    return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
// Dashboard: Refresh Knowledge Base
// -----------------------------------------------------------------------------

async function triggerRefresh() {
    const btn = document.getElementById('refresh-btn');
    const status = document.getElementById('refresh-status');
    btn.disabled = true;
    btn.textContent = 'Refreshing...';
    status.textContent = 'Checking sources for new episodes...';

    try {
        const resp = await fetch('/api/refresh', { method: 'POST' });
        if (resp.status === 409) {
            status.textContent = 'Refresh already running.';
            return;
        }
        // Poll for completion
        const poll = setInterval(async () => {
            const s = await fetch('/api/refresh/status').then(r => r.json());
            if (!s.running) {
                clearInterval(poll);
                btn.disabled = false;
                btn.textContent = 'Refresh Knowledge Base';
                if (s.last_result && s.last_result.episodes_ingested !== undefined) {
                    status.textContent =
                        `Done! ${s.last_result.episodes_ingested} new episodes ingested, ` +
                        `${s.last_result.takeaways_extracted} takeaways extracted.`;
                    fetchStats(); // Refresh dashboard stats
                } else if (s.last_result && s.last_result.error) {
                    status.textContent = 'Error: ' + s.last_result.error;
                }
            }
        }, 5000);
    } catch (e) {
        status.textContent = 'Error: ' + e.message;
        btn.disabled = false;
        btn.textContent = 'Refresh Knowledge Base';
    }
}


// -----------------------------------------------------------------------------
// Dashboard: Refresh Notification Banner
// -----------------------------------------------------------------------------

async function loadRefreshBanner() {
    try {
        const data = await fetch('/api/refresh/latest').then(r => r.json());
        if (!data || !data.episodes_ingested) return;

        // Only show if refresh was within last 7 days
        const refreshDate = new Date(data.finished_at);
        const daysSince = (Date.now() - refreshDate) / (1000 * 60 * 60 * 24);
        if (daysSince > 7) return;

        const banner = document.getElementById('refresh-banner');
        const text = document.getElementById('refresh-banner-text');
        const when = daysSince < 1 ? 'today' : `${Math.round(daysSince)}d ago`;
        text.textContent =
            `${data.episodes_ingested} new episodes ingested ${when} ` +
            `from ${data.sources_checked} sources`;
        banner.style.display = 'flex';
    } catch (e) { /* ignore */ }
}

function dismissBanner() {
    document.getElementById('refresh-banner').style.display = 'none';
}
