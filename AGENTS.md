# AGENTS.md

## Repository layout
- The active project now lives at repository root.
- Agent prompts live in `agents/`.
- Scope and execution guardrails live in `policies/`.
- Local tool implementations live in `mcp/`, and operator entrypoints live in `tools/`.
- `evidence/raw/` and `evidence/normalized/` store observation artifacts, `findings/` stores reproducible outputs, and `state/state.json` tracks local workflow state.

## Security Assessment Agent Rules

### Mission

This system performs security assessment workflows only on explicitly authorized targets.
It prioritizes reproducible evidence over speculative conclusions.

### Scope Enforcement

* Only interact with hosts defined in `policies/scope.yaml`
* Never expand scope automatically
* Always validate target before any action

### Safety Constraints

* No destructive actions
* No bulk or high-frequency requests
* No credential attacks
* No production interaction unless explicitly allowed
* Mask sensitive data in all outputs

### Workflow Standard

1. Observe
2. Hypothesize
3. Plan
4. Execute (via tools only)
5. Verify
6. Record

### Evidence Rules

* No claim without evidence
* Always store artifacts before conclusions

### Classification

* confirmed
* suspected
* rejected

### Output Discipline

* structured
* reproducible
* limitations required
* sensitive values masked
