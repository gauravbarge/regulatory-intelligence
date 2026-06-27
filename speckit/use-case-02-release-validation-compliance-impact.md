# Use Case 02 – Release Validation & Compliance Impact

## Objective
Help existing clients validate new releases, assess compliance impact, and prepare inspection-ready validation evidence packages.

## Example User Query
"We are upgrading Clinical View from v2026.2 to v2026.3. What needs validation and what evidence can we provide to FDA?"

## Required Agents
- Research Agent
- Developer Agent
- Agile Master Agent
- Document Analyst Agent

## Workflow
1. Supervisor identifies product, current version, target version, and client context.
2. Research Agent retrieves release notes, VSR, RTM, test reports, risk assessment, known issues.
3. Developer Agent identifies changed modules, APIs, schema changes, affected services.
4. Agile Agent maps changes to Jira stories, defects, and resolved issues.
5. Document Analyst reviews customer-specific validation templates or uploaded packages.
6. Supervisor performs impact analysis.
7. Guardrails check GxP, patient safety, audit trail, electronic signature, and data integrity impacts.
8. Human approval if regulated conclusion is made.
9. System generates validation recommendation and evidence package.

## Output
- Change impact summary
- Compliance impact assessment
- Validation recommendation
- Impacted requirements
- Impacted test cases
- Known issues
- Evidence package
- Human approval record

## Acceptance Criteria
- All recommendations have evidence.
- GxP-impacting changes require review.
- System does not claim FDA acceptance; it provides inspection-supporting evidence.
- Generated package includes source document versions.
