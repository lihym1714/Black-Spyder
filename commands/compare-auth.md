---
name: /compare-auth
summary: Compare two stored normalized artifacts for authorization clues.
workflow: compare-auth
agent: auth-analyzer
usage: black-spyder-agent slash /compare-auth left_artifact_path=evidence/normalized/left.json right_artifact_path=evidence/normalized/right.json
examples:
  - black-spyder-agent slash /compare-auth left_artifact_path=evidence/normalized/left.json right_artifact_path=evidence/normalized/right.json
passthrough_args:
  - left_artifact_path
  - right_artifact_path
---

# /compare-auth

Compare two stored artifacts to keep authorization claims evidence-driven.
