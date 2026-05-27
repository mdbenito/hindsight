#!/bin/bash
# Operations API examples for Hindsight CLI
# Run: bash examples/api/operations.sh

set -e

BANK_ID="my-bank"
OPERATION_ID="550e8400-e29b-41d4-a716-446655440000"

# =============================================================================
# Doc Examples
# =============================================================================

# [docs:operations-list]
# List recent operations for a bank (default: 20 most recent).
hindsight operation list $BANK_ID
# [/docs:operations-list]


# [docs:operations-get]
hindsight operation get $BANK_ID $OPERATION_ID
# [/docs:operations-get]


# [docs:operations-cancel]
# Cancel a pending operation before a worker claims it.
hindsight operation cancel $BANK_ID $OPERATION_ID
# [/docs:operations-cancel]


# [docs:operations-retry]
# Re-queue a failed (or cancelled) operation.
hindsight operation retry $BANK_ID $OPERATION_ID
# [/docs:operations-retry]
