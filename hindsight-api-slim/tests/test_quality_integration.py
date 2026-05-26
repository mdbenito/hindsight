"""
End-to-end quality integration tests: retain → recall → reflect with real LLM.

All tests use memory_real_llm and the LLM judge.  They are marked hs_llm_core
so they run in the single-provider quality CI job, not in the structural mock job.

These tests fill the gap identified in the testing philosophy review: the mock
suite proves API plumbing works; these tests prove the LLM pipeline actually
produces correct output.
"""

import uuid

import pytest

from hindsight_api.engine.memory_engine import Budget, MemoryEngine


@pytest.mark.hs_llm_core
class TestEndToEndPipeline:
    """Full retain → recall → reflect pipeline with meaningful output assertions."""

    @pytest.fixture
    def memory(self, memory_real_llm):
        return memory_real_llm

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2, reruns_delay=2)
    async def test_retain_recall_reflect_roundtrip(self, memory: MemoryEngine, request_context):
        """Facts retained should be correctly recalled and synthesised by reflect.

        Given a set of facts about a person, reflect must produce a response that
        demonstrates it actually used those facts — not a generic non-answer.
        """
        from tests.llm_judge import assert_meets_criteria

        bank_id = f"test-e2e-roundtrip-{uuid.uuid4().hex[:8]}"
        try:
            await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)

            for content in [
                "Elena Vasquez is a senior data engineer at a fintech startup.",
                "Elena specialises in Apache Kafka and real-time data pipelines.",
                "She has 8 years of experience in data engineering.",
                "Elena is currently leading a migration from batch to streaming architecture.",
                "She holds a bachelor's degree in computer science from UC Berkeley.",
            ]:
                await memory.retain_async(bank_id=bank_id, content=content, request_context=request_context)

            recall_result = await memory.recall_async(
                bank_id=bank_id,
                query="What is Elena's role and expertise?",
                budget=Budget.LOW,
                request_context=request_context,
            )
            assert len(recall_result.results) > 0, "Recall should find facts about Elena"

            reflect_result = await memory.reflect_async(
                bank_id=bank_id,
                query="Give me a summary of Elena's background and what she's currently working on.",
                request_context=request_context,
            )
            assert reflect_result.text, "Reflect must return a non-empty response"

            await assert_meets_criteria(
                response=reflect_result.text,
                criteria=(
                    "The response accurately describes Elena Vasquez's profile: it mentions her role "
                    "as a data engineer, her expertise in data pipelines or Kafka, and her current "
                    "migration or streaming project."
                ),
                msg=f"Reflect should synthesise retained facts about Elena. Got: {reflect_result.text[:600]}",
            )
        finally:
            await memory.delete_bank(bank_id, request_context=request_context)

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2, reruns_delay=2)
    async def test_reflect_answers_specific_factual_query(self, memory: MemoryEngine, request_context):
        """Reflect must retrieve and state specific retained facts when asked directly."""
        from tests.llm_judge import assert_meets_criteria

        bank_id = f"test-e2e-factual-{uuid.uuid4().hex[:8]}"
        try:
            await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)
            await memory.retain_async(
                bank_id=bank_id,
                content=(
                    "The project deadline is March 15th. "
                    "The client is Acme Corp. "
                    "The total budget is $250,000."
                ),
                context="project notes",
                request_context=request_context,
            )
            reflect_result = await memory.reflect_async(
                bank_id=bank_id,
                query="Who is the client and what is the budget for this project?",
                request_context=request_context,
            )
            assert reflect_result.text
            await assert_meets_criteria(
                response=reflect_result.text,
                criteria=(
                    "The response correctly identifies Acme Corp as the client "
                    "and $250,000 (or 250k) as the budget."
                ),
                msg=f"Reflect should state specific retained facts. Got: {reflect_result.text[:500]}",
            )
        finally:
            await memory.delete_bank(bank_id, request_context=request_context)

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2, reruns_delay=2)
    async def test_reflect_handles_query_with_no_relevant_facts(self, memory: MemoryEngine, request_context):
        """Reflect asked about a topic absent from memory should acknowledge the gap."""
        from tests.llm_judge import assert_meets_criteria

        bank_id = f"test-e2e-unknown-{uuid.uuid4().hex[:8]}"
        try:
            await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)
            # Retain something completely unrelated to the query
            await memory.retain_async(
                bank_id=bank_id,
                content="My sourdough starter needs feeding every 24 hours using a 1:1:1 flour-water-starter ratio.",
                request_context=request_context,
            )
            reflect_result = await memory.reflect_async(
                bank_id=bank_id,
                query="What is the quarterly revenue forecast for our enterprise segment?",
                request_context=request_context,
            )
            assert reflect_result.text
            await assert_meets_criteria(
                response=reflect_result.text,
                criteria=(
                    "The response indicates that no relevant information is available in memory "
                    "about the revenue forecast, OR it explicitly states it cannot answer from "
                    "the stored context."
                ),
                msg=f"Reflect should acknowledge missing relevant facts. Got: {reflect_result.text[:500]}",
            )
        finally:
            await memory.delete_bank(bank_id, request_context=request_context)


