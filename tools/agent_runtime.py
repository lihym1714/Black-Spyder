from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from os.path import expanduser

from mcp.artifact_writer import write_artifact
from mcp.common import PROJECT_ROOT, build_request_id, load_scope_policy, utc_now_iso, write_json
from mcp.http_probe import perform_probe
from mcp.response_diff import diff_observations
from mcp.schema_extract import extract_schema
from mcp.scope_guard import evaluate_scope
from mcp.yara_scan import run_yara_scan
from tools.ecosystem import build_runtime_run_manifest, load_agent_registry

STATE_FILE = PROJECT_ROOT / "state" / "state.json"
RUNTIME_STATE_FILE = PROJECT_ROOT / "state" / "runtime_state.json"
RUNTIME_LOCK_DIR = PROJECT_ROOT / "state" / "runtime_state.lock"
FINDING_TEMPLATE = PROJECT_ROOT / "templates" / "finding.md"
AUTO_EXECUTE_METHODS = {"GET", "HEAD", "OPTIONS"}
EVIDENCE_ROOTS = [PROJECT_ROOT / "evidence" / "normalized", PROJECT_ROOT / "evidence" / "raw"]
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"


@dataclass(frozen=True)
class RouteRule:
    workflow: str
    agent_name: str
    rationale: str
    tool: str
    reason: str
def default_state_summary() -> dict[str, Any]:
    return {
        "created_at": utc_now_iso(),
        "current_target": None,
        "observations": [],
        "hypotheses": [],
        "findings": [],
    }


def default_runtime_state() -> dict[str, Any]:
    return {
        "created_at": utc_now_iso(),
        "current_target": None,
        "observations": [],
        "hypotheses": [],
        "findings": [],
        "last_session_id": None,
        "sessions": [],
    }


