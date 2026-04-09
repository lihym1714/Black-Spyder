---
name: /converse
summary: Accept a conversational request and extract the safest structured analysis input automatically.
workflow: converse
agent: sec-orchestrator
usage: black-spyder-agent slash /converse goal="웹 페이지 진단해줘 https://example.com"
examples:
  - black-spyder-agent slash /converse goal="웹 페이지 진단해줘 https://example.com"
  - black-spyder-agent slash /converse goal="~/apk 분석해줘"
passthrough_args:
  - goal
---

# /converse

Accept a conversational request, extract the likely target, ask one follow-up when needed, and then route to the safest analysis workflow.
