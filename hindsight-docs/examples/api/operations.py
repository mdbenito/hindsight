#!/usr/bin/env python3
"""
Operations API examples for Hindsight (async tracking).
Run: python examples/api/operations.py
"""
import asyncio
import os
import time

from hindsight_client import Hindsight

HINDSIGHT_URL = os.getenv("HINDSIGHT_API_URL", "http://localhost:8888")

# =============================================================================
# Setup (not shown in docs)
# =============================================================================
client = Hindsight(base_url=HINDSIGHT_URL)


async def _examples():
    # [docs:operations-list]
    # List recent operations for a bank (default: 20 most recent).
    result = await client.operations.list_operations("my-bank")
    for op in result.operations:
        print(op.id, op.task_type, op.status)

    # Filter by status and type.
    pending_recompute = await client.operations.list_operations(
        "my-bank", status="pending", type="graph_maintenance"
    )

    # Hide retain_batch parent rows (show only individual child retain jobs).
    flat = await client.operations.list_operations("my-bank", exclude_parents=True)
    # [/docs:operations-list]

    # [docs:operations-get]
    status = await client.operations.get_operation_status(
        "my-bank", "550e8400-e29b-41d4-a716-446655440000"
    )
    print(status.status, status.error_message)

    # Include the submission payload (can be large for retain batches).
    detailed = await client.operations.get_operation_status(
        "my-bank", "550e8400-e29b-41d4-a716-446655440000", include_payload=True
    )
    # [/docs:operations-get]

    # [docs:operations-cancel]
    # Cancel a pending operation before a worker claims it.
    # Returns 409 if the operation is already processing/completed/failed.
    await client.operations.cancel_operation(
        "my-bank", "550e8400-e29b-41d4-a716-446655440000"
    )
    # [/docs:operations-cancel]

    # [docs:operations-retry]
    # Re-queue a failed (or cancelled) operation.
    # Returns 409 if the operation isn't in failed/cancelled state.
    await client.operations.retry_operation(
        "my-bank", "550e8400-e29b-41d4-a716-446655440000"
    )
    # [/docs:operations-retry]


# [docs:operations-async-retain]
# Submit a large batch asynchronously — the call returns immediately with an
# operation_id you can poll.
submission = client.retain_batch(
    bank_id="my-bank",
    items=[
        {"content": "Alice joined Google in 2023"},
        {"content": "Bob prefers Python over JavaScript"},
    ],
    retain_async=True,
)
operation_id = submission.operation_id


async def _wait_for_completion() -> None:
    while True:
        status = await client.operations.get_operation_status("my-bank", operation_id)
        if status.status in ("completed", "failed", "cancelled"):
            print(f"finished: {status.status}")
            return
        await asyncio.sleep(2)


asyncio.run(_wait_for_completion())
# [/docs:operations-async-retain]


asyncio.run(_examples())