@pytest.mark.hs_llm_core
class TestDispositionInfluence:
    """Test that disposition traits produce observable differences in reflect output.

    These are the first tests for disposition — previously there were zero.
    The suite only verifies one direction (skepticism) since it has the clearest
    prompt effect; other traits can be added as needed.
    """

    @pytest.fixture
    def memory(self, memory_real_llm):
        return memory_real_llm

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2, reruns_delay=2)
    async def test_high_skepticism_hedges_unverifiable_claims(self, memory: MemoryEngine, request_context):
        """Maximum skepticism (5) should produce hedging language for uncertain claims.

        An unverifiable rumour stored as a fact should elicit qualifications like
        'apparently', 'reportedly', 'might', 'it seems' etc. from a high-skepticism
        bank — language a low-skepticism bank would typically omit.
        """
        from tests.llm_judge import assert_meets_criteria

        claim = (
            "Apparently James has won every single hackathon he has ever entered "
            "and is widely considered unbeatable by his peers."
        )
        query = "How good is James at hackathons?"

        bank_skeptical = f"test-disposition-skeptical-{uuid.uuid4().hex[:8]}"
        try:
            await memory.get_bank_profile(bank_id=bank_skeptical, request_context=request_context)
            await memory.update_bank_disposition(
                bank_skeptical,
                {"skepticism": 5, "literalism": 3, "empathy": 3},
                request_context=request_context,
            )
            await memory.retain_async(bank_id=bank_skeptical, content=claim, request_context=request_context)

            skeptical_result = await memory.reflect_async(
                bank_id=bank_skeptical,
                query=query,
                request_context=request_context,
            )
            assert skeptical_result.text

            await assert_meets_criteria(
                response=skeptical_result.text,
                criteria=(
                    "The response uses hedging or qualifying language — words or phrases such as "
                    "'apparently', 'reportedly', 'it seems', 'might', 'may', 'could', 'allegedly', "
                    "'claimed', 'supposedly', or similar — reflecting appropriate skepticism about "
                    "an unverified claim."
                ),
                context=f"Bank has maximum skepticism (5/5). The stored claim was: '{claim}'",
                msg=f"High-skepticism response should hedge unverifiable claims. Got: {skeptical_result.text[:500]}",
            )
        finally:
            await memory.delete_bank(bank_skeptical, request_context=request_context)

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2, reruns_delay=2)
    async def test_high_skepticism_response_is_more_hedged_than_low(
        self, memory: MemoryEngine, request_context
    ):
        """Skepticism=5 should produce a measurably more hedged response than skepticism=1.

        A string-inequality check would pass purely from LLM sampling variance, so we
        give both responses to the judge and ask it which one shows more skepticism.
        This catches the case where the disposition trait isn't wired into the prompt
        at all — both responses would then look equally confident.
        """
        from tests.llm_judge import assert_meets_criteria

        claim = "Sam is supposedly the most productive engineer on the team by a wide margin."
        query = "What can you tell me about Sam's productivity?"

        bank_low = f"test-disposition-low-{uuid.uuid4().hex[:8]}"
        bank_high = f"test-disposition-high-{uuid.uuid4().hex[:8]}"
        try:
            for bank_id, skepticism in [(bank_low, 1), (bank_high, 5)]:
                await memory.get_bank_profile(bank_id=bank_id, request_context=request_context)
                await memory.update_bank_disposition(
                    bank_id,
                    {"skepticism": skepticism, "literalism": 3, "empathy": 3},
                    request_context=request_context,
                )
                await memory.retain_async(bank_id=bank_id, content=claim, request_context=request_context)

            low_result = await memory.reflect_async(bank_id=bank_low, query=query, request_context=request_context)
            high_result = await memory.reflect_async(bank_id=bank_high, query=query, request_context=request_context)

            assert low_result.text and high_result.text

            # Judge compares the two responses for relative skepticism.  Presenting both
            # in a single prompt lets it evaluate which is more hedged — sampling
            # variance alone won't satisfy this criterion.
            comparison = (
                f"RESPONSE A (from bank with skepticism=5/5):\n{high_result.text}\n\n"
                f"---\n\n"
                f"RESPONSE B (from bank with skepticism=1/5):\n{low_result.text}"
            )

            await assert_meets_criteria(
                response=comparison,
                criteria=(
                    "Response A shows more skepticism than Response B about the productivity "
                    "claim — A uses more hedging language ('apparently', 'reportedly', 'might', "
                    "'allegedly', etc.) or more explicitly flags the claim as unverified, while "
                    "B states it more directly or with less qualification.  If the two responses "
                    "show the same level of skepticism, the criterion is NOT met."
                ),
                context=(
                    "Both banks stored the same claim ('Sam is supposedly the most productive "
                    "engineer...') and were asked the same query.  The only difference is "
                    "their skepticism disposition trait.  A: skepticism=5, B: skepticism=1."
                ),
                msg=(
                    f"Disposition should make response A more skeptical than B.\n"
                    f"  A (skepticism=5): {high_result.text[:300]}\n"
                    f"  B (skepticism=1): {low_result.text[:300]}"
                ),
            )
        finally:
            await memory.delete_bank(bank_low, request_context=request_context)
            await memory.delete_bank(bank_high, request_context=request_context)
