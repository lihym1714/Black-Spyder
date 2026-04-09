---
name: /session-search
summary: Search stored runtime sessions by query or structured filters.
workflow: session-search
agent: sec-orchestrator
usage: black-spyder-agent slash /session-search workflow=observe status=completed
examples:
  - black-spyder-agent slash /session-search workflow=observe status=completed
  - black-spyder-agent slash /session-search query=loaflex
passthrough_args:
  - query
  - workflow
  - status
  - agent
---

# /session-search

Search local runtime sessions without manually opening runtime state files.
