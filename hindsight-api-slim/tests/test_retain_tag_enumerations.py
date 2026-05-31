"""End-to-end integration tests for tag_enumerations.

These tests exercise the full retain → store → recall pipeline to prove
that LLM-emitted tag classifications survive into storage and that the
recall path filters on them.

LLM stubbing pattern: monkeypatch ``LLMConfig.call`` (class-level) so that
all per-chunk extraction calls in the engine route through our fake. The
fake dispatches by ``scope``: ``retain_extract_facts`` returns the canned
facts we want stored; everything else (notably ``consolidation``) gets a
safe no-op response so consolidation doesn't crash during the auto-trigger
that runs after every retain.

This pattern mirrors ``test_extract_facts_from_text_merges_llm_tags_onto_fact_object``
in ``test_tag_enumerations_unit.py``, which is the smallest LLM-mocking
test in this slice — extending it to a full retain → recall round-trip.
"""

import uuid
from typing import Any

import pytest

from hindsight_api.engine.llm_wrapper import LLMConfig
from hindsight_api.engine.memory_engine import MemoryEngine
from hindsight_api.engine.response_models import TokenUsage


def _user_message_text(messages: list[dict[str, Any]]) -> str:
    """Extract the user-role content from a messages array."""
    for m in messages:
        if m.get("role") == "user":
            return m.get("content", "") or ""
    return ""


def _make_fake_call(scripted_facts_for_chunk):
    """Build a fake LLMConfig.call that:
      - For scope='retain_extract_facts': finds which scripted chunk's
        text appears in the user message and returns the matching facts.
      - For scope='consolidation': returns an empty creates/updates/deletes
        envelope so the auto-consolidation that fires after retain doesn't
        crash on a missing payload.
      - For any other scope: returns a minimal-but-valid object so we
        never accidentally exercise a real LLM.

    Args:
        scripted_facts_for_chunk: dict mapping a substring that uniquely
            identifies a chunk → list of fact dicts to return for that chunk.
    """

    async def fake_call(self, *args, **kwargs):
        scope = kwargs.get("scope", "")
        return_usage = kwargs.get("return_usage", False)
        messages = kwargs.get("messages") or (args[0] if args else [])

        if scope == "retain_extract_facts":
            user_text = _user_message_text(messages)
            facts: list[dict[str, Any]] = []
            for marker, fact_list in scripted_facts_for_chunk.items():
                if marker in user_text:
                    facts = fact_list
                    break
            result: dict[str, Any] = {"facts": facts}
            if return_usage:
                return result, TokenUsage()
            return result

        if scope == "consolidation":
            response_format = kwargs.get("response_format")
            empty: Any
            if response_format is not None:
                try:
                    empty = response_format(creates=[], updates=[], deletes=[])
                except Exception:
                    empty = {"creates": [], "updates": [], "deletes": []}
            else:
                empty = {"creates": [], "updates": [], "deletes": []}
            if return_usage:
                return empty, TokenUsage()
            return empty

        # Any other scope: best-effort empty/default response.
        response_format = kwargs.get("response_format")
        if response_format is not None:
            try:
                fallback: Any = response_format()
            except Exception:
                fallback = {}
        else:
            fallback = ""
        if return_usage:
            return fallback, TokenUsage()
        return fallback

    return fake_call


