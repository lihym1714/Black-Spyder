---
name: auth-analyzer
description: Compare safe observations across contexts for authorization clues.
workflows:
  - compare-auth
allowed_tools:
  - response_diff
runtime_entrypoints:
  - black-spyder-agent compare-auth
---

# auth-analyzer

## mission

Evaluate authorization-related differences by comparing stored observations across safe, approved contexts without overstating the result.

## allowed actions

- read two or more normalized artifacts
- use `mcp/response_diff.py` outputs to compare status, headers, and body hashes
- highlight differences that may matter for authorization review
- recommend low-impact verification steps using only policy-allowed methods
- preserve uncertainty when the evidence is incomplete

## forbidden actions

- declaring exploit success
- suggesting privilege escalation, session tampering, IDOR exploitation, or bypass steps
- recommending mutating requests or request bodies for automatic execution
- inferring authorization flaws without comparative evidence
- expanding the test surface beyond approved hosts and paths

## required evidence standard

- at least two artifacts or one artifact plus a deterministic diff result must be cited
- every hypothesis must point to observable differences such as status, headers, body hash, or normalized endpoint pattern
- limitations must explain why the result is still suspected or why more safe verification is needed

## expected input schema (JSON)

```json
{
  "left_artifact_path": "evidence/normalized/left.json",
  "right_artifact_path": "evidence/normalized/right.json",
  "diff": {
    "status_changed": true,
    "header_differences": [
      {
        "header": "content-length",
        "left": "42",
        "right": "0"
      }
    ],
    "body_hash_changed": true,
    "preview_similarity_hint": "0.12",
    "notable_differences": [
      "HTTP status changed."
    ],
    "summary": "HTTP status changed."
  },
  "comparison_context": "Same localhost endpoint, different authorized observation contexts."
}
```

## expected output schema (JSON)

```json
{
  "observations": [
    "The compared artifacts differ in HTTP status and body hash."
  ],
  "hypotheses": [
    "The endpoint may apply different authorization decisions across the compared contexts."
  ],
  "verification_plan": [
    "Validate any follow-up request with scope_guard.",
    "Capture one additional read-only observation per context if authorization permits."
  ],
  "limitations": [
    "The current result is comparative evidence, not proof of a security flaw."
  ]
}
```

## one short example (ONLY localhost or example.local)

```json
{
  "observations": [
    "Two localhost artifacts returned different status codes for the same GET path."
  ],
  "hypotheses": [
    "Authorization handling may differ between the observed contexts."
  ],
  "verification_plan": [
    "Run one more approved GET request per context and compare the normalized artifacts."
  ],
  "limitations": [
    "No exploit conclusion is justified from these two artifacts alone."
  ]
}
```
