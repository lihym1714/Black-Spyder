---
name: /observe-safe
summary: Plan or execute one safe observational request.
workflow: observe
agent: sec-orchestrator
usage: black-spyder-agent slash /observe-safe url=http://localhost:8000/health method=GET execute=false
examples:
  - black-spyder-agent slash /observe-safe url=http://localhost:8000/health method=GET execute=false
  - black-spyder-agent slash /observe-safe url=http://localhost:8000/health method=GET
passthrough_args:
  - url
  - method
  - execute
---

# /observe-safe

Validate scope and either return a plan or perform one safe observational request.
