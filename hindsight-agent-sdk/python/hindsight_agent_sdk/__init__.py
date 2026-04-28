"""Hindsight Agent SDK — self-learning knowledge pages for AI agents.

Opinionated wrapper over the Hindsight client for managing wiki pages,
recalling memories, and ingesting documents. Designed to be embedded in
harness plugins (OpenClaw, Hermes, Claude Code, Codex, etc.).

Usage:
    from hindsight_agent_sdk import AgentWiki

    wiki = AgentWiki(api_url="http://localhost:8888", bank_id="my-bank")
    pages = wiki.list_pages()
    wiki.create_page("prefs", "User Preferences", "What does the user prefer?")
    results = wiki.recall("SEO best practices")
    wiki.ingest("Guide", content="...")
"""

from hindsight_agent_sdk.wiki import AgentWiki

__all__ = ["AgentWiki"]
