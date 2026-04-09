# Black-Spyder

[English](README.md) | [한국어](README.ko.md)

`Black-Spyder` is a controlled, evidence-driven security assessment workspace for explicitly authorized targets only.  
`Black-Spyder`는 명시적으로 승인된 대상만 다루는 증거 중심 보안 점검 워크스페이스입니다.

## Project overview

`Black-Spyder` helps an operator validate scope, capture one safe HTTP observation at a time, compare stored artifacts, extract response structure hints, and write reproducible findings. It is designed for operator-controlled defensive review and documentation, not offensive testing.

## Safety model

- only explicitly authorized hosts from `policies/scope.yaml` are in scope
- only `GET`, `HEAD`, and `OPTIONS` run automatically
- `POST`, `PUT`, `PATCH`, and `DELETE` remain approval-only and are not auto-executed by the included tools
- no request bodies, concurrency, brute force, fuzzing, or bulk scanning
- no production-like targets unless `production_allowed: true` is set intentionally
- artifacts are written before conclusions
- sensitive headers are masked in stored outputs

## Architecture

### agents

- `agents/sec-orchestrator.md` and `agents/sec-orchestrator.ko.md` guide safe next-step planning
- `agents/recon-reader.md` and `agents/recon-reader.ko.md` describe evidence-based observation review
- `agents/auth-analyzer.md` and `agents/auth-analyzer.ko.md` cover comparison-based authorization review
- `agents/evidence-writer.md` and `agents/evidence-writer.ko.md` explain reproducible finding generation
- `agents/mobile-app-analyzer.md` and `agents/mobile-app-analyzer.ko.md` cover non-destructive mobile artifact analysis and backend-integration clue review

### command catalog

- `commands/*.md` stores slash-style command specs such as `/agents`, `/observe-safe`, `/recon`, `/compare-auth`, `/mobile-review`, `/write-finding`, `/sessions`, `/session-show`, `/next-step`, and `/doctor`
- `black-spyder-agent commands` lists the available command catalog entries
- `black-spyder-agent ecosystem` dumps the current agent catalog, command catalog, and core ecosystem paths in one machine-readable view
- `black-spyder-agent slash ...` runs cataloged workflows through the local runtime

### MCP tools

- `mcp/scope_guard.py` validates scheme, host, method, forbidden paths, and production-like targets
- `mcp/http_probe.py` performs one observational request and writes raw and normalized artifacts
- `mcp/response_diff.py` compares two normalized observations deterministically
- `mcp/schema_extract.py` extracts candidate fields, endpoint patterns, and auth hints from stored observations
- `mcp/artifact_writer.py` writes findings or evidence only inside approved project paths
- `mcp/yara_scan.py` runs optional read-only YARA scans against local artifacts using local rules or operator-supplied rules
- `mcp/common.py` holds shared policy, masking, hashing, and JSON helpers

### LLM orchestration model

- let the LLM propose candidate paths and next actions
- keep scope enforcement deterministic in `mcp/scope_guard.py`
- use `tools/orchestrate_candidates.py` to classify proposed paths into allowed vs blocked
- if a path matches `forbidden_path_patterns`, only an explicit `approved_path_exceptions` entry can override it
- keep execution one request at a time through `mcp/http_probe.py`

### executable agent runtime

- `tools/agent_runtime.py` is the local router/session layer that pairs the markdown agent specs with runnable workflows
- `tools/ecosystem.py` loads machine-readable agent metadata and slash-command catalog metadata from `agents/` and `commands/`
- `tools/agent_cli.py` exposes operator-facing commands such as `route`, `observe`, `recon`, `compare-auth`, `mobile-review`, `write-finding`, and `next-step`
- `black-spyder-agent` is the installed console entrypoint for the same runtime
- `tools/opencode_bridge.py` exposes the final OpenCode-facing bridge layer for host registration, registry discovery, and command execution
- `black-spyder-opencode-bridge` starts that host bridge on `127.0.0.1:8787`
- `state/state.json` stays as a tracked template, while local runtime summaries and sessions live in gitignored `state/runtime_state.json`

