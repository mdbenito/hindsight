"""AgentWiki — opinionated wiki interface over Hindsight mental models.

All page creation uses these defaults:
  - mode: delta (only processes new observations per refresh)
  - refresh_after_consolidation: true (auto-updates after each cycle)
  - exclude_mental_models: true (pages don't feed into each other)
  - fact_types: [observation] (synthesizes from observations only)
"""

from __future__ import annotations

from typing import Any

from hindsight_client import HindsightClient


# Opinionated defaults for wiki pages
_WIKI_TRIGGER = {
    "mode": "delta",
    "refresh_after_consolidation": True,
    "exclude_mental_models": True,
    "fact_types": ["observation"],
}


class AgentWiki:
    """High-level wiki interface for AI agent knowledge pages.

    Wraps HindsightClient with opinionated defaults for self-learning agents.
    Each plugin creates an instance with its resolved bank_id and passes it
    to the agent via tools, hooks, or scripts.

    Args:
        api_url: Hindsight API URL.
        bank_id: Memory bank identifier.
        api_token: Optional API token for authenticated instances.
    """

    def __init__(
        self,
        api_url: str,
        bank_id: str,
        api_token: str | None = None,
    ) -> None:
        self._bank_id = bank_id
        self._client = HindsightClient(
            api_url=api_url,
            api_token=api_token,
        )

    @property
    def bank_id(self) -> str:
        return self._bank_id

    # ── Pages ────────────────────────────────────────────

    def list_pages(self) -> list[dict[str, Any]]:
        """List all wiki pages."""
        result = self._client.mental_models.list_mental_models(
            bank_id=self._bank_id,
        )
        return result.items or []

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Get a specific wiki page by ID."""
        return self._client.mental_models.get_mental_model(
            bank_id=self._bank_id,
            mental_model_id=page_id,
        )

    def create_page(
        self,
        page_id: str,
        name: str,
        source_query: str,
        *,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Create a wiki page with opinionated defaults.

        Args:
            page_id: Unique page identifier (lowercase with hyphens).
            name: Human-readable page name.
            source_query: The question the system re-asks on every
                consolidation to rebuild this page's content.
            max_tokens: Maximum tokens for synthesized content.
        """
        return self._client.mental_models.create_mental_model(
            bank_id=self._bank_id,
            body={
                "id": page_id,
                "name": name,
                "source_query": source_query,
                "max_tokens": max_tokens,
                "trigger": _WIKI_TRIGGER,
            },
        )

    def update_page(
        self,
        page_id: str,
        *,
        name: str | None = None,
        source_query: str | None = None,
    ) -> dict[str, Any]:
        """Update a wiki page's name or source query."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if source_query is not None:
            body["source_query"] = source_query
        if not body:
            raise ValueError("At least one of name or source_query must be provided")
        return self._client.mental_models.update_mental_model(
            bank_id=self._bank_id,
            mental_model_id=page_id,
            body=body,
        )

    def delete_page(self, page_id: str) -> None:
        """Delete a wiki page."""
        self._client.mental_models.delete_mental_model(
            bank_id=self._bank_id,
            mental_model_id=page_id,
        )

    # ── Recall ───────────────────────────────────────────

    def recall(
        self,
        query: str,
        *,
        max_results: int = 10,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search agent memories."""
        return self._client.recall(
            bank_id=self._bank_id,
            query=query,
            max_results=max_results,
            types=types,
        )

    # ── Ingest ───────────────────────────────────────────

    def ingest(
        self,
        title: str,
        *,
        content: str | None = None,
        file_path: str | None = None,
    ) -> dict[str, Any]:
        """Ingest a document into agent memory.

        The title is slugified to a document_id for upsert behavior.

        Args:
            title: Document title (used as document ID).
            content: Inline content string.
            file_path: Path to a file to read content from.
        """
        if file_path:
            with open(file_path) as f:
                content = f.read()
        if not content or not content.strip():
            raise ValueError("No content provided")

        doc_id = title.lower().replace(" ", "-")
        return self._client.retain(
            bank_id=self._bank_id,
            content=content,
            document_id=doc_id,
            retain_async=True,
        )

    # ── Documents ────────────────────────────────────────

    def list_documents(self) -> list[dict[str, Any]]:
        """List documents retained for this agent."""
        result = self._client.documents.list_documents(
            bank_id=self._bank_id,
        )
        return result.documents or result.items or []

    # ── Tool Schemas ─────────────────────────────────────

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        """Return tool schemas for harness registration.

        Plugins can use these to register wiki tools with their harness.
        """
        return [
            {
                "name": "hindsight_wiki_list",
                "description": "List all knowledge pages. Returns page names, IDs, and content.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "hindsight_wiki_get",
                "description": "Get a specific knowledge page by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string", "description": "Page identifier"},
                    },
                    "required": ["page_id"],
                },
            },
            {
                "name": "hindsight_wiki_create",
                "description": (
                    "Create a new knowledge page. The source_query is a question the "
                    "system re-asks after every consolidation to rebuild the page."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Page ID (lowercase with hyphens, e.g. 'user-preferences')",
                        },
                        "name": {"type": "string", "description": "Human-readable page name"},
                        "source_query": {
                            "type": "string",
                            "description": "Synthesis query — the question that rebuilds this page",
                        },
                    },
                    "required": ["page_id", "name", "source_query"],
                },
            },
            {
                "name": "hindsight_wiki_update",
                "description": "Update a knowledge page's name or source query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string", "description": "Page identifier"},
                        "name": {"type": "string", "description": "New page name"},
                        "source_query": {"type": "string", "description": "New synthesis query"},
                    },
                    "required": ["page_id"],
                },
            },
            {
                "name": "hindsight_wiki_delete",
                "description": "Delete a knowledge page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string", "description": "Page identifier"},
                    },
                    "required": ["page_id"],
                },
            },
            {
                "name": "hindsight_wiki_recall",
                "description": "Search agent memories for specific facts, numbers, or details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search query"},
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hindsight_wiki_ingest",
                "description": (
                    "Upload a document into agent memory. Pass raw content — "
                    "never summarize before ingesting. The system handles extraction."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Document title (used as ID)"},
                        "content": {"type": "string", "description": "Document content"},
                    },
                    "required": ["title", "content"],
                },
            },
        ]

    def handle_tool_call(self, tool_name: str, args: dict[str, Any]) -> str:
        """Dispatch a tool call and return JSON result.

        Plugins can use this as a unified handler for all wiki tools.
        """
        import json

        try:
            if tool_name == "hindsight_wiki_list":
                result = self.list_pages()
                return json.dumps({"pages": result})

            elif tool_name == "hindsight_wiki_get":
                result = self.get_page(args["page_id"])
                return json.dumps(result)

            elif tool_name == "hindsight_wiki_create":
                result = self.create_page(
                    args["page_id"], args["name"], args["source_query"]
                )
                return json.dumps(result)

            elif tool_name == "hindsight_wiki_update":
                result = self.update_page(
                    args["page_id"],
                    name=args.get("name"),
                    source_query=args.get("source_query"),
                )
                return json.dumps(result)

            elif tool_name == "hindsight_wiki_delete":
                self.delete_page(args["page_id"])
                return json.dumps({"success": True})

            elif tool_name == "hindsight_wiki_recall":
                result = self.recall(
                    args["query"],
                    max_results=args.get("max_results", 10),
                )
                return json.dumps(result)

            elif tool_name == "hindsight_wiki_ingest":
                result = self.ingest(args["title"], content=args["content"])
                return json.dumps(result)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            return json.dumps({"error": str(e)})
