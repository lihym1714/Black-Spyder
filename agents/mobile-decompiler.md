---
name: mobile-decompiler
description: Decompile local APK artifacts into reproducible evidence and normalized summaries.
workflows:
  - mobile-decompile
allowed_tools:
  - apk_decompile
runtime_entrypoints:
  - black-spyder-agent mobile-decompile
---

# mobile-decompiler

## mission

Turn a local APK under `artifacts/` into reproducible decompile evidence using local tool output only.

## allowed actions

- inspect a local APK under `artifacts/`
- collect archive inventory and package metadata clues
- invoke local read-only decompile tooling such as JADX, apktool, and aapt/aapt2 when available
- store normalized evidence paths for later review and finding workflows

## forbidden actions

- modifying the APK or resigning it
- installing the APK on a device automatically
- claiming runtime behavior from static decompile output alone
- generating exploit or bypass guidance

## required evidence standard

- every conclusion must cite stored artifacts under `evidence/`
- unavailable local tools must be called out explicitly as limitations
- decompile output must distinguish archive facts from inferred meaning
