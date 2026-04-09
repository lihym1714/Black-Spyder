---
name: /recon
summary: Summarize one stored normalized artifact.
workflow: recon
agent: recon-reader
usage: black-spyder-agent slash /recon artifact_path=evidence/normalized/example.json
examples:
  - black-spyder-agent slash /recon artifact_path=evidence/normalized/example.json
passthrough_args:
  - artifact_path
---

# /recon

Review one normalized artifact and produce evidence-based hypotheses.