# ---------------------------------------------------------------------------
# Test 1: per-retain tag_enumerations drive classification and survive recall
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_retain_tag_enumerations_drives_classification(memory: MemoryEngine, request_context, monkeypatch):
    """The PRD's CRM-feedback walkthrough.

    Retain a single transcript with a per-retain ``feedback`` enumeration
    (multi-values: behavior/style/execution). The mock LLM classifies each
    of three extracted facts into one of those buckets. Recall by
    ``tags=['feedback:behavior']`` returns only the behavior fact, and
    caller-supplied tags (``user:chris``) survive on every fact alongside
    the LLM-emitted ``feedback:*`` classifications.
    """
    transcript = (
        "Chris feedback transcript. "
        "First correction: ship without asking next time, just do it. "
        "Second correction: prefer concise wording, drop the preamble. "
        "Third correction: run the tests before pushing, every time."
    )

    scripted = {
        # Single chunk — match on any unique substring of the transcript.
        "Chris feedback transcript": [
            {
                "what": "User wants ship-without-asking behavior",
                "when": "during chat",
                "who": "user",
                "why": "wants speed",
                "fact_type": "world",
                "fact_kind": "conversation",
                "tags": {"feedback": ["behavior"]},
            },
            {
                "what": "User prefers concise wording without preamble",
                "when": "during chat",
                "who": "user",
                "why": "communication style preference",
                "fact_type": "world",
                "fact_kind": "conversation",
                "tags": {"feedback": ["style"]},
            },
            {
                "what": "User requires tests run before every push",
                "when": "during chat",
                "who": "user",
                "why": "execution discipline",
                "fact_type": "world",
                "fact_kind": "conversation",
                "tags": {"feedback": ["execution"]},
            },
        ],
    }

    monkeypatch.setattr(LLMConfig, "call", _make_fake_call(scripted), raising=True)

    bank_id = f"test-tag-enums-classify-{uuid.uuid4().hex[:8]}"
    try:
        await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)

        per_retain_enums = [
            {
                "namespace": "feedback",
                "description": "Type of correction",
                "type": "multi-values",
                "values": [
                    {"value": "behavior", "description": "process / sequencing"},
                    {"value": "style", "description": "tone, verbosity"},
                    {"value": "execution", "description": "tooling, discipline"},
                ],
            }
        ]

        # Caller-supplied tag (user:chris) must survive on each stored fact
        # alongside the LLM-emitted classification tags.
        result = await memory.retain_batch_async(
            bank_id=bank_id,
            contents=[
                {
                    "content": transcript,
                    "context": "CRM chat with Chris",
                    "tags": ["user:chris"],
                    "tag_enumerations": per_retain_enums,
                }
            ],
            request_context=request_context,
        )
        assert result and len(result[0]) == 3, f"expected 3 stored facts, got {result}"

        # Recall by feedback:behavior — should ONLY return the behavior fact.
        behavior_hits = await memory.recall_async(
            bank_id=bank_id,
            query="behavior corrections",
            tags=["feedback:behavior"],
            tags_match="any_strict",
            fact_type=["world"],
            request_context=request_context,
        )
        behavior_texts = [r.text for r in behavior_hits.results]
        assert any("ship-without-asking" in t for t in behavior_texts), (
            f"behavior recall must include the ship-without-asking fact; got: {behavior_texts}"
        )
        for r in behavior_hits.results:
            assert "feedback:behavior" in (r.tags or []), (
                f"every returned fact must carry feedback:behavior tag; got tags={r.tags}"
            )
            # Caller-supplied tag must survive on every stored fact.
            assert "user:chris" in (r.tags or []), (
                f"caller-supplied tag user:chris must survive on stored fact; got tags={r.tags}"
            )

        # Recall by feedback:style — should return ONLY the style fact.
        style_hits = await memory.recall_async(
            bank_id=bank_id,
            query="style corrections",
            tags=["feedback:style"],
            tags_match="any_strict",
            fact_type=["world"],
            request_context=request_context,
        )
        style_texts = [r.text for r in style_hits.results]
        assert any("concise wording" in t for t in style_texts), (
            f"style recall must include the concise-wording fact; got: {style_texts}"
        )
        for r in style_hits.results:
            tags_on_fact = r.tags or []
            assert "feedback:style" in tags_on_fact, (
                f"every returned fact must carry feedback:style tag; got tags={tags_on_fact}"
            )
            # And must NOT be the behavior or execution fact (any_strict isolates).
            assert "feedback:behavior" not in tags_on_fact, (
                f"feedback:style recall leaked a behavior-tagged fact: tags={tags_on_fact}"
            )
            assert "feedback:execution" not in tags_on_fact, (
                f"feedback:style recall leaked an execution-tagged fact: tags={tags_on_fact}"
            )

    finally:
        await memory.delete_bank(bank_id, request_context=request_context)


