"""MiniTZ's single normal-user surface and read-only doctor diagnostics.

This module is deliberately an observation boundary.  It exposes one
discoverable surface over the existing capability contracts and reports
problems with a bounded reason and recovery action.  It does not start,
stop, repair, update, or advance any MiniTZ state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .capabilities import Availability, CapabilitySurface
from .source import source_manifest


SOURCE_IDENTITY = "source-library://minitz/main"
SURFACE_REF = "surface://minitz/operator/v1"
SURFACE_SCOPE_REF = "scope://minitz/operator/v1"
DOCTOR_REF = "diagnostic://minitz/doctor/v1"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _error_kind(error: BaseException) -> str:
    """Return only a stable error class; never expose an error payload."""
    return type(error).__name__


@dataclass(frozen=True)
class SurfaceSection:
    key: str
    title: str
    description: str
    command: str
    capability_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "command": self.command,
            "capability_refs": list(self.capability_refs),
        }


@dataclass(frozen=True)
class Diagnostic:
    check_ref: str
    title: str
    availability: Availability
    reason_code: str
    problem: str
    action: str
    dependency_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "check_ref": self.check_ref,
            "title": self.title,
            "availability": self.availability.value,
            "reason_code": self.reason_code,
            "problem": self.problem,
            "action": self.action,
            "dependency_refs": list(self.dependency_refs),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[Diagnostic, ...]
    source_identity: str = SOURCE_IDENTITY

    def as_dict(self) -> dict[str, object]:
        checks = [item.as_dict() for item in self.checks]
        counts = {
            state.value: sum(item.availability is state for item in self.checks)
            for state in Availability
        }
        payload: dict[str, object] = {
            "schema": "minitz.doctor/v1",
            "doctor_ref": DOCTOR_REF,
            "source_identity": self.source_identity,
            "check_count": len(checks),
            "checks": checks,
            "availability_counts": counts,
            "overall_availability": _worst(self.checks).value,
        }
        payload["doctor_sha256"] = _digest(payload)
        return payload


def _worst(checks: Sequence[Diagnostic]) -> Availability:
    if not checks:
        return Availability.NEEDS_ATTENTION
    priority = {
        Availability.NEEDS_ATTENTION: 90,
        Availability.UNAVAILABLE: 80,
        Availability.DISABLED: 70,
        Availability.RECOVERING: 60,
        Availability.UPDATING: 50,
        Availability.DEGRADED: 40,
        Availability.NEEDS_SETUP: 30,
        Availability.NOT_PRESENT: 20,
        Availability.READY: 0,
    }
    return max(checks, key=lambda item: priority[item.availability]).availability


def _capability_refs(surface: CapabilitySurface, namespaces: set[str]) -> tuple[str, ...]:
    return tuple(
        item.capability_ref.value
        for item in surface.descriptors()
        if item.capability.namespace in namespaces
    )


class Doctor:
    """Read-only diagnostics for the source, task authority, and runtime truth."""

    def __init__(
        self,
        repo_root: Path,
        state_root: Path,
        task_program_path: Path | None = None,
        capabilities: CapabilitySurface | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.state_root = Path(state_root).resolve()
        self.task_program_path = (
            Path(task_program_path).resolve()
            if task_program_path is not None
            else Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json")).resolve()
        )
        self.capabilities = capabilities or CapabilitySurface()

    def _source_check(self) -> Diagnostic:
        try:
            manifest = source_manifest(self.repo_root)
            source_sha256 = str(manifest["source_sha256"])
            return Diagnostic(
                "diagnostic://minitz/doctor/source-identity/v1",
                "Canonical source",
                Availability.READY,
                "SOURCE_IDENTITY_READY",
                "The canonical MiniTZ source identity is readable and credential-safe.",
                "No action required.",
                evidence_refs=(f"evidence://minitz/source/{source_sha256}",),
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            return Diagnostic(
                "diagnostic://minitz/doctor/source-identity/v1",
                "Canonical source",
                Availability.NEEDS_ATTENTION,
                "SOURCE_IDENTITY_UNAVAILABLE",
                f"The canonical source identity could not be read ({_error_kind(error)}).",
                "Run the managed MiniTZ source verification and review its bounded result.",
            )

    def _task_check(self) -> Diagnostic:
        try:
            import minitz_task_program as tasks  # type: ignore[import-untyped]

            program = tasks.load(self.task_program_path)
            current = program.get("current_execution")
            task_id = current.get("task_id") if isinstance(current, Mapping) else None
            if not isinstance(task_id, str) or not task_id:
                raise ValueError("current task is absent")
            return Diagnostic(
                "diagnostic://minitz/doctor/task-authority/v1",
                "Task authority",
                Availability.READY,
                "TASK_AUTHORITY_READY",
                f"The canonical Task Program exposes current task {task_id}.",
                "No action required.",
                evidence_refs=(f"evidence://minitz/task-program/{program['_observed_sha256']}",),
            )
        except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
            return Diagnostic(
                "diagnostic://minitz/doctor/task-authority/v1",
                "Task authority",
                Availability.NEEDS_ATTENTION,
                "TASK_AUTHORITY_UNAVAILABLE",
                f"The canonical Task Program could not be read ({_error_kind(error)}).",
                "Restore the configured canonical Task Program path, then rerun MiniTZ doctor.",
            )

    def _qualification_check(self) -> Diagnostic:
        path = self.state_root / "qualification" / "sandbox-foundation.json"
        if not path.is_file():
            return Diagnostic(
                "diagnostic://minitz/doctor/qualification/v1",
                "Runtime qualification",
                Availability.NEEDS_SETUP,
                "QUALIFICATION_MISSING",
                "No current MiniTZ sandbox qualification observation is present.",
                "Run the managed MiniTZ qualification route, then rerun MiniTZ doctor.",
            )
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            state = value.get("state") if isinstance(value, Mapping) else None
            if state in {"READY", "LOCAL_CAPABILITY_QUALIFIED", "QUALIFIED"}:
                availability = Availability.READY
                reason = "QUALIFICATION_READY"
                problem = "The latest MiniTZ sandbox qualification observation is Ready."
                action = "No action required."
            elif state == "RECOVERING":
                availability = Availability.RECOVERING
                reason = "QUALIFICATION_RECOVERING"
                problem = "The latest MiniTZ sandbox qualification observation is recovering."
                action = "Review the managed recovery evidence and rerun MiniTZ doctor when it settles."
            elif state == "UPDATING":
                availability = Availability.UPDATING
                reason = "QUALIFICATION_UPDATING"
                problem = "The latest MiniTZ sandbox qualification observation is updating."
                action = "Review the managed update evidence and rerun MiniTZ doctor when it settles."
            else:
                availability = Availability.NEEDS_ATTENTION
                reason = "QUALIFICATION_STATE_UNKNOWN"
                problem = "The latest qualification observation is not a recognized Ready state."
                action = "Open the managed qualification evidence and repair the reported dependency."
            return Diagnostic(
                "diagnostic://minitz/doctor/qualification/v1",
                "Runtime qualification",
                availability,
                reason,
                problem,
                action,
                dependency_refs=("dependency://minitz/sandbox-qualification/v1",),
                evidence_refs=(f"evidence://minitz/qualification/{hashlib.sha256(path.read_bytes()).hexdigest()}",),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            return Diagnostic(
                "diagnostic://minitz/doctor/qualification/v1",
                "Runtime qualification",
                Availability.NEEDS_ATTENTION,
                "QUALIFICATION_UNREADABLE",
                f"The current qualification observation is unreadable ({_error_kind(error)}).",
                "Repair or regenerate the managed qualification observation, then rerun MiniTZ doctor.",
            )

    def _capability_check(self) -> Diagnostic:
        statuses = self.capabilities.statuses()
        availability = _worst(
            tuple(
                Diagnostic(
                    "diagnostic://minitz/doctor/capabilities/v1",
                    "Capability resources",
                    item.availability,
                    "CAPABILITY_RESOURCES_OBSERVED" if item.availability is Availability.READY else "CAPABILITY_RESOURCES_UNOBSERVED",
                    item.reason,
                    "Register a current Resource observation through the managed Resource route.",
                    evidence_refs=item.evidence_refs,
                )
                for item in statuses
            )
        )
        if availability is Availability.READY:
            reason = "CAPABILITY_RESOURCES_READY"
            problem = "All declared capability resources and executors are currently Ready."
            action = "No action required."
        else:
            reason = "CAPABILITY_RESOURCES_UNOBSERVED"
            problem = "One or more declared capabilities lack a current Ready Resource observation."
            action = "Register a current Resource observation through the managed Resource route."
        return Diagnostic(
            "diagnostic://minitz/doctor/capabilities/v1",
            "Capability resources",
            availability,
            reason,
            problem,
            action,
            dependency_refs=("dependency://minitz/resource-observation/v1",),
            evidence_refs=tuple(sorted({ref for item in statuses for ref in item.evidence_refs})),
        )

    def report(self) -> DoctorReport:
        return DoctorReport((self._source_check(), self._task_check(), self._qualification_check(), self._capability_check()))


class OperatorSurface:
    """The one normal-user MiniTZ surface, with all routes visible together."""

    def __init__(
        self,
        repo_root: Path,
        state_root: Path,
        task_program_path: Path | None = None,
        capabilities: CapabilitySurface | None = None,
    ) -> None:
        self.capabilities = capabilities or CapabilitySurface()
        self.doctor = Doctor(repo_root, state_root, task_program_path, self.capabilities)
        self.sections = (
            SurfaceSection("tasks", "Tasks", "See the current task and its validated next action.", "minitz status", _capability_refs(self.capabilities, {"system"})),
            SurfaceSection("resources", "Resources", "See which managed resources are available and why.", "minitz capabilities", _capability_refs(self.capabilities, {"system", "storage", "model", "network"})),
            SurfaceSection("files", "Files", "Read and manage MiniTZ files through the filesystem capability.", "minitz capabilities", _capability_refs(self.capabilities, {"filesystem", "storage"})),
            SurfaceSection("apps", "Apps", "Run managed applications through declared process capabilities.", "minitz capabilities", _capability_refs(self.capabilities, {"process", "software"})),
            SurfaceSection("browser/computer", "Browser and computer", "Use browser and computer routes with their human-action boundaries visible.", "minitz capabilities", _capability_refs(self.capabilities, {"browser", "system"})),
            SurfaceSection("memory", "Memory", "Review bounded MiniTZ memory and task-session evidence routes.", "minitz status", _capability_refs(self.capabilities, {"storage", "system"})),
            SurfaceSection("health", "Health", "Run one doctor view with reason codes and recovery actions.", "minitz doctor", _capability_refs(self.capabilities, {"system", "evidence"})),
            SurfaceSection("updates", "Updates", "Review managed update state before any owner-authorized transition.", "minitz doctor", _capability_refs(self.capabilities, {"system", "storage"})),
            SurfaceSection("recovery", "Recovery", "Find the bounded recovery action for an observed problem.", "minitz doctor", _capability_refs(self.capabilities, {"system", "evidence"})),
            SurfaceSection("evidence", "Evidence", "Read source, resource, action, and diagnostic evidence references.", "minitz doctor", _capability_refs(self.capabilities, {"evidence", "system"})),
        )

    def snapshot(self) -> dict[str, object]:
        doctor = self.doctor.report().as_dict()
        capabilities = self.capabilities.snapshot()
        payload: dict[str, object] = {
            "schema": "minitz.operator-surface/v1",
            "product": "MiniTZ OS",
            "source_identity": SOURCE_IDENTITY,
            "surface_ref": SURFACE_REF,
            "scope_ref": SURFACE_SCOPE_REF,
            "discoverable_command": "minitz dashboard",
            "sections": [item.as_dict() for item in self.sections],
            "capabilities": capabilities,
            "doctor": doctor,
        }
        evidence_payload = {
            "schema": "minitz.operator-evidence/v1",
            "evidence_ref": "evidence://minitz/operator-surface/v1",
            "source_identity": SOURCE_IDENTITY,
            "scope_ref": SURFACE_SCOPE_REF,
            "surface_sha256": _digest(payload),
            "doctor_sha256": doctor["doctor_sha256"],
        }
        evidence_payload["evidence_sha256"] = _digest(evidence_payload)
        payload["evidence"] = evidence_payload
        payload["surface_sha256"] = _digest(payload)
        return payload


def render_dashboard(snapshot: Mapping[str, object]) -> str:
    lines = ["MiniTZ OS", "", "What do you want to do?"]
    sections = snapshot.get("sections", [])
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, Mapping):
                lines.append(f"  {section.get('title')}: {section.get('description')} [{section.get('command')}]")
    doctor = snapshot.get("doctor")
    if isinstance(doctor, Mapping):
        lines.extend(["", f"Health: {doctor.get('overall_availability')}"])
        checks = doctor.get("checks", [])
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, Mapping) and check.get("availability") != Availability.READY.value:
                    lines.append(f"  {check.get('reason_code')}: {check.get('problem')} Action: {check.get('action')}")
    return "\n".join(lines)


def render_doctor(report: Mapping[str, object]) -> str:
    lines = [f"MiniTZ doctor: {report.get('overall_availability')}"]
    checks = report.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, Mapping):
                lines.append(f"{check.get('availability')}: {check.get('title')} ({check.get('reason_code')})")
                lines.append(f"  Problem: {check.get('problem')}")
                lines.append(f"  Action: {check.get('action')}")
    return "\n".join(lines)


__all__ = ["Doctor", "DoctorReport", "OperatorSurface", "render_dashboard", "render_doctor"]
