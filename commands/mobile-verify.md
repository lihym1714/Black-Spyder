---
name: /mobile-verify
summary: Capture adb-based runtime evidence for an Android package.
workflow: mobile-verify
agent: mobile-dynamic-verifier
usage: black-spyder-agent slash /mobile-verify package_name=com.example.app
examples:
  - black-spyder-agent slash /mobile-verify package_name=com.example.app
passthrough_args:
  - package_name
  - device_id
---

# /mobile-verify

Collect reproducible adb runtime evidence for an installed Android package.
