# AGENTS.md

## Repository layout
- The active project lives under `sec-agent/`.
- `sec-agent/AGENTS.md` defines the security-assessment operating rules for that project.
- Agent prompts live in `sec-agent/agents/`.
- Scope and execution guardrails live in `sec-agent/policies/`.
- Local tool implementations live in `sec-agent/mcp/`, and operator entrypoints live in `sec-agent/tools/`.
- `sec-agent/evidence/raw/` and `sec-agent/evidence/normalized/` store observation artifacts, `sec-agent/findings/` stores reproducible outputs, and `sec-agent/state/state.json` tracks local workflow state.

## Working rules for future sessions
- Treat `sec-agent/policies/scope.yaml` as the scope source of truth before proposing or simulating any action.
- Keep the system evidence-first: artifacts should be written before conclusions or finding summaries.
- Keep all tool behavior non-destructive by default: observational HTTP only, no bodies, no concurrency, no brute force, no bulk scanning.
