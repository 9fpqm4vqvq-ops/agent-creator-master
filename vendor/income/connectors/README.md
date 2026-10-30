# Integration boundary (optional, not preconnected)

- **YouTube Data API**: public video/channel data may help demand research, but **not** revenue, actual buyer conversion, or Iraq merchant eligibility. Set `YOUTUBE_API_KEY` and use `python connectors/youtube_public.py search --query "..."` when needed; quota and API availability apply. This tool never downloads video files.
- **Google Search/Google Trends/Google Alerts**: use authorized browser/manual workflows first; no undocumented scraper or guaranteed free programmatic API is bundled.
- **Crawl4AI**: optional third-party web extraction. Respect robots.txt, terms, privacy, and rate limits. Not configured here.
- **LangGraph**: optional separate orchestration runtime; Claude Code subagents work without it. No implied background service.
- **n8n**: optional self-hosted monitoring and scheduling; requires a secured external instance, explicit permissions, and manual setup.
- **Metabase**: optional visualization of exported reports; this project supplies a SQLite store but does not include a Metabase server.

Do not enter sensitive authentication tokens into agent chat or commit `.env`. For payment research, use publicly documented provider pages, never authenticate into somebody else's account.
