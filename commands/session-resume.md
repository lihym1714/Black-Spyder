---
name: /session-resume
summary: Resume one stored runtime session through its saved run manifest.
workflow: session-resume
agent: sec-orchestrator
usage: black-spyder-agent slash /session-resume session_id=session-1234abcd
examples:
  - black-spyder-agent slash /session-resume session_id=session-1234abcd
passthrough_args:
  - session_id
---

# /session-resume

Resume one stored session by replaying its saved run manifest through the declarative dispatcher.
