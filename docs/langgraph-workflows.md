# LangGraph Workflow Specification

## Supervisor Graph

Nodes:
1. `receive_request`
2. `classify_use_case`
3. `load_context`
4. `plan_tasks`
5. `dispatch_agents`
6. `collect_results`
7. `synthesize_response`
8. `run_guardrails`
9. `human_approval_if_needed`
10. `publish_final_response`

Edges:
- If use case = requirement validation -> dispatch Document Analyst, Research, Agile, Developer
- If use case = release validation -> dispatch Research, Developer, Agile, Document Analyst
- If compliance confidence < threshold -> HITL
- If tool failure -> retry or dead letter

## Agent Graph Pattern

Each specialist agent uses:

```text
receive_subtask
  -> recall_memory
  -> reason
  -> act_tool_call
  -> observe_result
  -> decide_continue_or_finish
  -> produce_structured_result
```

Loop until:
- sufficient evidence found
- max iterations reached
- human approval required
- tool error becomes unrecoverable

## Dead Letter Handling
Any failed message after retry policy must go to `dead.letter` with:
- request_id
- agent_name
- payload
- error
- retry_count
- timestamp
