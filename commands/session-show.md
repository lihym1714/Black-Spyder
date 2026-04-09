---
name: /session-show
summary: Show the full details of one runtime session.
workflow: session-show
agent: sec-orchestrator
usage: black-spyder-agent slash /session-show session_id=session-1234abcd
examples:
  - black-spyder-agent slash /session-show session_id=session-1234abcd
passthrough_args:
  - session_id
---

# /session-show

Inspect one recorded runtime session in full detail.