def load_json_file(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = cast(dict[str, Any], json.load(handle))
    except json.JSONDecodeError:
        return fallback
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return loaded


def load_state_snapshot() -> dict[str, Any]:
    state = load_json_file(STATE_FILE, default_state_summary())
    state.setdefault("created_at", utc_now_iso())
    state.setdefault("current_target", None)
    state.setdefault("observations", [])
    state.setdefault("hypotheses", [])
    state.setdefault("findings", [])
    return state


def save_state(state: dict[str, Any]) -> None:
    write_json(STATE_FILE, state)


def load_runtime_state_snapshot() -> dict[str, Any]:
    state = load_json_file(RUNTIME_STATE_FILE, default_runtime_state())
    state.setdefault("created_at", utc_now_iso())
    state.setdefault("current_target", None)
    state.setdefault("observations", [])
    state.setdefault("hypotheses", [])
    state.setdefault("findings", [])
    state.setdefault("last_session_id", None)
    state.setdefault("sessions", [])
    return state


def save_runtime_state(state: dict[str, Any]) -> None:
    write_json(RUNTIME_STATE_FILE, state)


@contextmanager
def runtime_state_lock() -> Any:
    RUNTIME_LOCK_DIR.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    while True:
        try:
            os.mkdir(RUNTIME_LOCK_DIR)
            break
        except FileExistsError:
            if time.monotonic() - started > 5:
                raise TimeoutError("Timed out acquiring runtime state lock.")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            os.rmdir(RUNTIME_LOCK_DIR)
        except FileNotFoundError:
            pass


def mutate_runtime_state(mutator: Any) -> dict[str, Any]:
    with runtime_state_lock():
        state = load_runtime_state_snapshot()
        mutator(state)
        save_runtime_state(state)
        return state


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def resolve_evidence_artifact_path(artifact_path: str) -> Path:
    candidate = Path(artifact_path)
    candidate = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    if not any(root.resolve() == candidate or root.resolve() in candidate.parents for root in EVIDENCE_ROOTS):
        raise ValueError("Artifact paths must stay inside evidence/raw or evidence/normalized.")
    if not candidate.exists():
        raise FileNotFoundError(f"Artifact path not found: {candidate}")
    return candidate


def resolve_artifact_target_path(target_path: str) -> Path:
    candidate = Path(target_path)
    candidate = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    root = ARTIFACTS_ROOT.resolve()
    if not (root == candidate or root in candidate.parents):
        raise ValueError("Mobile review target must stay inside the local artifacts/ directory.")
    if not candidate.exists():
        raise FileNotFoundError(f"Target path not found: {candidate}")
    return candidate


def update_state_summary(*, current_target: str | None = None, observations: list[str] | None = None, hypotheses: list[str] | None = None, findings: list[str] | None = None) -> None:
    def _mutate(state: dict[str, Any]) -> None:
        if current_target is not None:
            state["current_target"] = current_target
        if observations:
            cast(list[str], state["observations"]).extend(observations)
        if hypotheses:
            cast(list[str], state["hypotheses"]).extend(hypotheses)
        if findings:
            cast(list[str], state["findings"]).extend(findings)

    mutate_runtime_state(_mutate)


def start_session(workflow: str, agent_name: str, inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    session = {
        "session_id": f"session-{build_request_id()}",
        "workflow": workflow,
        "agent": agent_name,
        "run_manifest": build_runtime_run_manifest(workflow, agent_name, inputs),
        "status": "running",
        "started_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "inputs": inputs,
        "events": [],
        "result": None,
    }

    def _mutate(state: dict[str, Any]) -> None:
        cast(list[dict[str, Any]], state["sessions"]).append(session)
        state["last_session_id"] = session["session_id"]

    state = mutate_runtime_state(_mutate)
    return state, session


def append_event(state: dict[str, Any], session_id: str, phase: str, payload: dict[str, Any]) -> None:
    def _mutate(current_state: dict[str, Any]) -> None:
        sessions = cast(list[dict[str, Any]], current_state["sessions"])
        for session in sessions:
            if session["session_id"] == session_id:
                cast(list[dict[str, Any]], session["events"]).append(
                    {"phase": phase, "recorded_at": utc_now_iso(), "payload": payload}
                )
                session["updated_at"] = utc_now_iso()
                return
        raise ValueError(f"Unknown session_id: {session_id}")

    refreshed = mutate_runtime_state(_mutate)
    state.clear()
    state.update(refreshed)


def finish_session(state: dict[str, Any], session_id: str, result: dict[str, Any], status: str = "completed") -> dict[str, Any]:
    updated_session: dict[str, Any] = {}

    def _mutate(current_state: dict[str, Any]) -> None:
        nonlocal updated_session
        sessions = cast(list[dict[str, Any]], current_state["sessions"])
        for session in sessions:
            if session["session_id"] == session_id:
                session["status"] = status
                session["updated_at"] = utc_now_iso()
                session["result"] = result
                updated_session = session
                return
        raise ValueError(f"Unknown session_id: {session_id}")

    refreshed = mutate_runtime_state(_mutate)
    state.clear()
    state.update(refreshed)
    return updated_session


def list_agents() -> dict[str, Any]:
    registry = load_agent_registry()
    return {
        "agents": [asdict(spec) for spec in registry.values()],
        "count": len(registry),
    }


def select_route_rule(
    *,
    url: str | None,
    method: str,
    artifact_path: str | None,
    left_artifact_path: str | None,
    right_artifact_path: str | None,
    finding_title: str | None,
    target_path: str | None,
) -> tuple[RouteRule, dict[str, Any]]:
    ordered_rules: list[tuple[bool, RouteRule, dict[str, Any]]] = [
        (
            bool(target_path),
            RouteRule(
                workflow="mobile-review",
                agent_name="mobile-app-analyzer",
                rationale="A local artifact tree is present, so mobile artifact review is the safest specialized workflow.",
                tool="yara_scan",
                reason="Use read-only local pattern matching to gather non-destructive clues first.",
            ),
            {"target_path": target_path},
        ),
        (
            bool(left_artifact_path and right_artifact_path),
            RouteRule(
                workflow="compare-auth",
                agent_name="auth-analyzer",
                rationale="Two normalized artifacts indicate a comparison workflow for authorization review.",
                tool="response_diff",
                reason="Compare deterministic artifacts before forming any authorization hypothesis.",
            ),
            {"left_artifact_path": left_artifact_path, "right_artifact_path": right_artifact_path},
        ),
        (
            bool(artifact_path),
            RouteRule(
                workflow="recon",
                agent_name="recon-reader",
                rationale="A normalized artifact is available, so structure-first review should happen before any stronger claim.",
                tool="schema_extract",
                reason="Extract candidate fields and auth hints from stored evidence.",
            ),
            {"artifact_path": artifact_path},
        ),
        (
            bool(finding_title),
            RouteRule(
                workflow="write-finding",
                agent_name="evidence-writer",
                rationale="The operator provided finding intent, so the evidence-writer should assemble a reproducible record.",
                tool="artifact_writer",
                reason="Persist a finding only after evidence inputs are provided.",
            ),
            {"title": finding_title},
        ),
        (
            bool(url),
            RouteRule(
                workflow="observe",
                agent_name="sec-orchestrator",
                rationale="A concrete URL implies an observe-first workflow under policy control.",
                tool="scope_guard",
                reason="Scope validation must precede every safe observation.",
            ),
            {"url": url, "method": method.upper()},
        ),
    ]

    for matches, rule, payload in ordered_rules:
        if matches:
            return rule, payload

    return (
        RouteRule(
            workflow="route",
            agent_name="sec-orchestrator",
            rationale="Default to orchestrator until concrete evidence inputs identify a narrower workflow.",
            tool="scope_guard",
            reason="Validate a candidate request before any network action.",
        ),
        {"url": url or "http://example.local/", "method": method.upper()},
    )


def route_workflow(
    *,
    goal: str | None = None,
    url: str | None = None,
    method: str = "GET",
    artifact_path: str | None = None,
    left_artifact_path: str | None = None,
    right_artifact_path: str | None = None,
    finding_title: str | None = None,
    target_path: str | None = None,
) -> dict[str, Any]:
    registry = load_agent_registry()
    route_rule, route_input = select_route_rule(
        url=url,
        method=method,
        artifact_path=artifact_path,
        left_artifact_path=left_artifact_path,
        right_artifact_path=right_artifact_path,
        finding_title=finding_title,
        target_path=target_path,
    )

    return {
        "workflow": route_rule.workflow,
        "agent": asdict(registry[route_rule.agent_name]),
        "goal": goal,
        "rationale": route_rule.rationale,
        "next_action": {
            "tool": route_rule.tool,
            "reason": route_rule.reason,
            "input": route_input,
        },
        "limitations": [
            "No destructive or approval-required method will be auto-executed.",
            "Stored artifacts remain the source of truth for later analysis.",
        ],
    }


def run_observe(url: str, method: str = "GET", headers: dict[str, str] | None = None, execute: bool = True) -> dict[str, Any]:
    normalized_method = method.upper()
    inputs = {"url": url, "method": normalized_method, "execute": execute}
    state, session = start_session("observe", "sec-orchestrator", inputs)
    update_state_summary(current_target=url)
    policy = load_scope_policy()
    scope_result = evaluate_scope(url, normalized_method, policy)
    append_event(state, session["session_id"], "scope-check", scope_result)
    should_execute = execute and normalized_method in AUTO_EXECUTE_METHODS

    result: dict[str, Any] = {
        "phase": "plan" if not scope_result["allowed"] or not should_execute else "observe",
        "agent": "sec-orchestrator",
        "scope_guard": scope_result,
        "next_action": None,
        "artifacts": [],
    }

    if not scope_result["allowed"]:
        result["next_action"] = {
            "tool": "scope_guard",
            "reason": "Adjust policy or target until the request is inside scope.",
            "input": {"url": url, "method": normalized_method},
        }
        finish_session(state, session["session_id"], result)
        return result

    if not should_execute:
        result["next_action"] = {
            "tool": "http_probe",
            "reason": "Only GET, HEAD, and OPTIONS can auto-execute; other methods remain plan-only even if policy allows them.",
            "input": {"url": url, "method": normalized_method},
        }
        finish_session(state, session["session_id"], result)
        return result

    probe_result = perform_probe(url, normalized_method, headers=headers)
    append_event(state, session["session_id"], "http-probe", probe_result)
    result["probe"] = probe_result
    result["artifacts"] = list((probe_result.get("artifact_paths") or {}).values())

    normalized_path = (probe_result.get("artifact_paths") or {}).get("normalized")
    if normalized_path:
        recon_result = run_recon(normalized_path, session_id=session["session_id"], state=state)
        result["phase"] = "verify"
        result["recon"] = recon_result
        update_state_summary(
            observations=[normalized_path],
            hypotheses=cast(list[str], recon_result["hypotheses"]),
        )

    result["next_action"] = {
        "tool": "schema_extract" if normalized_path else "http_probe",
        "reason": "Review the stored normalized artifact before any conclusion.",
        "input": {"artifact_path": normalized_path} if normalized_path else {"url": url, "method": normalized_method},
    }
    finish_session(state, session["session_id"], result)
    return result


def load_json_artifact(artifact_path: str) -> dict[str, Any]:
    path = resolve_evidence_artifact_path(artifact_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_recon(artifact_path: str, session_id: str | None = None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    local_state = state
    local_session_id = session_id
    if local_state is None or local_session_id is None:
        local_state, session = start_session("recon", "recon-reader", {"artifact_path": artifact_path})
        local_session_id = session["session_id"]

    artifact = load_json_artifact(artifact_path)
    schema = extract_schema(artifact_path)
    observations = [
        f"The artifact reports HTTP {artifact.get('status')}.",
        f"The request method was {artifact.get('method', 'GET')}.",
    ]
    content_type = artifact.get("headers", {}).get("content-type")
    if content_type:
        observations.append(f"The response content type appears to be {content_type}.")

    hypotheses: list[str] = []
    if schema["candidate_fields"]:
        hypotheses.append("The response preview contains structured fields worth comparing against future observations.")
    if schema["auth_indicators"]:
        hypotheses.append("The stored response contains authentication-related hints that should stay tentative until compared.")
    if not hypotheses:
        hypotheses.append("Only a single low-impact observation is available, so stronger conclusions remain premature.")

    result = {
        "agent": "recon-reader",
        "artifact_path": artifact_path,
        "observations": observations,
        "candidate_endpoints": schema["candidate_endpoint_patterns"],
        "candidate_parameters": schema["candidate_fields"],
        "auth_hints": schema["auth_indicators"],
        "hypotheses": hypotheses,
        "limitations": schema["notes"],
    }
    append_event(local_state, local_session_id, "recon", result)
    if state is None:
        update_state_summary(hypotheses=hypotheses)
        finish_session(local_state, local_session_id, result)
    return result


def run_compare_auth(left_artifact_path: str, right_artifact_path: str) -> dict[str, Any]:
    resolve_evidence_artifact_path(left_artifact_path)
    resolve_evidence_artifact_path(right_artifact_path)
    state, session = start_session(
        "compare-auth",
        "auth-analyzer",
        {"left_artifact_path": left_artifact_path, "right_artifact_path": right_artifact_path},
    )
    diff = diff_observations(left_artifact_path, right_artifact_path)
    append_event(state, session["session_id"], "response-diff", diff)

    observations: list[str] = []
    hypotheses: list[str] = []
    if diff["status_changed"]:
        observations.append("The compared artifacts returned different HTTP status codes.")
        hypotheses.append("Authorization or request context may differ between the compared observations.")
    if diff["body_hash_changed"]:
        observations.append("The response body hash changed across the compared artifacts.")
        hypotheses.append("The endpoint behavior may vary across contexts and should be validated with one more read-only comparison.")
    if diff["header_differences"]:
        observations.append(f"{len(diff['header_differences'])} response header differences were observed.")
    if not observations:
        observations.append("No notable differences were detected between the compared artifacts.")
        hypotheses.append("Current comparative evidence does not support a stronger authorization hypothesis.")

    result = {
        "agent": "auth-analyzer",
        "left_artifact_path": left_artifact_path,
        "right_artifact_path": right_artifact_path,
        "diff": diff,
        "observations": observations,
        "hypotheses": hypotheses,
        "verification_plan": [
            "Validate every follow-up URL with scope_guard before observation.",
            "Capture at most one additional GET/HEAD/OPTIONS artifact per context if policy allows.",
            "Use response_diff again before escalating a suspected finding.",
        ],
        "limitations": [
            "Comparative evidence can justify suspicion, not exploit claims.",
            "No mutating request or body is auto-generated by this workflow.",
        ],
    }
    update_state_summary(hypotheses=hypotheses)
    finish_session(state, session["session_id"], result)
    return result


def infer_mobile_metadata(target_path: Path) -> dict[str, Any]:
    files = [path for path in target_path.rglob("*") if path.is_file()]
    extension_counts = Counter(path.suffix.lower() or "<no_ext>" for path in files)
    backend_hosts: set[str] = set()
    package_or_bundle: str | None = None
    transport_notes: list[str] = []
    evidence_entries: list[dict[str, Any]] = []

    for path in files[:30]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue
        if package_or_bundle is None:
            package_match = re.search(r"\b(?:package|applicationId|CFBundleIdentifier)\b[^\w]*(?:=|:)?[^\w]*([A-Za-z0-9_.-]+)", text)
            if package_match:
                package_or_bundle = package_match.group(1)
        for url_match in re.findall(r"https?://[A-Za-z0-9._:-]+", text):
            backend_hosts.add(urlparse(url_match).hostname or url_match)
        if "NSAppTransportSecurity" in text or "networkSecurityConfig" in text:
            transport_notes.append(f"Observed transport-related configuration text in {relative_path(path)}.")
        evidence_entries.append(
            {
                "path": relative_path(path),
                "type": path.suffix.lower().lstrip(".") or "file",
                "summary": f"Indexed local artifact for mobile review ({len(text[:200].splitlines())} preview lines).",
            }
        )

    return {
        "file_count": len(files),
        "extension_counts": dict(sorted(extension_counts.items())),
        "backend_hosts": sorted(host for host in backend_hosts if host),
        "package_or_bundle": package_or_bundle,
        "transport_notes": sorted(set(transport_notes)),
        "evidence_entries": evidence_entries[:20],
    }


def run_mobile_review(target_path: str, rules_path: str | None = None) -> dict[str, Any]:
    target = resolve_artifact_target_path(target_path)
    update_state_summary(current_target=relative_path(target))
    state, session = start_session(
        "mobile-review",
        "mobile-app-analyzer",
        {"target_path": relative_path(target), "rules_path": rules_path},
    )
    metadata = infer_mobile_metadata(target)
    yara_result = run_yara_scan(str(target), rules_path=rules_path)
    append_event(state, session["session_id"], "yara-scan", yara_result)

    finding_candidates = []
    if metadata["backend_hosts"]:
        finding_candidates.append(
            {
                "title": "Mobile artifacts include backend host references",
                "severity_candidate": "info",
                "confidence": "medium",
                "rationale": "Observed backend-like host strings in supplied local artifacts.",
                "evidence": metadata["backend_hosts"],
                "analyst_note": "Configuration clues are useful triage data, not proof of exposure by themselves.",
                "safe_follow_up": "Validate whether the referenced hosts are expected for the assessed build.",
            }
        )
    if yara_result.get("match_count", 0) > 0:
        finding_candidates.append(
            {
                "title": "YARA rules matched mobile control clues",
                "severity_candidate": "info",
                "confidence": "medium",
                "rationale": "Observed rule matches against local files using the bundled read-only ruleset.",
                "evidence": yara_result.get("matches", []),
                "analyst_note": "YARA output is supporting evidence only and should be corroborated with file review.",
                "safe_follow_up": "Open the matched files and confirm whether the strings reflect real app behavior.",
            }
        )

    result = {
        "agent": "mobile-app-analyzer",
        "target_path": relative_path(target),
        "app_profile": {
            "platform": "android" if any(ext in metadata["extension_counts"] for ext in [".xml", ".smali", ".dex"]) else "unknown",
            "package_or_bundle": metadata["package_or_bundle"],
            "version": None,
            "permissions": [],
            "backend_hosts": metadata["backend_hosts"],
            "transport_notes": metadata["transport_notes"],
            "artifact_inventory": metadata["extension_counts"],
        },
        "evidence_entries": metadata["evidence_entries"],
        "finding_candidates": finding_candidates,
        "yara_scan": yara_result,
        "limitations": [
            "File heuristics are preview-based and may miss binary-only metadata.",
            "YARA matches remain supporting clues rather than standalone proof.",
            "No runtime hooking, bypass, or exploit workflow is included.",
        ],
    }
    finish_session(state, session["session_id"], result)
    return result


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "finding"


def render_finding_markdown(
    *,
    title: str,
    host: str,
    endpoint: str,
    method: str,
    auth_context: str,
    classification: str,
    artifacts: list[str],
    observations: list[str],
    limitations: list[str],
    remediation_notes: list[str],
) -> str:
    request_ids: list[str] = []
    for artifact_path in artifacts:
        artifact = load_json_artifact(artifact_path)
        request_id = artifact.get("request_id")
        if isinstance(request_id, str) and request_id:
            request_ids.append(request_id)

    reproduction = [
        "Validate the request or artifact path against the current scope and workflow constraints.",
        "Store evidence under evidence/raw or evidence/normalized before writing the finding.",
        "Re-run the same read-only workflow and confirm the observed result matches the cited artifacts.",
    ]
    impact = observations[0] if observations else "Evidence recorded for operator review."
    observed_differences = "; ".join(observations) if observations else "None recorded."
    remediation = remediation_notes[0] if remediation_notes else "Review whether the observed behavior aligns with the intended deployment policy."

    return "\n".join(
        [
            f"# {title}",
            "",
            "## Scope",
            "",
            f"* Host: {host}",
            f"* Endpoint: {endpoint}",
            f"* Method: {method.upper()}",
            f"* Auth context: {auth_context}",
            "",
            "## Classification",
            "",
            f"* {classification}",
            "",
            "## Preconditions",
            "",
            "* Explicit authorization exists for the assessed environment.",
            "",
            "## Evidence",
            "",
            f"* Request IDs: {', '.join(request_ids) if request_ids else 'None recorded'}",
            f"* Artifacts: {', '.join(artifacts)}",
            f"* Observed differences: {observed_differences}",
            "",
            "## Reproduction",
            "",
            f"1. {reproduction[0]}",
            f"2. {reproduction[1]}",
            f"3. {reproduction[2]}",
            "",
            "## Impact",
            "",
            f"* {impact}",
            "",
            "## Limitations",
            "",
            *[f"* {item}" for item in limitations],
            "",
            "## Remediation",
            "",
            f"* {remediation}",
            "",
        ]
    )


def run_write_finding(
    *,
    title: str,
    host: str,
    endpoint: str,
    method: str,
    auth_context: str,
    classification: str,
    artifacts: list[str],
    observations: list[str],
    limitations: list[str],
    remediation_notes: list[str],
    relative_output_path: str | None = None,
) -> dict[str, Any]:
    if not artifacts:
        raise ValueError("At least one evidence artifact is required before writing a finding.")
    for artifact_path in artifacts:
        resolve_evidence_artifact_path(artifact_path)

    state, session = start_session(
        "write-finding",
        "evidence-writer",
        {
            "title": title,
            "host": host,
            "endpoint": endpoint,
            "method": method,
            "auth_context": auth_context,
            "classification": classification,
            "artifacts": artifacts,
        },
    )

    markdown = render_finding_markdown(
        title=title,
        host=host,
        endpoint=endpoint,
        method=method,
        auth_context=auth_context,
        classification=classification,
        artifacts=artifacts,
        observations=observations,
        limitations=limitations,
        remediation_notes=remediation_notes,
    )
    target = relative_output_path or f"findings/{slugify(title)}.md"
    write_result = write_artifact(target, markdown, "text")
    append_event(state, session["session_id"], "artifact-write", write_result)

    result = {
        "agent": "evidence-writer",
        "template_path": relative_path(FINDING_TEMPLATE),
        "finding_path": target,
        "classification": classification,
        "evidence": artifacts,
        "reproduction_summary": [
            "Validate scope and workflow eligibility before every observation.",
            "Capture and store evidence before drafting findings.",
            "Re-run the same read-only workflow to confirm the cited behavior.",
        ],
        "limitations": limitations,
        "artifact_writer": write_result,
    }
    update_state_summary(findings=[target])
    finish_session(state, session["session_id"], result)
    return result


def summarize_analysis(goal: str, workflow: str | None, executed: bool, needs_clarification: bool) -> str:
    if needs_clarification:
        return "More input is required before Black-Spyder can continue safely."
    if not executed:
        return f"Black-Spyder selected the '{workflow or 'unknown'}' workflow but did not execute it yet."
    return f"Black-Spyder executed the '{workflow or 'unknown'}' workflow for the requested goal."


def build_analysis_envelope(
    *,
    analysis_mode: str,
    goal: str,
    route: dict[str, Any] | None,
    executed: bool,
    result: dict[str, Any] | None,
    next_action: dict[str, Any] | None,
    needs_clarification: bool = False,
    clarification_question: str | None = None,
    suggested_input: dict[str, str] | None = None,
    extraction: dict[str, str] | None = None,
) -> dict[str, Any]:
    workflow = route["workflow"] if route is not None else None
    envelope: dict[str, Any] = {
        "status": "needs_clarification" if needs_clarification else ("completed" if executed else "planned"),
        "analysis_mode": analysis_mode,
        "goal": goal,
        "workflow": workflow,
        "executed": executed,
        "summary": summarize_analysis(goal, workflow, executed, needs_clarification),
        "route": route,
        "result": result,
        "next_action": next_action,
        "recommended_surface": "/converse" if analysis_mode == "conversation" else "/analyze",
    }
    if needs_clarification:
        envelope["needs_clarification"] = True
    if clarification_question is not None:
        envelope["clarification_question"] = clarification_question
    if suggested_input is not None:
        envelope["suggested_input"] = suggested_input
    if extraction is not None:
        envelope["conversation_extraction"] = extraction
    return envelope


def run_autonomous_analysis(
    *,
    goal: str,
    url: str | None = None,
    method: str = "GET",
    artifact_path: str | None = None,
    left_artifact_path: str | None = None,
    right_artifact_path: str | None = None,
    target_path: str | None = None,
    rules_path: str | None = None,
) -> dict[str, Any]:
    route = route_workflow(
        goal=goal,
        url=url,
        method=method,
        artifact_path=artifact_path,
        left_artifact_path=left_artifact_path,
        right_artifact_path=right_artifact_path,
        target_path=target_path,
    )
    workflow = route["workflow"]
    result: dict[str, Any] | None = None

    if workflow == "observe" and url is not None:
        result = run_observe(url=url, method=method, execute=True)
    elif workflow == "recon" and artifact_path is not None:
        result = run_recon(artifact_path=artifact_path)
    elif workflow == "compare-auth" and left_artifact_path is not None and right_artifact_path is not None:
        result = run_compare_auth(left_artifact_path=left_artifact_path, right_artifact_path=right_artifact_path)
    elif workflow == "mobile-review" and target_path is not None:
        result = run_mobile_review(target_path=target_path, rules_path=rules_path)

    return build_analysis_envelope(
        analysis_mode="structured",
        goal=goal,
        route=route,
        executed=result is not None,
        result=result,
        next_action=route["next_action"] if result is None else None,
    )


def extract_url_from_goal(goal: str) -> str | None:
    match = re.search(r"https?://[^\s]+", goal)
    return match.group(0) if match else None


def extract_path_from_goal(goal: str) -> str | None:
    match = re.search(r"(~?/[^\s]+|\./[^\s]+|/[^\s]+)", goal)
    if not match:
        return None
    return expanduser(match.group(0))


def goal_mentions_mobile(goal: str) -> bool:
    lowered = goal.lower()
    keywords = ["apk", "android", "ipa", "app 분석", "앱 분석", "mobile", "ios"]
    return any(keyword in lowered for keyword in keywords)


def run_conversational_analysis(goal: str) -> dict[str, Any]:
    extracted_url = extract_url_from_goal(goal)
    extracted_path = extract_path_from_goal(goal)

    def as_conversation(result: dict[str, Any], extraction: dict[str, str]) -> dict[str, Any]:
        return build_analysis_envelope(
            analysis_mode="conversation",
            goal=goal,
            route=result.get("route"),
            executed=bool(result.get("executed")),
            result=result.get("result"),
            next_action=result.get("next_action"),
            extraction=extraction,
        )

    if goal_mentions_mobile(goal) and extracted_path is None:
        return build_analysis_envelope(
            analysis_mode="conversation",
            goal=goal,
            route=None,
            executed=False,
            result=None,
            next_action=None,
            needs_clarification=True,
            clarification_question="어떤 앱을 분석할까요? APK 파일 경로나 추출된 앱 디렉터리 경로를 알려주세요.",
            suggested_input={"target_path": "~/Downloads/example.apk 또는 추출된 앱 디렉터리 경로"},
        )

    if extracted_path is not None and goal_mentions_mobile(goal):
        candidate = Path(extracted_path).expanduser()
        if not candidate.exists():
            return build_analysis_envelope(
                analysis_mode="conversation",
                goal=goal,
                route=None,
                executed=False,
                result=None,
                next_action=None,
                needs_clarification=True,
                clarification_question="분석할 APK나 추출된 앱 경로를 찾지 못했습니다. 실제 존재하는 경로를 알려주세요.",
                suggested_input={"target_path": extracted_path},
            )
        try:
            resolved_target = str(resolve_artifact_target_path(str(candidate)))
        except (ValueError, FileNotFoundError):
            return build_analysis_envelope(
                analysis_mode="conversation",
                goal=goal,
                route=None,
                executed=False,
                result=None,
                next_action=None,
                needs_clarification=True,
                clarification_question="APK 분석은 현재 artifacts/ 아래의 로컬 파일 또는 추출 디렉터리를 기준으로 진행합니다. 분석할 앱 경로를 artifacts/ 아래로 준비해 알려주세요.",
                suggested_input={"target_path": str(candidate)},
            )
        return as_conversation(
            run_autonomous_analysis(goal=goal, target_path=resolved_target),
            {"target_path": resolved_target},
        )

    if extracted_url is not None:
        return as_conversation(
            run_autonomous_analysis(goal=goal, url=extracted_url),
            {"url": extracted_url},
        )

    return build_analysis_envelope(
        analysis_mode="conversation",
        goal=goal,
        route=None,
        executed=False,
        result=None,
        next_action=None,
        needs_clarification=True,
        clarification_question="분석할 대상이 필요합니다. URL이나 로컬 파일/디렉터리 경로를 알려주세요.",
        suggested_input={"url": "https://example.com", "target_path": "~/Downloads/example.apk"},
    )


def next_step() -> dict[str, Any]:
    state = load_runtime_state_snapshot()
    last_session_id = state.get("last_session_id")
    if not last_session_id:
        return {
            "phase": "plan",
            "next_action": {
                "tool": "route",
                "reason": "No prior agent session exists yet.",
                "input": {"goal": "Start with an authorized target or stored artifact."},
            },
        }

    for session in reversed(cast(list[dict[str, Any]], state["sessions"])):
        if session["session_id"] != last_session_id:
            continue
        workflow = session["workflow"]
        result = session.get("result") or {}
        next_action = result.get("next_action")
        if next_action:
            return {
                "session_id": session["session_id"],
                "workflow": workflow,
                "status": session["status"],
                "next_action": next_action,
            }
        if workflow == "observe":
            return {
                "session_id": session["session_id"],
                "workflow": workflow,
                "status": session["status"],
                "next_action": {
                    "tool": "recon",
                    "reason": "A safe observation completed, so the next step is structured review of the normalized artifact.",
                    "input": {"artifact_path": (result.get("artifacts") or [None])[-1]},
                },
            }
        return {
            "session_id": session["session_id"],
            "workflow": workflow,
            "status": session["status"],
            "next_action": {
                "tool": "route",
                "reason": "The last workflow completed without an explicit follow-up.",
                "input": {"goal": "Choose the next evidence-based step."},
            },
        }

    return {
        "phase": "plan",
        "next_action": {
            "tool": "route",
            "reason": "No matching runtime session was found in state.",
            "input": {"goal": "Start a new workflow."},
        },
    }
