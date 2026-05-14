"""
Helper functions for hybrid search (semantic + BM25 + graph).
"""

from typing import Any

from .types import MergedCandidate, RetrievalResult


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievalResult]],
    k: int = 60,
    weights: dict[str, float] | None = None,
) -> list[MergedCandidate]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF formula: score(d) = sum_over_lists(w_i / (k + rank(d)))

    When weights are provided, each retrieval strategy's contribution is
    multiplied by its weight. A weight of 2.0 doubles that strategy's
    influence; 0.0 disables it entirely. Default weight is 1.0 (unweighted).

    Args:
        result_lists: List of result lists, each containing RetrievalResult objects
        k: Constant for RRF formula (default: 60)
        weights: Optional mapping of strategy name to weight, e.g.
                 {"semantic": 1.0, "bm25": 1.0, "graph": 2.0, "temporal": 1.0}

    Returns:
        Merged list of MergedCandidate objects, sorted by RRF score

    Example:
        semantic_results = [RetrievalResult(...), RetrievalResult(...), ...]
        bm25_results = [RetrievalResult(...), RetrievalResult(...), ...]
        graph_results = [RetrievalResult(...), RetrievalResult(...), ...]

        # Unweighted (default)
        merged = reciprocal_rank_fusion([semantic_results, bm25_results, graph_results])

        # With graph retrieval weighted 2x
        merged = reciprocal_rank_fusion(
            [semantic_results, bm25_results, graph_results],
            weights={"graph": 2.0},
        )
    """
    # Track scores from each list
    rrf_scores = {}
    source_ranks = {}  # Track rank from each source for each doc_id
    all_retrievals = {}  # Store the actual RetrievalResult (use first occurrence)

    source_names = ["semantic", "bm25", "graph", "temporal"]

    for source_idx, results in enumerate(result_lists):
        source_name = source_names[source_idx] if source_idx < len(source_names) else f"source_{source_idx}"
        weight = (weights or {}).get(source_name, 1.0)

        for rank, retrieval in enumerate(results, start=1):
            # Type check to catch tuple issues
            if isinstance(retrieval, tuple):
                raise TypeError(
                    f"Expected RetrievalResult but got tuple in {source_name} results at rank {rank}. "
                    f"Tuple value: {retrieval[:2] if len(retrieval) >= 2 else retrieval}. "
                    f"This suggests the retrieval function returned tuples instead of RetrievalResult objects."
                )
            if not isinstance(retrieval, RetrievalResult):
                raise TypeError(
                    f"Expected RetrievalResult but got {type(retrieval).__name__} in {source_name} results at rank {rank}"
                )
            doc_id = retrieval.id

            # Store retrieval result (use first occurrence)
            if doc_id not in all_retrievals:
                all_retrievals[doc_id] = retrieval

            # Calculate weighted RRF score contribution
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
                source_ranks[doc_id] = {}

            rrf_scores[doc_id] += weight / (k + rank)
            source_ranks[doc_id][f"{source_name}_rank"] = rank

    # Combine into final results with metadata
    merged_results = []
    for rrf_rank, (doc_id, rrf_score) in enumerate(
        sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True), start=1
    ):
        merged_candidate = MergedCandidate(
            retrieval=all_retrievals[doc_id], rrf_score=rrf_score, rrf_rank=rrf_rank, source_ranks=source_ranks[doc_id]
        )
        merged_results.append(merged_candidate)

    return merged_results


def normalize_scores_on_deltas(results: list[dict[str, Any]], score_keys: list[str]) -> list[dict[str, Any]]:
    """
    Normalize scores based on deltas (min-max normalization within result set).

    This ensures all scores are in [0, 1] range based on the spread in THIS result set.

    Args:
        results: List of result dicts
        score_keys: Keys to normalize (e.g., ["recency", "frequency"])

    Returns:
        Results with normalized scores added as "{key}_normalized"
    """
    for key in score_keys:
        values = [r.get(key, 0.0) for r in results if key in r]

        if not values:
            continue

        min_val = min(values)
        max_val = max(values)
        delta = max_val - min_val

        if delta > 0:
            for r in results:
                if key in r:
                    r[f"{key}_normalized"] = (r[key] - min_val) / delta
        else:
            # All values are the same, set to 0.5
            for r in results:
                if key in r:
                    r[f"{key}_normalized"] = 0.5

    return results
