# sec-agent

[English](README.md) | [한국어](README.ko.md)

`sec-agent`는 명시적으로 승인된 대상만을 위한 증거 중심 보안 점검 워크스페이스입니다. 운영자가 범위를 검증하고, 저위험 관찰을 수집하고, 산출물을 비교하고, 재현 가능한 finding을 작성할 수 있도록 설계되어 있습니다. 공격 자동화 도구가 아니라 운영자 통제형 방어 진단 도구입니다.

## 프로젝트 개요

`sec-agent`는 범위 검증, 단일 HTTP 관찰 수집, 응답 비교, 구조 힌트 추출, finding 작성까지를 하나의 안전한 작업 흐름으로 제공합니다. 모든 판단은 저장된 증거를 기준으로 하며, 정책과 산출물 없이 결론을 내리지 않도록 설계되어 있습니다.

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

### MCP 도구

- `mcp/scope_guard.py`는 스킴, 호스트, 메서드, 금지 경로, 운영 환경성 여부를 검증합니다
- `mcp/http_probe.py`는 단일 관찰 요청을 수행하고 raw/normalized 산출물을 기록합니다
- `mcp/response_diff.py`는 normalized 산출물 두 개를 결정적으로 비교합니다
- `mcp/schema_extract.py`는 저장된 응답에서 필드, 경로 패턴, 인증 단서를 추출합니다
- `mcp/artifact_writer.py`는 허용된 경로 내부에만 finding 또는 evidence를 기록합니다
- `mcp/common.py`는 정책 로딩, 마스킹, 해시 계산, JSON 저장 공통 기능을 제공합니다

### 정책 시스템

- `policies/scope.yaml`이 허용 호스트, 스킴, 메서드, 제한값의 단일 기준점입니다
- `AGENTS.md`가 전체 비파괴 운영 원칙을 정의합니다
- `state/state.json`은 dry run 초기화와 운영자 작업 연속성을 위한 로컬 상태 파일입니다

## 설치

### bootstrap 사용

macOS / Linux

```bash
cd /Users/everspin/Side/black-spyder/sec-agent
python3 tools/bootstrap.py
source .venv/bin/activate
```

Windows PowerShell

```powershell
cd /Users/everspin/Side/black-spyder/sec-agent
python tools\bootstrap.py
.\.venv\Scripts\Activate.ps1
```

### 수동 설치 대안

macOS / Linux

```bash
cd /Users/everspin/Side/black-spyder/sec-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Windows PowerShell

```powershell
cd /Users/everspin/Side/black-spyder/sec-agent
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

### 도구 사용 예시

```bash
python mcp/scope_guard.py --url http://example.local/ --method GET
python mcp/http_probe.py --url http://localhost:8000/health --method GET
python mcp/response_diff.py --left-artifact-path evidence/normalized/left.json --right-artifact-path evidence/normalized/right.json
python mcp/schema_extract.py --artifact-path evidence/normalized/example.json
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
6. 증거 저장이 끝난 뒤에만 `artifact_writer`로 finding을 작성합니다

## 제한사항

- 이 워크스페이스는 의도적으로 읽기 전용, 저빈도 모델을 유지합니다
- 익스플로잇, 스캐너 오케스트레이션, 우회 로직은 포함하지 않습니다
- 인가 분석은 비교 증거가 확보되기 전까지 가설 수준을 유지합니다
- `schema_extract`의 JSON 추정은 미리보기 기반이므로 잘린 본문에서는 불완전할 수 있습니다

## 고지 사항 (인가된 사용만 허용)

`sec-agent`는 명시적 승인을 받은 환경에서만 사용해야 합니다. 포함된 도구와 문서는 의도적으로 보수적이며, 모든 동작은 운영자 통제 하에 수행되어야 합니다.
