"""Guardrails and Human-in-the-Loop decisioning.

Implements the rules in ``docs/guardrails-hitl.md``. The engine inspects the
draft response and decides whether human approval is required and records the
reasons (for audit) and any output-quality violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from medidata_common.config import Settings, get_settings
from medidata_common.contracts import SupervisorDecision

# Phrases that, if present in a regulated conclusion, force human review.
_COMPLIANCE_CLAIM_TERMS = (
    "fda",
    "part 11",
    "21 cfr",
    "gxp",
    "gmp",
    "patient safety",
    "data integrity",
    "compliant",
    "validated",
)

_GXP_IMPACT_TERMS = ("gxp", "patient safety", "data integrity", "21 cfr", "part 11")


@dataclass
class GuardrailResult:
    requires_human: bool = False
    reasons: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "requires_human": self.requires_human,
            "reasons": self.reasons,
            "violations": self.violations,
        }


class GuardrailEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def evaluate(self, draft: dict, confidence: float) -> GuardrailResult:
        result = GuardrailResult()
        decision = draft.get("decision", "")
        summary = (draft.get("executive_summary") or "").lower()
        findings = draft.get("evidence_backed_findings", [])

        # 1. Confidence below threshold for a regulatory conclusion -> HITL.
        if confidence < self._settings.compliance_confidence_threshold:
            result.requires_human = True
            result.reasons.append(
                f"confidence {confidence:.2f} < threshold "
                f"{self._settings.compliance_confidence_threshold:.2f}"
            )

        # 2. AI recommends NO validation for a GxP-impacting change.
        if decision == SupervisorDecision.NO_VALIDATION_REQUIRED.value and any(
            term in summary for term in _GXP_IMPACT_TERMS
        ):
            result.requires_human = True
            result.reasons.append("no-validation recommended on a GxP-impacting change")

        # 3. AI makes an FDA / Part 11 / compliance claim.
        if any(term in summary for term in _COMPLIANCE_CLAIM_TERMS):
            result.requires_human = True
            result.reasons.append("explicit compliance/regulatory claim present")

        # 4. Explicit human-review decision from synthesis.
        if decision == SupervisorDecision.HUMAN_REVIEW_REQUIRED.value:
            result.requires_human = True
            result.reasons.append("synthesis flagged human review")

        # Output guardrail: every compliance conclusion needs evidence.
        for f in findings:
            if not f.get("evidence_ids"):
                result.violations.append(
                    f"finding without evidence: {f.get('statement', '')[:80]!r}"
                )
        if result.violations:
            result.requires_human = True
            result.reasons.append("findings missing evidence")

        return result
