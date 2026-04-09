---
name: /doctor
summary: Check the local Black-Spyder ecosystem registry, command catalog, and runtime state.
workflow: doctor
agent: sec-orchestrator
usage: black-spyder-agent slash /doctor
examples:
  - black-spyder-agent slash /doctor
passthrough_args:
---

# /doctor

Verify that the local Black-Spyder ecosystem is discoverable and internally consistent.

The output is machine-readable and includes per-check codes, severity, status, and remediation guidance so bootstrap and operators can use the same report.
