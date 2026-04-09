---
name: /mobile-review
summary: Review local mobile artifacts with safe file heuristics and optional YARA.
workflow: mobile-review
agent: mobile-app-analyzer
usage: black-spyder-agent slash /mobile-review target_path=artifacts/mobile_app_extracted
examples:
  - black-spyder-agent slash /mobile-review target_path=artifacts/mobile_app_extracted
passthrough_args:
  - target_path
  - rules_path
---

# /mobile-review

Review local mobile artifacts using the Black-Spyder mobile-app-analyzer flow.
