# Black-Spyder

[English](README.md) | [한국어](README.ko.md)

`Black-Spyder`는 명시적으로 승인된 대상만을 위한 증거 중심 보안 점검 워크스페이스입니다. 운영자가 범위를 검증하고, 저위험 관찰을 수집하고, 산출물을 비교하고, 재현 가능한 finding을 작성할 수 있도록 설계되어 있습니다. 공격 자동화 도구가 아니라 운영자 통제형 방어 진단 도구입니다.

## 프로젝트 개요

`Black-Spyder`는 범위 검증, 단일 HTTP 관찰 수집, 응답 비교, 구조 힌트 추출, finding 작성까지를 하나의 안전한 작업 흐름으로 제공합니다. 모든 판단은 저장된 증거를 기준으로 하며, 정책과 산출물 없이 결론을 내리지 않도록 설계되어 있습니다.

## 안전 모델

- `policies/scope.yaml`에 명시된 호스트만 범위에 포함됩니다
- 자동 실행되는 메서드는 `GET`, `HEAD`, `OPTIONS`로 제한됩니다
- `POST`, `PUT`, `PATCH`, `DELETE`는 승인 전용이며 기본 도구는 자동 실행하지 않습니다
- 요청 본문, 동시성, 무차별 대입, 퍼징, 대량 스캔을 지원하지 않습니다
- `production_allowed: true`를 의도적으로 설정하지 않는 한 운영 환경성 대상은 금지됩니다
- 결론보다 산출물 저장이 먼저입니다
- 저장되는 헤더 값 중 민감 정보는 마스킹됩니다

## 아키텍처

### 에이전트 문서

- `agents/sec-orchestrator.md`, `agents/sec-orchestrator.ko.md`는 안전한 다음 단계 선택 기준을 제공합니다
- `agents/recon-reader.md`, `agents/recon-reader.ko.md`는 관찰 결과 해석 원칙을 설명합니다
- `agents/auth-analyzer.md`, `agents/auth-analyzer.ko.md`는 비교 기반 인가 검토 절차를 정의합니다
- `agents/evidence-writer.md`, `agents/evidence-writer.ko.md`는 재현 가능한 finding 작성 기준을 설명합니다
- `agents/mobile-app-analyzer.md`, `agents/mobile-app-analyzer.ko.md`는 비파괴 모바일 산출물 분석과 백엔드 연동 단서 검토 기준을 제공합니다

### 명령 카탈로그

- `commands/*.md`에는 `/agents`, `/observe-safe`, `/recon`, `/compare-auth`, `/mobile-review`, `/write-finding`, `/sessions`, `/session-show`, `/next-step`, `/doctor` 같은 slash-style 명령 스펙이 저장됩니다
- `black-spyder-agent commands`로 사용 가능한 명령 카탈로그를 확인할 수 있습니다
- `black-spyder-agent ecosystem`은 현재 에이전트 카탈로그, 명령 카탈로그, 핵심 경로를 한 번에 machine-readable 형태로 출력합니다
- `black-spyder-agent slash ...`는 카탈로그에 등록된 워크플로우를 로컬 런타임으로 실행합니다

### MCP 도구

- `mcp/scope_guard.py`는 스킴, 호스트, 메서드, 금지 경로, 운영 환경성 여부를 검증합니다
- `mcp/http_probe.py`는 단일 관찰 요청을 수행하고 raw/normalized 산출물을 기록합니다
- `mcp/response_diff.py`는 normalized 산출물 두 개를 결정적으로 비교합니다
- `mcp/schema_extract.py`는 저장된 응답에서 필드, 경로 패턴, 인증 단서를 추출합니다
- `mcp/artifact_writer.py`는 허용된 경로 내부에만 finding 또는 evidence를 기록합니다
- `mcp/yara_scan.py`는 로컬 룰 또는 운영자 제공 룰을 사용해 로컬 산출물에 대해 읽기 전용 YARA 스캔을 수행합니다
- `mcp/common.py`는 정책 로딩, 마스킹, 해시 계산, JSON 저장 공통 기능을 제공합니다

### LLM 오케스트레이션 모델

- LLM은 후보 경로와 다음 액션을 제안만 합니다
- 실제 범위 판정은 `mcp/scope_guard.py`가 결정적으로 수행합니다
- `tools/orchestrate_candidates.py`로 후보 경로를 허용/차단으로 분류합니다
- `forbidden_path_patterns`에 걸리는 경로는 `approved_path_exceptions`에 명시된 경우에만 예외 허용됩니다
- 실제 실행은 `mcp/http_probe.py`로 한 번에 한 요청씩만 진행합니다

### 실행형 에이전트 런타임

- `tools/agent_runtime.py`는 markdown 에이전트 스펙과 실제 워크플로우를 연결하는 로컬 router/session 레이어입니다
- `tools/ecosystem.py`는 `agents/`와 `commands/`에서 machine-readable 메타데이터를 읽어 에이전트/명령 카탈로그를 구성합니다
- `tools/agent_cli.py`는 `route`, `observe`, `recon`, `compare-auth`, `mobile-review`, `write-finding`, `next-step` 같은 운영자용 명령을 제공합니다
- `black-spyder-agent`는 같은 런타임을 위한 설치형 콘솔 엔트리포인트입니다
- `state/state.json`은 추적 가능한 템플릿으로만 유지하고, 로컬 런타임 요약과 세션은 gitignored `state/runtime_state.json`에 저장합니다

