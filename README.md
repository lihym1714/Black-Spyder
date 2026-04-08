# sec-agent

[English](README.md) | [한국어](README.ko.md)

`sec-agent` is a controlled, evidence-driven security assessment workspace for explicitly authorized targets only.  
`sec-agent`는 명시적으로 승인된 대상만 다루는 증거 중심 보안 점검 워크스페이스입니다.

## Project overview

`sec-agent` helps an operator validate scope, capture one safe HTTP observation at a time, compare stored artifacts, extract response structure hints, and write reproducible findings. It is designed for operator-controlled defensive review and documentation, not offensive testing.

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

### MCP tools

- `mcp/scope_guard.py` validates scheme, host, method, forbidden paths, and production-like targets
- `mcp/http_probe.py` performs one observational request and writes raw and normalized artifacts
- `mcp/response_diff.py` compares two normalized observations deterministically
- `mcp/schema_extract.py` extracts candidate fields, endpoint patterns, and auth hints from stored observations
- `mcp/artifact_writer.py` writes findings or evidence only inside approved project paths
- `mcp/common.py` holds shared policy, masking, hashing, and JSON helpers

### LLM orchestration model

- let the LLM propose candidate paths and next actions
- keep scope enforcement deterministic in `mcp/scope_guard.py`
- use `tools/orchestrate_candidates.py` to classify proposed paths into allowed vs blocked
- if a path matches `forbidden_path_patterns`, only an explicit `approved_path_exceptions` entry can override it
- keep execution one request at a time through `mcp/http_probe.py`

### policy system

- `policies/scope.yaml` is the source of truth for allowed hosts, schemes, methods, rate limits, and response caps
- `AGENTS.md` defines the global non-destructive operating rules
- `state/state.json` stores local workflow state for dry-run initialization and operator continuity

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

## Usage

### dry run

```bash
python tools/dry_run.py
```

The dry run loads the policy, prints allowed hosts and methods, validates a sample URL with `scope_guard`, initializes `state/state.json` if needed, and prints the next recommended safe action without making a live request.

### tool usage examples

```bash
python mcp/scope_guard.py --url http://example.local/ --method GET
python mcp/http_probe.py --url http://localhost:8000/health --method GET
python mcp/response_diff.py --left-artifact-path evidence/normalized/left.json --right-artifact-path evidence/normalized/right.json
python mcp/schema_extract.py --artifact-path evidence/normalized/example.json
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
6. write findings with `artifact_writer` only after evidence is stored

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

## Disclaimer (authorized use only)

Use `sec-agent` only in environments where you have explicit authorization to perform a security assessment. The included tooling is intentionally conservative and operator-controlled.
