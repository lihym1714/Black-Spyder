---
name: /analyze
summary: Let Black-Spyder route and run the safest matching analysis path from a natural-language goal.
workflow: analyze
agent: sec-orchestrator
usage: black-spyder-agent slash /analyze goal="Review this target safely" url=http://localhost:8000/health
examples:
  - black-spyder-agent slash /analyze goal="Review this target safely" url=http://localhost:8000/health
  - black-spyder-agent slash /analyze goal="Review this artifact" artifact_path=evidence/normalized/example.json
passthrough_args:
  - goal
  - url
  - method
  - artifact_path
  - left_artifact_path
  - right_artifact_path
  - target_path
  - rules_path
---

# /analyze

Accept a natural-language goal and let Black-Spyder choose the safest matching analysis workflow automatically.