### 정책 시스템

- `policies/scope.yaml`이 허용 호스트, 스킴, 메서드, 제한값의 단일 기준점입니다
- `AGENTS.md`가 전체 비파괴 운영 원칙을 정의합니다
- `state/state.json`은 dry run 초기화를 위한 tracked baseline template이고, 실제 운영자 작업 연속성은 `state/runtime_state.json`에 기록됩니다

## 설치

### bootstrap 사용

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

### 수동 설치 대안

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

## 사용 방법

### dry run

```bash
python tools/dry_run.py
```

dry run은 정책을 로드하고, 허용 호스트 및 메서드를 출력하고, 샘플 URL을 `scope_guard`로 검증하고, 필요 시 `state/state.json`을 초기화한 뒤, 실제 요청 없이 다음 안전한 작업을 제안합니다.

### 에이전트 런타임 빠른 시작

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
```

에이전트 런타임도 기본 MCP 도구와 동일한 안전 모델을 따릅니다. 즉, 정책 기반 관찰만 허용하고, 한 번에 한 단계씩 진행하며, 증거 없이 결론을 내리지 않습니다.
추적 대상인 `state/state.json`은 깨끗한 템플릿으로 남겨 두고, 실제 런타임 요약과 세션 타임라인은 `state/runtime_state.json`에 기록하여 일반 실행만으로 저장소 상태 파일이 더러워지지 않게 했습니다.
이제 bootstrap은 ecosystem index를 생성하고, 운영자가 직접 보는 것과 같은 구조화된 doctor 보고서를 함께 실행합니다.

### 도구 사용 예시

아래 명령은 `.venv`가 이미 활성화되어 있다는 전제를 가집니다. 가상환경을 활성화하지 않을 경우 macOS/Linux에서는 `python` 대신 `./.venv/bin/python`을 사용하십시오.

```bash
python mcp/scope_guard.py --url http://example.local/ --method GET
python mcp/http_probe.py --url http://localhost:8000/health --method GET
python mcp/response_diff.py --left-artifact-path evidence/normalized/left.json --right-artifact-path evidence/normalized/right.json
python mcp/schema_extract.py --artifact-path evidence/normalized/example.json
python mcp/yara_scan.py --target-path artifacts/mobile_app_extracted
python mcp/artifact_writer.py --relative-path findings/example.md --mode text --content "# Example"
```

## 정책 수정

실제 점검 전에 반드시 `policies/scope.yaml`을 수정하십시오.

- `allowed_hosts`는 구체적으로 관리합니다
- 명시적 승인과 거버넌스 검토 없이는 `production_allowed: false`를 유지합니다
- 변경 메서드는 `approval_required_methods`에 남겨 둡니다
- 절대 접근하지 않을 경로는 `forbidden_path_patterns`로 막습니다
- `max_response_bytes`, `request_timeout_seconds`는 보수적으로 유지합니다

## 증거 워크플로우

1. `scope_guard`로 요청 범위를 검증합니다
2. `http_probe`로 안전한 단일 관찰을 수집합니다
3. raw/normalized 산출물을 먼저 저장합니다
4. 여러 관찰이 있으면 `response_diff`로 비교합니다
5. 필요 시 `schema_extract`로 구조 힌트를 보강합니다
6. 필요 시 `yara_scan`으로 로컬 산출물에서 보호기법/SDK 단서를 패턴 기반으로 보강합니다
7. 증거 저장이 끝난 뒤에만 `artifact_writer`로 finding을 작성합니다

## 승인 기반 자동화

LLM으로 절차를 자동화하더라도, 실행 가능 여부를 모델이 직접 결정하면 안 됩니다. 안전한 흐름은 다음과 같습니다.

1. LLM이 후보 경로를 제안합니다
2. `tools/orchestrate_candidates.py`로 정책 기준 허용/차단 여부를 분류합니다
3. 금지 패턴 경로는 `policies/scope.yaml`의 `approved_path_exceptions`에 명시적으로 승인된 경우에만 예외 허용합니다
4. 허용된 경로만 `mcp/http_probe.py`로 한 번에 한 요청씩 실행합니다

예시:

```bash
python tools/orchestrate_candidates.py \
  --base-url https://loaflex.com \
  --paths '["/", "/robots.txt", "/admin", "/debug"]'
```

## 제한사항

- 이 워크스페이스는 의도적으로 읽기 전용, 저빈도 모델을 유지합니다
- 익스플로잇, 스캐너 오케스트레이션, 우회 로직은 포함하지 않습니다
- 인가 분석은 비교 증거가 확보되기 전까지 가설 수준을 유지합니다
- `schema_extract`의 JSON 추정은 미리보기 기반이므로 잘린 본문에서는 불완전할 수 있습니다
- YARA 지원은 선택 사항이며 패턴 기반 단서 제공용입니다. 매치 결과만으로 결론을 확정하면 안 됩니다

## 고지 사항 (인가된 사용만 허용)

`Black-Spyder`는 명시적 승인을 받은 환경에서만 사용해야 합니다. 포함된 도구와 문서는 의도적으로 보수적이며, 모든 동작은 운영자 통제 하에 수행되어야 합니다.