### policy system

- `policies/scope.yaml` is the source of truth for allowed hosts, schemes, methods, rate limits, and response caps
- `AGENTS.md` defines the global non-destructive operating rules
- `state/state.json` remains the tracked baseline template used for dry-run initialization, while live operator continuity lives in `state/runtime_state.json`

## Installation

### bootstrap usage

macOS / Linux

```bash
cd /path/to/repo
python3 tools/bootstrap.py
source .venv/bin/activate
```

Windows PowerShell

```powershell
cd C:\path\to\repo
python tools\bootstrap.py
.\.venv\Scripts\Activate.ps1
```

### manual fallback

macOS / Linux

```bash
cd /path/to/repo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Windows PowerShell

```powershell
cd C:\path\to\repo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

### Installation for LLM

Paste this prompt into OpenCode as-is to let it handle installation, bridge startup, and initial host connection in one flow:

```text
Set up and connect Black-Spyder for this session.

Do these steps in order:
1. If the current working directory is not already the Black-Spyder repository root, clone `https://github.com/lihym1714/Black-Spyder.git` and enter that directory.
2. Run `python3 tools/bootstrap.py`.
3. Start the simplest OpenCode-ready flow by running `./.venv/bin/black-spyder opencode up`.
4. Wait until `http://127.0.0.1:8787/health` responds successfully.
5. If needed, POST `/connect` with:
   {
     "host_name": "opencode-host",
     "host_version": "1.0",
      "capabilities": ["registry", "execute"]
   }
6. Treat the returned registry as the available command surface for this session.
7. When the user asks in plain conversation, use POST `/converse` first.
8. Use POST `/analyze` when the target is already structured as a URL or file path.
9. Use POST `/execute` only when you intentionally want a specific lower-level slash command.

At the end, report:
- whether bootstrap succeeded,
- whether the bridge is reachable,
- whether `/connect` succeeded,
- and confirm that plain conversation should use `/converse` while structured inputs should use `/analyze`.
```

## Usage

### dry run

```bash
python tools/dry_run.py
```

The dry run loads the policy, prints allowed hosts and methods, validates a sample URL with `scope_guard`, initializes `state/state.json` if needed, and prints the next recommended safe action without making a live request.

### agent runtime quick start

### easiest way

```bash
black-spyder opencode up
```

This starts the local OpenCode bridge on `127.0.0.1:8787` and prepares the default OpenCode host connection state.

For the simplest prompt-first usage, let OpenCode call `/converse` first and only use `/analyze` when it already extracted a concrete URL or file path.

```bash
black-spyder-agent registry
black-spyder-agent commands
black-spyder-agent ecosystem
black-spyder-agent doctor
black-spyder-agent session-search --workflow observe --status completed
black-spyder-agent session-show --session-id session-1234abcd
black-spyder-agent session-resume --session-id session-1234abcd
black-spyder-agent route --url http://localhost:8000/health --method GET
black-spyder-agent observe --url http://localhost:8000/health --plan-only
black-spyder-agent recon --artifact-path evidence/normalized/example.json
black-spyder-agent compare-auth --left-artifact-path evidence/normalized/left.json --right-artifact-path evidence/normalized/right.json
black-spyder-agent mobile-review --target-path artifacts/mobile_app_extracted
black-spyder-agent slash /observe-safe url=http://localhost:8000/health method=GET execute=false
black-spyder-agent sessions
black-spyder-agent slash /session-search workflow=observe status=completed
black-spyder-agent slash /session-show session_id=session-1234abcd
black-spyder-agent slash /session-resume session_id=session-1234abcd
black-spyder-agent next-step
black-spyder up
black-spyder opencode up
black-spyder converse --goal "웹 페이지 진단해줘 https://example.com"
black-spyder converse --goal "apk 분석해줘"
```

The agent runtime keeps the same safety model as the underlying MCP tools: policy-gated observation only, one step at a time, and evidence before conclusions.
Tracked `state/state.json` remains a clean template, while local runtime summaries and session timelines are written to `state/runtime_state.json` so normal execution does not dirty the repository state file.
Bootstrap now generates the ecosystem index and runs the same structured doctor report that operators can inspect manually.

### OpenCode host bridge

Run `black-spyder opencode up` for the simplest OpenCode-oriented flow, or `black-spyder up` / `black-spyder-opencode-bridge` if you only want to start the bridge.

Available endpoints:

- `GET /health` returns bridge health plus the structured doctor report
- `GET /registry` returns the machine-readable bridge manifest and ecosystem catalog
- `POST /connect` performs host registration and returns the registry in one response
- `POST /converse` accepts a plain conversational request, extracts likely inputs, and asks one follow-up question when needed
- `POST /analyze` accepts a natural-language goal and lets Black-Spyder choose and run the safest matching workflow automatically
- `POST /register-host` records a local host registration
- `POST /execute` runs one slash-style command through the existing runtime

### Conversation extraction layer vs structured analysis

- Use `/converse` when the user just talks naturally, for example: `웹 페이지 진단해줘 https://example.com` or `apk 분석해줘`
- Use `/analyze` when the host already knows the structured target, for example a concrete `url` or `target_path`
- For APK-style prompts without a path, `/converse` now returns one clarification question asking which app or APK path to analyze

