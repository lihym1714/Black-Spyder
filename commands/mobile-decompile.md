---
name: /mobile-decompile
summary: Decompile a local APK under artifacts/ into reproducible evidence.
workflow: mobile-decompile
agent: mobile-decompiler
usage: black-spyder-agent slash /mobile-decompile apk_path=artifacts/mobile/example.apk
examples:
  - black-spyder-agent slash /mobile-decompile apk_path=artifacts/mobile/example.apk
passthrough_args:
  - apk_path
---

# /mobile-decompile

Generate evidence-backed APK decompile artifacts from a local APK path.
