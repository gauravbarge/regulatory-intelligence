"""Fake model gateway behaviour."""

import pytest

from medidata_common.contracts import RequestContext, UseCase
from supervisor.model_gateway import FakeModelGateway


@pytest.mark.asyncio
async def test_classify_requirement_vs_release() -> None:
    gw = FakeModelGateway()
    req = await gw.classify_use_case(
        "Does Clinical View support electronic signatures?", RequestContext()
    )
    assert req is UseCase.REQUIREMENT_VALIDATION

    rel = await gw.classify_use_case(
        "Assess the validation impact of upgrading to release 2026.3",
        RequestContext(release="2026.3"),
    )
    assert rel is UseCase.RELEASE_VALIDATION


@pytest.mark.asyncio
async def test_synthesize_aggregates_confidence() -> None:
    gw = FakeModelGateway()
    results = [
        {"confidence": 0.9, "status": "success", "findings": [
            {"statement": "supported", "confidence": 0.9, "evidence_ids": ["e1"]}
        ]},
        {"confidence": 0.8, "status": "success", "findings": []},
    ]
    draft = await gw.synthesize(
        "q", UseCase.REQUIREMENT_VALIDATION, results, RequestContext()
    )
    assert draft["decision"] == "supported"
    assert draft["confidence"] == pytest.approx(0.85)
    assert len(draft["evidence_backed_findings"]) == 1