### tool usage examples

These commands assume you already activated `.venv`. If you prefer not to activate it, replace `python` with `./.venv/bin/python` on macOS/Linux.

```bash
python mcp/scope_guard.py --url http://example.local/ --method GET
python mcp/http_probe.py --url http://localhost:8000/health --method GET
python mcp/response_diff.py --left-artifact-path evidence/normalized/left.json --right-artifact-path evidence/normalized/right.json
python mcp/schema_extract.py --artifact-path evidence/normalized/example.json
python mcp/yara_scan.py --target-path artifacts/mobile_app_extracted
python mcp/artifact_writer.py --relative-path findings/example.md --mode text --content "# Example"
```

## Policy editing

Update `policies/scope.yaml` before any real assessment.

- keep `allowed_hosts` explicit
- keep `production_allowed: false` unless you have explicit authorization and governance approval
- keep mutating methods in `approval_required_methods`
- use `forbidden_path_patterns` to block sensitive areas you never want the tools to touch
- keep `max_response_bytes` and `request_timeout_seconds` conservative

## Evidence workflow

1. validate the candidate request with `scope_guard`
2. capture one safe observation with `http_probe`
3. store raw and normalized artifacts automatically
4. compare artifacts with `response_diff` when multiple observations exist
5. extract structure hints with `schema_extract` if needed
6. optionally run `yara_scan` for pattern-based control and SDK clues in local artifacts
7. write findings with `artifact_writer` only after evidence is stored

## Approval-gated automation

For LLM-driven planning, do not let the model directly decide execution eligibility. Instead:

1. have the LLM propose candidate paths
2. run `tools/orchestrate_candidates.py` to classify them against policy
3. add only explicitly approved forbidden-path exceptions to `policies/scope.yaml`
4. run `mcp/http_probe.py` one request at a time for the allowed set

Example:

```bash
python tools/orchestrate_candidates.py \
  --base-url https://loaflex.com \
  --paths '["/", "/robots.txt", "/admin", "/debug"]'
```

## Limitations

- this workspace is intentionally read-only and low-volume
- it does not implement exploitation, scanner orchestration, or bypass logic
- authorization analysis remains hypothesis-driven until supported by comparative evidence
- JSON preview parsing in `schema_extract` is best-effort and may remain incomplete for truncated bodies
- YARA support is optional and pattern-based; matches are triage clues, not proof by themselves

## Disclaimer (authorized use only)

Use `Black-Spyder` only in environments where you have explicit authorization to perform a security assessment. The included tooling is intentionally conservative and operator-controlled.