# ---------------------------------------------------------------------------
# Test 2: per-retain tag_enumerations overrides bank-level by namespace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_retain_overrides_bank_by_namespace(memory: MemoryEngine, request_context, monkeypatch):
    """Bank-level config declares ``feedback`` with value=old_value. A
    subsequent retain passes its OWN ``feedback`` enumeration whose values
    are behavior/style/execution — per-retain must win by namespace, so
    the LLM is allowed (and observed) to emit ``behavior``, and that
    flows into the recall index.
    """
    bank_id = f"test-tag-enums-override-{uuid.uuid4().hex[:8]}"
    try:
        await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)

        # Bank-level config: feedback has ONLY old_value, type=value.
        await memory._config_resolver.update_bank_config(
            bank_id=bank_id,
            updates={
                "tag_enumerations": [
                    {
                        "namespace": "feedback",
                        "type": "value",
                        "optional": True,
                        "values": [{"value": "old_value"}],
                    }
                ]
            },
            context=request_context,
        )

        # Per-retain config: feedback redefined as multi-values with
        # behavior/style/execution. Per-retain wins by namespace, so the
        # extraction schema accepts "behavior".
        per_retain_enums = [
            {
                "namespace": "feedback",
                "type": "multi-values",
                "values": [
                    {"value": "behavior"},
                    {"value": "style"},
                    {"value": "execution"},
                ],
            }
        ]

        marker = "override-namespace transcript"
        scripted = {
            marker: [
                {
                    "what": "User wants ship-without-asking behavior",
                    "when": "during chat",
                    "who": "user",
                    "why": "wants speed",
                    "fact_type": "world",
                    "fact_kind": "conversation",
                    "tags": {"feedback": ["behavior"]},
                },
            ],
        }
        monkeypatch.setattr(LLMConfig, "call", _make_fake_call(scripted), raising=True)

        result = await memory.retain_batch_async(
            bank_id=bank_id,
            contents=[
                {
                    "content": f"{marker}. Ship without asking next time, please.",
                    "tag_enumerations": per_retain_enums,
                }
            ],
            request_context=request_context,
        )
        assert result and len(result[0]) == 1, f"expected 1 stored fact, got {result}"

        # Recall by the override value — proves per-retain replaced bank.
        hits = await memory.recall_async(
            bank_id=bank_id,
            query="behavior corrections",
            tags=["feedback:behavior"],
            tags_match="any_strict",
            fact_type=["world"],
            request_context=request_context,
        )
        assert len(hits.results) >= 1, (
            "per-retain override should let LLM emit feedback:behavior and "
            "make the fact recallable by that tag; got 0 results"
        )
        assert all("feedback:behavior" in (r.tags or []) for r in hits.results), (
            f"every returned fact must carry feedback:behavior; got: {[r.tags for r in hits.results]}"
        )

    finally:
        await memory.delete_bank(bank_id, request_context=request_context)


