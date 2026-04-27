"""Hindsight API server launcher for Android.

Starts an embedded PostgreSQL instance and runs the real hindsight-api-slim
FastAPI server on localhost. Called from Kotlin via Chaquopy.
"""

from __future__ import annotations

import os
import sys
import threading

_server_thread: threading.Thread | None = None
_server_instance = None
_pg_manager = None


def start_server(
    files_dir: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    port: int = 8741,
    assets_dir: str | None = None,
) -> str:
    """Start embedded PostgreSQL + Hindsight API server.

    Called from Kotlin via Chaquopy.

    Args:
        files_dir: App's internal files directory
        api_key: OpenAI (or other LLM provider) API key
        model: LLM model name
        port: Port for the API server
        assets_dir: Path to extracted APK assets (contains postgres-arm64.tar.gz)

    Returns:
        Status message
    """
    global _server_thread, _server_instance, _pg_manager

    # 1. Start PostgreSQL
    from .pg_manager import setup_postgres

    _pg_manager = setup_postgres(files_dir, assets_dir)
    db_url = _pg_manager.database_url

    # 2. Configure Hindsight via env vars
    os.environ["HINDSIGHT_API_DATABASE_URL"] = db_url
    os.environ["HINDSIGHT_API_LLM_PROVIDER"] = "openai"
    os.environ["HINDSIGHT_API_LLM_API_KEY"] = api_key
    os.environ["HINDSIGHT_API_LLM_MODEL"] = model
    os.environ["HINDSIGHT_API_HOST"] = "127.0.0.1"
    os.environ["HINDSIGHT_API_PORT"] = str(port)
    # Use OpenAI embeddings (no local model on Android)
    os.environ["HINDSIGHT_API_EMBEDDINGS_PROVIDER"] = "openai"
    os.environ["HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY"] = api_key
    # Disable local ML models (too heavy for phone)
    os.environ["HINDSIGHT_API_RERANKER_PROVIDER"] = "none"
    # Disable features not needed for POC
    os.environ["HINDSIGHT_API_ENABLE_MCP"] = "false"

    # 3. Add hindsight-api-slim to Python path if not already
    api_slim_path = os.path.join(files_dir, "hindsight-api-slim")
    if os.path.exists(api_slim_path) and api_slim_path not in sys.path:
        sys.path.insert(0, api_slim_path)

    # 4. Start the real Hindsight API server
    import uvicorn

    from hindsight_api.main import create_app

    app = create_app()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    _server_instance = uvicorn.Server(config)

    def _run():
        _server_instance.run()

    _server_thread = threading.Thread(target=_run, daemon=True)
    _server_thread.start()

    return f"Server starting on port {port}, DB: {db_url}"


def stop_server() -> None:
    """Stop the Hindsight API server and PostgreSQL."""
    global _server_instance, _pg_manager
    if _server_instance:
        _server_instance.should_exit = True
        _server_instance = None
    if _pg_manager:
        _pg_manager.stop()
        _pg_manager = None


def is_running() -> bool:
    """Check if the server is running."""
    return _server_instance is not None and _server_instance.started


def get_status() -> dict:
    """Get server and database status."""
    return {
        "server_running": is_running(),
        "pg_running": _pg_manager.is_running() if _pg_manager else False,
        "db_url": _pg_manager.database_url if _pg_manager else None,
    }
