---
name: /write-finding
summary: Write a reproducible finding from stored evidence.
workflow: write-finding
agent: evidence-writer
usage: black-spyder-agent slash /write-finding title="Example" host=example.local endpoint=/status method=GET auth_context=anonymous classification=suspected artifacts='["evidence/normalized/example.json"]' observations='["Observed HTTP 200"]'
examples:
  - black-spyder-agent slash /write-finding title="Example" host=example.local endpoint=/status method=GET auth_context=anonymous classification=suspected artifacts='["evidence/normalized/example.json"]' observations='["Observed HTTP 200"]'
passthrough_args:
  - title
  - host
  - endpoint
  - method
  - auth_context
  - classification
  - artifacts
  - observations
  - limitations
  - remediation_notes
  - relative_output_path
---

# /write-finding

Write a markdown finding only after valid evidence artifacts already exist.
