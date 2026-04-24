"""hindsight-agent ingest — upload a resource directly into an agent's memory."""

from __future__ import annotations

import json
import sys

import click

from ..api import HindsightAPI
from ..config import get_agent


@click.command("ingest-document")
@click.argument("agent_id")
@click.argument("title")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), default=None, help="Read content from a file")
@click.option("--content", "-c", "inline_content", default=None, help="Inline content string")
def ingest(agent_id: str, title: str, file_path: str | None, inline_content: str | None) -> None:
    """Ingest a resource into an agent's memory.

    AGENT_ID identifies which agent's bank to retain into.
    TITLE is used as the document ID for upsert behavior.

    Content is read from --file, --content, or stdin.

    Examples:
      hindsight-agent ingest my-agent "SEO Best Practices" -f seo-guide.md
      hindsight-agent ingest my-agent "Style Guide" -c "Always use active voice..."
      cat notes.txt | hindsight-agent ingest my-agent "Meeting Notes"
    """
    if file_path:
        with open(file_path) as f:
            content = f.read()
    elif inline_content:
        content = inline_content
    else:
        content = sys.stdin.read()

    if not content.strip():
        raise click.ClickException("No content provided. Use --file, --content, or pipe to stdin.")

    cfg = get_agent(agent_id)
    api = HindsightAPI(cfg.api_url, api_token=cfg.api_token)

    # Use title as document_id (slug) for upsert
    doc_id = title.lower().replace(" ", "-")

    result = api.retain(cfg.bank_id, content, document_id=doc_id)
    click.echo(json.dumps(result))
