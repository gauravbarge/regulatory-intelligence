# Guardrails and Human-in-the-Loop

## Guardrail Categories

### Compliance Guardrails
Human approval required when:
- AI recommends no validation for a GxP-impacting change
- AI makes FDA/Part 11 compliance claims
- AI detects patient safety or data integrity impact
- Confidence < 0.8 for regulatory conclusion

### Security Guardrails
- Do not expose customer-specific data across tenants.
- Do not show source code to customer-facing users.
- Do not include confidential roadmap items unless authorized.

### Output Guardrails
- Every compliance conclusion needs evidence.
- Every validation recommendation needs rationale.
- Unsupported requirements must not be described as supported.
- AI must clearly state uncertainty.

## Human Approval Flow
1. Supervisor flags response.
2. Response stored as draft.
3. QA/Validation reviewer approves, edits, or rejects.
4. Final response is released.
5. Approval action is audit logged.
