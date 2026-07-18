"""Offline tests for GPT-5.6 configuration boundaries."""

import pytest

from api.config import Settings
from api.llm import CandidateAssessment, LlmConfigurationError, RerankResult, _client
from api.pipeline.rerank import accepted_top_three


def test_live_client_requires_an_api_key() -> None:
    with pytest.raises(LlmConfigurationError):
        _client(Settings())


def test_strict_reject_rule_removes_a_duvet_cover() -> None:
    result = RerankResult(
        candidates=[
            CandidateAssessment(
                id="jacket",
                match_score=91,
                reason="Correct silhouette.",
                reject_flag=False,
            ),
            CandidateAssessment(
                id="duvet",
                match_score=88,
                reason="Wrong garment type.",
                reject_flag=True,
            ),
        ]
    )

    assert [item.id for item in accepted_top_three(result)] == ["jacket"]
