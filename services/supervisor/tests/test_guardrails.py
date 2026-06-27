"""Guardrail rule tests (docs/guardrails-hitl.md)."""

from medidata_common.config import Settings
from medidata_common.contracts import SupervisorDecision
from supervisor.guardrails import GuardrailEngine

SETTINGS = Settings(compliance_confidence_threshold=0.8)


def test_low_confidence_requires_human() -> None:
    engine = GuardrailEngine(SETTINGS)
    draft = {
        "decision": SupervisorDecision.SUPPORTED.value,
        "executive_summary": "looks fine",
        "evidence_backed_findings": [],
    }
    result = engine.evaluate(draft, confidence=0.5)
    assert result.requires_human
    assert any("threshold" in r for r in result.reasons)


def test_compliance_claim_requires_human() -> None:
    engine = GuardrailEngine(SETTINGS)
    draft = {
        "decision": SupervisorDecision.SUPPORTED.value,
        "executive_summary": "The product is fully 21 CFR Part 11 compliant.",
        "evidence_backed_findings": [
            {"statement": "x", "confidence": 0.95, "evidence_ids": ["e1"]}
        ],
    }
    result = engine.evaluate(draft, confidence=0.95)
    assert result.requires_human
    assert any("compliance" in r for r in result.reasons)


def test_no_validation_on_gxp_change_requires_human() -> None:
    engine = GuardrailEngine(SETTINGS)
    draft = {
        "decision": SupervisorDecision.NO_VALIDATION_REQUIRED.value,
        "executive_summary": "Change has GxP impact but no validation needed.",
        "evidence_backed_findings": [
            {"statement": "x", "confidence": 0.9, "evidence_ids": ["e1"]}
        ],
    }
    result = engine.evaluate(draft, confidence=0.9)
    assert result.requires_human


def test_clean_high_confidence_auto_releases() -> None:
    engine = GuardrailEngine(SETTINGS)
    draft = {
        "decision": SupervisorDecision.SUPPORTED.value,
        "executive_summary": "Feature is available and configurable.",
        "evidence_backed_findings": [
            {"statement": "x", "confidence": 0.95, "evidence_ids": ["e1"]}
        ],
    }
    result = engine.evaluate(draft, confidence=0.95)
    assert not result.requires_human
    assert not result.violations


def test_finding_without_evidence_is_violation() -> None:
    engine = GuardrailEngine(SETTINGS)
    draft = {
        "decision": SupervisorDecision.SUPPORTED.value,
        "executive_summary": "ok",
        "evidence_backed_findings": [
            {"statement": "no evidence here", "confidence": 0.95, "evidence_ids": []}
        ],
    }
    result = engine.evaluate(draft, confidence=0.95)
    assert result.violations
    assert result.requires_human
