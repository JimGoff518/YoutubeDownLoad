# Dashboard Command Center - Design Doc

**Date:** 2026-02-19
**Status:** Approved

## Goal

Transform the Bill AI Machine from a chat-only interface into a **marketing command center** with a dashboard view, quick-action prompts, live PI/mass tort news ticker, and knowledge base stats — while keeping the existing chat experience intact.

## Architecture

**Frontend:** Vanilla HTML/CSS/JS (no frameworks, no build step)
**Backend:** Flask (server.py) — add `/api/stats` and `/api/news` endpoints
**Deployment:** Same Railway setup, no infra changes

## Layout

```
+----------------+------------------------------------------+
|   SIDEBAR      |  [Dashboard]  [Chat]    <- tab nav        |
|                |                                           |
|  News Ticker   |  Main content area                       |
|  (PI/mass tort |  (Dashboard view OR Chat view)            |
|   headlines)   |                                           |
|                |                                           |
|  Conversations |                                           |
|  (when Chat)   |                                           |
+----------------+------------------------------------------+
```

### Sidebar
- **Top:** News ticker (always visible) — scrolling PI/mass tort headlines
- **Bottom:** Conversation list (visible in Chat view only)

### Main Area
- SPA-style view switching (no page reloads)
- Dashboard view: stats cards + quick-action prompts
- Chat view: existing chat experience (unchanged)

## Dashboard View

### Stats Cards (top row)
- Episodes Indexed (from takeaways_index.json total_episodes)
- Sources Tracked (count of unique SOURCE_DISPLAY_NAMES)
- Topics Covered (count from takeaways topic set)
- Total Conversations (from database)

### Quick-Action Prompts (below stats)
Clickable cards that switch to Chat view and auto-fire the prompt:
- Weekly Marketing Briefing
- Content Calendar Ideas
- Competitive Intel Report
- Intake Optimization Review
- SEO Strategy Update
- Draft an SOP

## News Ticker

### Data Sources
- **Google News RSS** — queries: "personal injury law", "mass tort"
- **Reddit JSON API** — r/lawyers, r/personalinjury (public, no auth)

### Backend
- `/api/news` endpoint fetches and caches feeds
- 30-minute cache to avoid rate limits
- Returns: `[{title, url, source, published_ago}]`

### Frontend
- Sidebar panel with headline list
- Each headline: title (clickable) + source label + time ago
- Auto-refreshes every 30 minutes

## Files Modified
- `server.py` — add `/api/stats`, `/api/news` endpoints
- `templates/index.html` — restructure layout with tab nav
- `static/style.css` — dashboard, news ticker, tab styles
- `static/app.js` — view switching, stats/news fetching

## Files NOT Modified
- `rag.py` — no changes needed (read-only for stats)
- `database.py` — no changes needed (existing API sufficient)
