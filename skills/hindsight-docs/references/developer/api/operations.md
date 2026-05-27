
# Operations

Hindsight runs several maintenance and ingestion tasks asynchronously instead of blocking the API call that triggers them. These tasks share a single queue (`async_operations`) and a single worker pool, and the same REST endpoints — list, status, cancel, retry — work across every type.

This page explains each operation type, when it fires, and how to inspect or manage it.

{/* Import raw source files */}

> **💡 Prerequisites**
> 
Make sure you've completed the [Quick Start](./quickstart) and understand [how retain works](./retain).
## How operations work

When an API call needs background work, the request handler writes a row to the `async_operations` table with `status=pending` and returns immediately. A worker (running either in-process inside the API by default, or as a dedicated service — see [Services - Worker Service](../services#worker-service)) polls the table, claims pending rows, executes the corresponding handler, and marks the row `completed` or `failed`.

By default, every operation runs in-process: no external queue, no extra process to deploy. The same code paths support scaling out to dedicated worker processes when throughput demands it.

### Lifecycle

| Status | Meaning |
|--------|---------|
| `pending` | The row is queued. Either no worker has picked it up yet, or an extension has parked it via `next_retry_at` in the future (e.g., for backpressure). |
| `processing` | A worker has claimed the row and is actively running the handler. |
| `completed` | The handler returned successfully. |
| `failed` | The handler raised. `error_message` carries the reason; you can re-queue with `POST /…/retry`. |
| `cancelled` | The operation was cancelled via `DELETE /…/operations/{id}` before a worker picked it up. Cancelling a `processing` operation is not supported. |

The worker retries failed operations up to `HINDSIGHT_API_WORKER_MAX_RETRIES` times before settling on `failed`. Deterministic failures (e.g., invalid embedding dimensions, integrity violations) skip retries — they won't succeed by re-running.

## Operation types

Every operation has an `operation_type` in the database and a `task_type` in the payload. They're usually the same.

### `retain`

Submitted by `POST /v1/default/banks/{bank_id}/memories` with `async=true`, or by the multi-item `retain_batch` call. The handler runs the same pipeline as a synchronous retain: fact extraction (LLM), embedding generation, entity resolution, and link creation (temporal, semantic).

Use async retain when you're ingesting thousands of items and don't want the HTTP call to hold for minutes. The `operation_id` in the response lets you poll for completion.

#### Parent op: `retain_batch`

For large submissions, Hindsight automatically splits the input into sub-batches and creates a single `retain_batch` parent operation that tracks the children. The parent's status reflects the aggregate — `pending` until at least one child is running, `processing` while children execute, `completed` once every child has finished, `failed` if any child failed. Each child is itself a `retain` operation linked to the parent, so you can drill in for per-batch error messages.

When you list operations, the parent and its children all appear by default. Pass `exclude_parents=true` to hide the aggregate rows and show only individual `retain` jobs.

### `file_convert_retain`

Submitted by file upload endpoints. The handler runs MIME-specific conversion (PDF → text, DOCX → text, etc.) and then passes the extracted text into the retain pipeline. Failures here are **non-retryable** by default — a corrupted PDF or missing OCR won't improve on rerun, so the operation goes straight to `failed`.

Which parser runs (`markitdown`, `iris`, or `llama_parse`) is selected per deployment via `HINDSIGHT_API_FILE_PARSER`, and clients can override it per request — see [Configuration → File Processing](../configuration#file-processing).

### `consolidation`

Produces **observations** from new world/experience memories. See [Observations](../observations) for what they are and how they're synthesized.

Triggered automatically:

- After every retain that added world/experience facts (gated by per-bank `enable_auto_consolidation` and `enable_observations`).
- After deletes that invalidated existing observations (the source memory disappeared → derived observations are stale → re-run with the surviving co-source memories).
- Manually via `POST /v1/default/banks/{bank_id}/consolidate`. Pass `observation_scopes` to consolidate only memories matching specific tag combinations.

**Bank-deduped**: while one `consolidation` job is pending for a bank, repeat submits return the existing `operation_id` instead of stacking. Once the job starts processing, the next submit becomes the next pending slot.

### `refresh_mental_model`

A mental model has a `source_query` that defines which memories it summarizes. The handler re-runs that query, re-summarizes the result, and updates the model's content in place.

Triggered either manually via `POST /v1/default/banks/{bank_id}/mental-models/{id}/refresh`, or automatically by the auto-refresh schedule for mental models that have one configured.

### `graph_maintenance`

Reconciles derived state that becomes stale after a mutation. Bank-deduped at submit time, so concurrent triggers against the same bank coalesce into one drain.

The queue is keyed by `(bank_id, kind, target_id)` and dispatched by `kind`. Today the only kind is `relink_unit`; future cleanups (orphan entity pruning, stale cooccurrences) will ride on the same surface without a new task type.

#### Kind: `relink_unit`

Tops up a memory unit's outgoing temporal/semantic links after one of its top-K neighbours is deleted.

**Why:** the retain pipeline picks each new unit's top neighbours from a capped probe (20 temporal, 50 semantic). When one of those neighbours is later deleted, the FK cascade removes the link but nothing re-evaluates whether a different neighbour (originally just past the cut-off) should take its place — so surviving units sit permanently under-capped, which degrades graph-expansion recall.

**Triggers:** any delete that removes memory_units — `DELETE /documents/{id}`, `DELETE /memories/{id}`, and re-retaining an existing `document_id` (the upsert path). A full bank wipe (`delete_bank`) is a no-op: there are no surviving units to top up.

### `webhook_delivery`

After certain operations complete (e.g., consolidation finishing on a bank with a registered webhook), Hindsight enqueues a `webhook_delivery` task. The handler POSTs the payload to the configured URL and retries on transient failures.

## Endpoints

All paths below are scoped by `bank_id`.

### List operations

```bash
GET /v1/default/banks/{bank_id}/operations
```

Query parameters:

| Param | Description |
|-------|-------------|
| `status` | Filter by `pending`, `processing`, `completed`, `failed`, `cancelled`. |
| `type` | Filter by `retain`, `file_convert_retain`, `consolidation`, `refresh_mental_model`, `graph_maintenance`, `webhook_delivery`. |
| `limit` | 1–100, default 20. |
| `offset` | Pagination offset. |
| `exclude_parents` | Exclude parent batch operations from results (large `retain_batch` calls create one parent + N children). |

### Python

```python
# Section 'operations-list' not found in api/operations.py
```

### Node.js

```javascript
// List recent operations for a bank (default: 20 most recent).
const { data: recent } = await sdk.listOperations({
    client: apiClient,
    path: { bank_id: 'my-bank' },
});
for (const op of recent.operations) {
    console.log(op.id, op.task_type, op.status);
}

// Filter by status and type.
const { data: pendingRecompute } = await sdk.listOperations({
    client: apiClient,
    path: { bank_id: 'my-bank' },
    query: { status: 'pending', type: 'graph_maintenance' },
});

// Hide retain_batch parent rows (show only individual child retain jobs).
const { data: flat } = await sdk.listOperations({
    client: apiClient,
    path: { bank_id: 'my-bank' },
    query: { exclude_parents: true },
});
```

### CLI

```bash
# List recent operations for a bank (default: 20 most recent).
hindsight operation list $BANK_ID
```

### Go

```go
# Section 'operations-list' not found in api/operations.go
```

`items_count` is operation-specific — non-zero only for retain-shaped operations (it counts content items in the submission).

### Get operation status

### Python

```python
# Section 'operations-get' not found in api/operations.py
```

### Node.js

```javascript
const { data: status } = await sdk.getOperationStatus({
    client: apiClient,
    path: { bank_id: 'my-bank', operation_id: '550e8400-e29b-41d4-a716-446655440000' },
});
console.log(status.status, status.error_message);

// Include the submission payload (can be large for retain batches).
const { data: detailed } = await sdk.getOperationStatus({
    client: apiClient,
    path: { bank_id: 'my-bank', operation_id: '550e8400-e29b-41d4-a716-446655440000' },
    query: { include_payload: true },
});
```

### CLI

```bash
hindsight operation get $BANK_ID $OPERATION_ID
```

### Go

```go
# Section 'operations-get' not found in api/operations.go
```

### Cancel a pending operation

Returns `409` if the operation is already in `processing`, `completed`, or `failed` state.

### Python

```python
# Section 'operations-cancel' not found in api/operations.py
```

### Node.js

```javascript
// Cancel a pending operation before a worker claims it.
// Returns 409 if the operation is already processing/completed/failed.
await sdk.cancelOperation({
    client: apiClient,
    path: { bank_id: 'my-bank', operation_id: '550e8400-e29b-41d4-a716-446655440000' },
});
```

### CLI

```bash
# Cancel a pending operation before a worker claims it.
hindsight operation cancel $BANK_ID $OPERATION_ID
```

### Go

```go
# Section 'operations-cancel' not found in api/operations.go
```

### Retry a failed operation

The row's status resets to `pending` and the worker picks it up again. Returns `409` if the operation isn't in `failed` or `cancelled` state.

### Python

```python
# Section 'operations-retry' not found in api/operations.py
```

### Node.js

```javascript
// Re-queue a failed (or cancelled) operation.
// Returns 409 if the operation isn't in failed/cancelled state.
await sdk.retryOperation({
    client: apiClient,
    path: { bank_id: 'my-bank', operation_id: '550e8400-e29b-41d4-a716-446655440000' },
});
```

### CLI

```bash
# Re-queue a failed (or cancelled) operation.
hindsight operation retry $BANK_ID $OPERATION_ID
```

### Go

```go
# Section 'operations-retry' not found in api/operations.go
```

## Async retain example

Submit a batch asynchronously and poll until the operation completes:

### Python

```python
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
```

### Node.js

```javascript
// Submit a large batch asynchronously — the call returns immediately with an
// operation_id you can poll.
const submission = await client.retainBatch('my-bank', [
    { content: 'Alice joined Google in 2023' },
    { content: 'Bob prefers Python over JavaScript' },
], { async: true });
const operationId = submission.operation_id;

while (true) {
    const { data: s } = await sdk.getOperationStatus({
        client: apiClient,
        path: { bank_id: 'my-bank', operation_id: operationId },
    });
    if (['completed', 'failed', 'cancelled'].includes(s.status)) {
        console.log(`finished: ${s.status}`);
        break;
    }
    await new Promise((r) => setTimeout(r, 2000));
}
```

### Go

```go
# Section 'operations-async-retain' not found in api/operations.go
```

## Worker tuning

Each worker has a single concurrency budget (`HINDSIGHT_API_WORKER_MAX_SLOTS`, default 10) shared across all operation types. Per-type slot reservations (`HINDSIGHT_API_WORKER_<TYPE>_MAX_SLOTS`) carve out guaranteed capacity within that budget; remaining slots form a shared pool any type can use. See [Configuration → Worker Configuration](../configuration#worker-configuration) for the full table.

For most deployments the defaults are fine. Reserve slots for an operation type if you've seen it starved by a flood of another type (e.g., a long file_convert_retain blocking graph_maintenance on a deletion-heavy workload).

## Next Steps

- [**Documents**](./documents) — Track document sources
- [**Memory Banks**](./memory-banks) — Configure bank settings
