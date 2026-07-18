"""Candidate filtering and one-call-per-slot GPT-5.6 Sol reranking."""

from api.llm import CandidateAssessment, RerankResult, rerank_slot


def accepted_top_three(result: RerankResult) -> list[CandidateAssessment]:
    """Discard strict rejects and return the three strongest visual matches."""

    accepted = (item for item in result.candidates if not item.reject_flag)
    return sorted(accepted, key=lambda item: item.match_score, reverse=True)[:3]


__all__ = ["accepted_top_three", "rerank_slot"]
