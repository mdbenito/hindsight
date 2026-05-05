"""
LLM Minimum Acceptance Tests.

Validates that a given LLM provider/model works correctly with Hindsight's
core operations: API methods, fact extraction, and reflect.

Provider and model are set via environment variables:
  - LLM_TEST_PROVIDER: the provider name (e.g., "openai", "anthropic", "gemini")
  - LLM_TEST_MODEL: the model name (e.g., "gpt-4o-mini", "claude-sonnet-4-20250514")

These tests are excluded from the regular test-api CI job (marked with pytest.mark.llm)
and run in a dedicated workflow with a CI-managed matrix of provider/model combinations.
"""

import os
from datetime import datetime

import pytest

from hindsight_api.engine.llm_wrapper import LLMProvider
from hindsight_api.engine.utils import extract_facts
from hindsight_api.engine.search.think_utils import reflect

pytestmark = pytest.mark.llm

_PROVIDER = os.environ.get("LLM_TEST_PROVIDER", "")
_MODEL = os.environ.get("LLM_TEST_MODEL", "")

PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def _get_api_key() -> str:
    env_var = PROVIDER_KEY_MAP.get(_PROVIDER, "")
    return os.environ.get(env_var, "") if env_var else ""


def _skip_if_not_configured():
    if not _PROVIDER or not _MODEL:
        pytest.skip(
            "LLM_TEST_PROVIDER and LLM_TEST_MODEL must be set to run LLM acceptance tests"
        )


def _make_llm() -> LLMProvider:
    return LLMProvider(
        provider=_PROVIDER,
        api_key=_get_api_key(),
        base_url="",
        model=_MODEL,
    )


@pytest.mark.asyncio
@pytest.mark.timeout(300)
async def test_llm_api_methods():
    """
    Test all LLM API methods used by Hindsight at runtime.

    Tests:
    1. verify_connection() - Connection verification
    2. call() with plain text - Basic LLM call
    3. call() with response_format - Structured output (used in fact extraction)
    4. call_with_tools() - Tool calling (used in reflect agent)
    """
    _skip_if_not_configured()
    llm = _make_llm()

    # Test 1: verify_connection()
    await llm.verify_connection()

    # Test 2: call() with plain text
    response = await llm.call(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2? Answer in one word."},
        ],
        max_completion_tokens=50,
    )
    assert response is not None, "call() returned None"
    assert len(response) > 0, "call() returned empty string"

    # Test 3: call() with response_format (structured output)
    from pydantic import BaseModel

    class TestResponse(BaseModel):
        answer: str
        confidence: str

    structured = await llm.call(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ],
        response_format=TestResponse,
        max_completion_tokens=100,
    )
    assert isinstance(structured, TestResponse), f"Expected TestResponse, got {type(structured)}"
    assert structured.answer, "Structured output missing 'answer'"
    assert structured.confidence, "Structured output missing 'confidence'"

    # Test 4: call_with_tools() (tool calling)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    result = await llm.call_with_tools(
        messages=[
            {"role": "system", "content": "You are a helpful assistant with access to tools."},
            {"role": "user", "content": "What's the weather like in Paris?"},
        ],
        tools=tools,
        max_completion_tokens=500,
    )

    assert result is not None, "call_with_tools() returned None"
    assert hasattr(result, "tool_calls"), "Result missing 'tool_calls' attribute"
    assert len(result.tool_calls) > 0, f"Expected at least 1 tool call, got {len(result.tool_calls)}"

    tool_call = result.tool_calls[0]
    assert tool_call.name == "get_weather", f"Expected 'get_weather', got '{tool_call.name}'"
    assert "location" in tool_call.arguments, "Tool call arguments missing 'location'"


@pytest.mark.asyncio
@pytest.mark.timeout(600)
async def test_llm_memory_operations():
    """
    Test LLM provider with actual memory operations: fact extraction and reflect.
    """
    _skip_if_not_configured()
    llm = _make_llm()

    # Fact extraction (structured output)
    test_text = """
    User: I just got back from my trip to Paris last week. The Eiffel Tower was amazing!
    Assistant: That sounds wonderful! How long were you there?
    User: About 5 days. I also visited the Louvre and saw the Mona Lisa.
    """

    facts, chunks = await extract_facts(
        text=test_text,
        event_date=datetime(2024, 12, 10),
        context="Travel conversation",
        llm_config=llm,
    )

    assert facts is not None, "fact extraction returned None"
    assert len(facts) > 0, "should extract at least one fact"

    for fact in facts:
        assert fact.fact, "fact missing text"
        assert fact.fact_type in ["world", "experience"], f"invalid fact_type: {fact.fact_type}"

    # Reflect
    response = await reflect(
        llm_config=llm,
        query="What was the highlight of my Paris trip?",
        experience_facts=[
            "I visited Paris in December 2024",
            "I saw the Eiffel Tower and it was amazing",
            "I visited the Louvre and saw the Mona Lisa",
            "The trip lasted 5 days",
        ],
        world_facts=[
            "The Eiffel Tower is a famous landmark in Paris",
            "The Mona Lisa is displayed at the Louvre museum",
        ],
        name="Traveler",
    )

    assert response is not None, "reflect returned None"
    assert len(response) > 10, "reflect response too short"


@pytest.mark.asyncio
@pytest.mark.timeout(600)
async def test_llm_consolidation(memory_no_llm_verify, request_context):
    """
    Test LLM provider with consolidation (mental model generation from observations).
    """
    _skip_if_not_configured()

    api_key = _get_api_key()
    llm = LLMProvider(
        provider=_PROVIDER,
        api_key=api_key,
        base_url="",
        model=_MODEL,
    )

    memory_no_llm_verify._consolidation_llm = llm
    memory_no_llm_verify._retain_llm = llm

    test_bank_id = f"llm_test_consolidation_{_PROVIDER}_{_MODEL}_{datetime.now().timestamp()}"

    from hindsight_api.config import _get_raw_config

    config = _get_raw_config()
    original_value = config.enable_observations
    config.enable_observations = True

    try:
        await memory_no_llm_verify.retain_async(
            bank_id=test_bank_id,
            content="""
            Bob prefers functional programming with Rust and Haskell.
            He emphasizes immutability and pure functions in code reviews.
            Bob advocates for type safety and compile-time guarantees.
            He avoids mutable state and prefers declarative code patterns.
            """,
            context="Team coding preferences",
            event_date=datetime(2024, 12, 1),
            request_context=request_context,
        )

        from hindsight_api.engine.consolidation.consolidator import run_consolidation_job

        result = await run_consolidation_job(
            memory_engine=memory_no_llm_verify,
            bank_id=test_bank_id,
            request_context=request_context,
        )

        assert result["status"] in ["success", "no_new_memories"], f"consolidation failed: {result}"

        if result.get("observations_created", 0) > 0:
            observations = await memory_no_llm_verify.list_mental_models_consolidated(
                bank_id=test_bank_id,
                request_context=request_context,
            )
            assert len(observations) > 0, "consolidation created 0 observations"

            obs_content = observations[0].get("content", "").lower()
            relevant_terms = ["bob", "functional", "rust", "immutab", "type"]
            matches = [term for term in relevant_terms if term in obs_content]
            assert len(matches) >= 2, (
                f"consolidated observation doesn't contain relevant info. "
                f"Expected at least 2 of {relevant_terms}, found {matches}"
            )
    finally:
        config.enable_observations = original_value
