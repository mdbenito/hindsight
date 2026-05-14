"""
Tests for weighted Reciprocal Rank Fusion.

Validates that per-strategy weights correctly influence RRF merge ordering.
"""

import pytest

from hindsight_api.engine.search.fusion import reciprocal_rank_fusion
from hindsight_api.engine.search.types import RetrievalResult


def _make_result(id: str, **kwargs) -> RetrievalResult:
    """Create a minimal RetrievalResult for testing."""
    return RetrievalResult(id=id, text=f"text-{id}", fact_type="world", **kwargs)


class TestWeightedRRF:
    """Tests for weighted Reciprocal Rank Fusion."""

    def test_unweighted_default(self):
        """Without weights, all strategies contribute equally (existing behavior)."""
        semantic = [_make_result("a"), _make_result("b")]
        bm25 = [_make_result("b"), _make_result("a")]
        graph = [_make_result("a"), _make_result("c")]

        merged = reciprocal_rank_fusion([semantic, bm25, graph])

        # "a" appears rank 1 in semantic + graph, rank 2 in bm25 → highest score
        assert merged[0].id == "a"
        # All candidates present
        assert {m.id for m in merged} == {"a", "b", "c"}

    def test_weights_none_same_as_unweighted(self):
        """Passing weights=None produces identical results to no weights."""
        semantic = [_make_result("a"), _make_result("b")]
        bm25 = [_make_result("b"), _make_result("a")]
        graph = [_make_result("c")]

        merged_default = reciprocal_rank_fusion([semantic, bm25, graph])
        merged_none = reciprocal_rank_fusion([semantic, bm25, graph], weights=None)

        assert [m.id for m in merged_default] == [m.id for m in merged_none]
        for d, n in zip(merged_default, merged_none):
            assert d.rrf_score == pytest.approx(n.rrf_score)

    def test_all_weights_one_same_as_unweighted(self):
        """Explicit weights of 1.0 produce identical results."""
        semantic = [_make_result("a"), _make_result("b")]
        bm25 = [_make_result("b"), _make_result("a")]
        graph = [_make_result("c")]

        merged_default = reciprocal_rank_fusion([semantic, bm25, graph])
        merged_ones = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"semantic": 1.0, "bm25": 1.0, "graph": 1.0},
        )

        assert [m.id for m in merged_default] == [m.id for m in merged_ones]

    def test_high_graph_weight_boosts_graph_results(self):
        """A high graph weight should boost items that rank well in graph retrieval."""
        # "a" is rank 1 in semantic only
        # "b" is rank 1 in graph only
        semantic = [_make_result("a")]
        bm25 = []
        graph = [_make_result("b")]

        # Without weights: "a" and "b" tie (both rank 1 in one list)
        merged_equal = reciprocal_rank_fusion([semantic, bm25, graph])
        scores_equal = {m.id: m.rrf_score for m in merged_equal}
        assert scores_equal["a"] == pytest.approx(scores_equal["b"])

        # With graph weight 3.0: "b" should score higher
        merged_weighted = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"graph": 3.0},
        )
        scores_weighted = {m.id: m.rrf_score for m in merged_weighted}
        assert scores_weighted["b"] > scores_weighted["a"]
        assert merged_weighted[0].id == "b"

    def test_zero_weight_disables_strategy(self):
        """A weight of 0.0 should completely disable a strategy's contribution."""
        # "a" is only in semantic, "b" is only in graph
        semantic = [_make_result("a")]
        bm25 = []
        graph = [_make_result("b")]

        merged = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"semantic": 0.0},
        )

        scores = {m.id: m.rrf_score for m in merged}
        assert scores["a"] == 0.0  # semantic disabled
        assert scores["b"] > 0.0  # graph still contributes
        assert merged[0].id == "b"

    def test_partial_weights_default_to_one(self):
        """Omitted strategy keys default to weight 1.0."""
        semantic = [_make_result("a")]
        bm25 = [_make_result("b")]
        graph = [_make_result("c")]

        # Only specify graph weight, others should be 1.0
        merged = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"graph": 2.0},
        )

        scores = {m.id: m.rrf_score for m in merged}
        # "a" (semantic, w=1.0) and "b" (bm25, w=1.0) should have equal scores
        assert scores["a"] == pytest.approx(scores["b"])
        # "c" (graph, w=2.0) should have double the score
        assert scores["c"] == pytest.approx(scores["a"] * 2.0)

    def test_weights_with_temporal(self):
        """Weights work correctly with 4 retrieval strategies including temporal."""
        semantic = [_make_result("a")]
        bm25 = [_make_result("b")]
        graph = [_make_result("c")]
        temporal = [_make_result("d")]

        merged = reciprocal_rank_fusion(
            [semantic, bm25, graph, temporal],
            weights={"temporal": 5.0},
        )

        scores = {m.id: m.rrf_score for m in merged}
        # "d" (temporal, w=5.0) should have highest score
        assert merged[0].id == "d"
        assert scores["d"] == pytest.approx(scores["a"] * 5.0)

    def test_weight_changes_ranking_order(self):
        """Demonstrate that weights can reverse the ranking of two items."""
        # Both "a" and "b" appear in semantic and graph, but in different positions
        # Semantic: a=1, b=2  →  Graph: b=1, a=2
        semantic = [_make_result("a"), _make_result("b")]
        bm25 = []
        graph = [_make_result("b"), _make_result("a")]

        # Unweighted: tied (both appear at rank 1 and rank 2, once each)
        merged_equal = reciprocal_rank_fusion([semantic, bm25, graph])
        scores_equal = {m.id: m.rrf_score for m in merged_equal}
        assert scores_equal["a"] == pytest.approx(scores_equal["b"])

        # Weight graph 3x: "b" wins because it's rank 1 in the heavier strategy
        merged_graph_heavy = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"graph": 3.0},
        )
        assert merged_graph_heavy[0].id == "b"

        # Weight semantic 3x: "a" wins
        merged_semantic_heavy = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"semantic": 3.0},
        )
        assert merged_semantic_heavy[0].id == "a"

    def test_source_ranks_preserved_with_weights(self):
        """Source ranks should be unaffected by weights — only scores change."""
        semantic = [_make_result("a"), _make_result("b")]
        bm25 = [_make_result("b")]
        graph = [_make_result("a")]

        merged = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"graph": 10.0},
        )

        ranks = {m.id: m.source_ranks for m in merged}
        assert ranks["a"]["semantic_rank"] == 1
        assert ranks["a"]["graph_rank"] == 1
        assert ranks["b"]["semantic_rank"] == 2
        assert ranks["b"]["bm25_rank"] == 1

    def test_rrf_rank_reflects_weighted_order(self):
        """rrf_rank should reflect the weighted score ordering."""
        semantic = [_make_result("a")]
        bm25 = []
        graph = [_make_result("b")]

        merged = reciprocal_rank_fusion(
            [semantic, bm25, graph],
            weights={"graph": 2.0},
        )

        rank_map = {m.id: m.rrf_rank for m in merged}
        assert rank_map["b"] == 1  # graph-boosted item ranks first
        assert rank_map["a"] == 2