# ---------------------------------------------------------------------------
# Test 3: entity_labels and tag_enumerations compose in one retain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_labels_and_tag_enumerations_compose_in_one_retain(
    memory: MemoryEngine, request_context, monkeypatch
):
    """Configure BOTH entity_labels (pedagogy group) AND tag_enumerations
    (feedback namespace) on the same retain. The mock LLM emits a fact
    that carries both:
      labels: {"pedagogy": "scaffolding"}   →  entity 'pedagogy:scaffolding'
      tags:   {"feedback": ["behavior"]}    →  tag 'feedback:behavior'

    Verify the stored fact has the entity label entity AND the feedback tag,
    proving the two systems don't trample each other.
    """
    bank_id = f"test-labels-and-enums-{uuid.uuid4().hex[:8]}"
    try:
        await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)

        # Bank-level: configure entity_labels with a pedagogy group.
        # Use tag=True so the label also appears as a fact tag, which gives
        # us a simple recall-side assertion without needing entity inspection.
        await memory._config_resolver.update_bank_config(
            bank_id=bank_id,
            updates={
                "entity_labels": [
                    {
                        "key": "pedagogy",
                        "type": "value",
                        "tag": True,
                        "values": [
                            {"value": "scaffolding"},
                            {"value": "active_engagement"},
                        ],
                    }
                ]
            },
            context=request_context,
        )

        # Per-retain: declare a feedback tag enumeration.
        per_retain_enums = [
            {
                "namespace": "feedback",
                "type": "multi-values",
                "values": [
                    {"value": "behavior"},
                    {"value": "style"},
                ],
            }
        ]

        marker = "compose-labels-and-tags transcript"
        scripted = {
            marker: [
                {
                    "what": "Teacher used scaffolding while giving feedback",
                    "when": "session",
                    "who": "teacher",
                    "why": "instructional approach",
                    "fact_type": "world",
                    "fact_kind": "conversation",
                    # entity_labels payload (separate field)
                    "labels": {"pedagogy": "scaffolding"},
                    # tag_enumerations payload (separate field)
                    "tags": {"feedback": ["behavior"]},
                }
            ],
        }
        monkeypatch.setattr(LLMConfig, "call", _make_fake_call(scripted), raising=True)

        result = await memory.retain_batch_async(
            bank_id=bank_id,
            contents=[
                {
                    "content": f"{marker}. Teacher used scaffolding during feedback.",
                    "tag_enumerations": per_retain_enums,
                }
            ],
            request_context=request_context,
        )
        assert result and len(result[0]) == 1, f"expected 1 stored fact, got {result}"

        # Recall everything in the bank and inspect the single fact.
        all_hits = await memory.recall_async(
            bank_id=bank_id,
            query="scaffolding feedback",
            fact_type=["world"],
            include_entities=True,
            request_context=request_context,
        )
        assert len(all_hits.results) == 1, (
            f"expected 1 fact in bank, got {len(all_hits.results)}: {[r.text for r in all_hits.results]}"
        )
        fact = all_hits.results[0]
        tags = fact.tags or []

        # tag_enumerations: feedback:behavior must be present.
        assert "feedback:behavior" in tags, f"tag_enumerations must populate feedback:behavior; got tags={tags}"
        # entity_labels (with tag=True): pedagogy:scaffolding must also be
        # present, proving the two extraction systems compose.
        assert "pedagogy:scaffolding" in tags, (
            f"entity_labels with tag=True must populate pedagogy:scaffolding; got tags={tags}"
        )

        # Recall by feedback:behavior — fact must be returned.
        feedback_hits = await memory.recall_async(
            bank_id=bank_id,
            query="behavior corrections",
            tags=["feedback:behavior"],
            tags_match="any_strict",
            fact_type=["world"],
            request_context=request_context,
        )
        assert len(feedback_hits.results) == 1, (
            f"recall by feedback:behavior must return the composed fact; got {len(feedback_hits.results)} results"
        )

        # Recall by pedagogy:scaffolding — fact must be returned.
        pedagogy_hits = await memory.recall_async(
            bank_id=bank_id,
            query="scaffolding instruction",
            tags=["pedagogy:scaffolding"],
            tags_match="any_strict",
            fact_type=["world"],
            request_context=request_context,
        )
        assert len(pedagogy_hits.results) == 1, (
            f"recall by pedagogy:scaffolding must return the composed fact; got {len(pedagogy_hits.results)} results"
        )

    finally:
        await memory.delete_bank(bank_id, request_context=request_context)
