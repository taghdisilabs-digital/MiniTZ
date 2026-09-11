from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import minitz_task_program as minitz

ANCHOR_TASK_ID = "RUNTIME-AI-01"
_OWNER_EVIDENCE = (
    "Owner approved five-Boost execution, Linux-only HAL, Founder Mode, trust anchors, "
    "two-slot GPU residency, and qualified browser swarm on 2026-09-11.",
)


def _dep(kind: str, task_ref: str, reason: str) -> dict[str, str]:
    return {"dependency_type": kind, "task_ref": task_ref, "reason": reason}


def _refs(*paths: str) -> list[dict[str, str]]:
    return [{"kind": "CURRENT_SOURCE", "path": path} for path in paths]


def _task(
    task_id: str, title: str, *, dependencies: Sequence[dict[str, str]],
    paths: Sequence[str], objective: str, deliverables: Sequence[str],
    acceptance: Sequence[str], negative_controls: Sequence[str],
    capabilities: Sequence[str], source_refs: Sequence[dict[str, str]],
    validation: Sequence[str], scope: str = "MINITZ DEEP ENGINEERING",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "revision": 1,
        "status": "PENDING",
        "active_task_survival": True,
        "review_state": "VALUE_GATE_PASSED",
        "title": title,
        "scope": scope,
        "dependencies": list(dependencies),
        "write_scope": {
            "authority": "TASK_OWNED_ONLY",
            "execution_root": "/root/biella/repos/biella-engine",
            "allowed_paths": list(paths),
        },
        "objective": {"desired_state": objective},
        "deliverables": list(deliverables),
        "acceptance": list(acceptance),
        "negative_controls": list(negative_controls),
        "required_capabilities": list(capabilities),
        "source_refs": list(source_refs),
        "required_evidence": list(validation),
        "validation": list(validation),
    }


def extension_tasks() -> list[dict[str, Any]]:
    return [
        _task(
            "HAL-LINUX-01", "Establish Linux-native MiniTZ hardware and driver capability binding",
            dependencies=[_dep("HARD", "RUNTIME-AI-01", "Attach HAL work after persistent runtime intelligence is live-proven.")],
            paths=["src/biella/hal.py", "src/biella/resource.py", "ops/workstation/minitz-hal-probe.py", "tests/test_minitz_hal.py"],
            objective="Discover CPU, GPU, IOMMU and I/O topology, bind Linux-native driver domains, and publish hardware capabilities without creating a second resource authority.",
            deliverables=["HAL resource graph", "driver-domain resolver", "hardware probe and functional readback"],
            acceptance=["Linux-only driver domains resolve from hardware identity to semantic capabilities", "GPU/CPU/I/O readiness requires functional readback", "unsupported hardware remains unavailable instead of guessed ready"],
            negative_controls=["no host-kernel bypass claim while Linux remains the executing substrate", "no vendor-specific hardware becomes architecture authority"],
            capabilities=["resource.route", "system.integration.qualify", "evidence.record"],
            source_refs=_refs("src/biella/resource.py", "src/biella/routing.py", "ops/workstation/provider-registry.json"),
            validation=["driver binding receipt", "GPU functional readback", "IOMMU/I/O topology readback"],
        ),
        _task(
            "HAL-FOUNDER-01", "Implement Founder Mode deterministic CPU GPU and I/O leasing",
            dependencies=[_dep("HARD", "HAL-LINUX-01", "Founder Mode consumes the qualified Linux HAL graph.")],
            paths=["src/biella/hal.py", "src/biella/resource.py", "ops/workstation/minitz-founder-mode.py", "tests/test_minitz_founder_mode.py"],
            objective="Map qualified CPU threads, GPU memory/device leases and I/O groups into fenced MiniTZ Run resources with deterministic ownership and accounting.",
            deliverables=["Founder execution profile", "CPU/GPU/I/O lease model", "lease fencing and recovery evidence"],
            acceptance=["Run resources are topology-aware and explicitly leased", "VRAM isolation claims match actual hardware capability", "lease loss/recovery cannot change Task authority"],
            negative_controls=["no hard real-time claim without measured real-time qualification", "no generic desktop service dependency in Founder execution profile"],
            capabilities=["resource.route", "state.transition.atomic", "recovery.failure.learn"],
            source_refs=_refs("src/biella/resource.py", "src/biella/execution.py", "src/biella/run.py"),
            validation=["lease isolation test", "resource accounting test", "restart recovery test"],
        ),
        _task(
            "TRUST-NODE-01", "Establish MiniTZ node trust anchors and strict execution posture",
            dependencies=[
                _dep("HARD", "SECRET-01", "Trust anchors require the canonical private-state boundary."),
                _dep("HARD", "HAL-LINUX-01", "Node trust records bind to qualified hardware/firmware observations."),
            ],
            paths=["src/biella/node_trust.py", "ops/workstation/minitz-node-trust.py", "tests/test_minitz_node_trust.py"],
            objective="Represent measured boot posture, node/root identity, managed-storage policy and authenticated cloud/root trust anchors without storing raw secrets in task state.",
            deliverables=["node trust model", "strict-mode storage/service policy", "attestation/root-anchor verification receipts"],
            acceptance=["strict mode degrades when required trust anchors are absent", "raw credential values never enter task memory or public projections", "recovery/provisioning remains available when privileged execution is locked"],
            negative_controls=["no network reachability equals trust", "no one opaque trust score replaces inspectable checks"],
            capabilities=["source.secret_safe.inspect", "identity.authority.migrate", "system.integration.qualify"],
            source_refs=_refs("ops/local-ai/minitz_private_secret_verifier.py", "ops/workstation/provider-registry.json"),
            validation=["boot-integrity evidence", "node-identity evidence", "credential-binding evidence", "strict-mode recovery evidence"],
        ),
        _task(
            "GPU-RESIDENCY-01", "Qualify two-slot persistent GPU residency with protected headroom",
            dependencies=[_dep("HARD", "HAL-LINUX-01", "Residency requires qualified GPU/driver capability binding.")],
            paths=["ops/workstation/minitz-gpu-residency.json", "ops/workstation/biella-qwen-residency.sh", "ops/workstation/biella-ollama.service", "tests/test_gpu_residency_policy.py"],
            objective="Keep one logic/code model slot and one visual-generation slot within measured L40S capacity while preserving about 2 GiB VRAM for runtime headroom.",
            deliverables=["two-slot residency policy", "logic-slot Qwen offload profile", "qualification-gated visual slot"],
            acceptance=["combined residency never exceeds 44020 MiB on the observed 46068 MiB L40S", "logic slot supports code comparison calculation and reasoning", "visual slot is not reported ready until real local weights pass functional qualification"],
            negative_controls=["no auto-download on boot", "no visual readiness claim from an empty slot"],
            capabilities=["resource.route", "capability.synthesize", "system.integration.qualify"],
            source_refs=_refs("ops/workstation/biella-qwen-residency.sh", "ops/workstation/biella-ollama.service"),
            validation=["VRAM readback", "logic inference test", "visual model binding test when present"],
        ),
        _task(
            "BOOST-FABRIC-01", "Activate five isolated Boost workers over thirty Commander lanes",
            dependencies=[
                _dep("HARD", "UNIFY-04", "Boost workers require exact checkpoint/session continuity."),
                _dep("HARD", "UNIFY-06", "Boost results require unified event/evidence identities."),
            ],
            paths=["ops/local-ai/minitz_boost_fabric.py", "ops/local-ai/biella_production_runner.py", "ops/control_gateway/biella_control_state.py", "ops/control_gateway/biella_live_projection.py", "ops/control_gateway/minitz_live_projection.py", "website/src/control", "website/src/live", "tests/test_boost_fabric.py"],
            objective="Run five isolated ChatGPT Boost workers, each bound to six unique Commander lanes and one derived section of the current canonical task, with one shared non-authoritative progress projection.",
            deliverables=["five-worker assignment fabric", "worker report contract", "private/public Boost status projection"],
            acceptance=["CMD-01 through CMD-30 are assigned exactly once", "Boost workers cannot mutate Task Program progression", "worker reports are task-digest and program-digest bound", "website exposes current Boost/task/Commander state"],
            negative_controls=["no second scheduler or task queue", "no concurrent write-scope overlap", "no worker starts before owner resume"],
            capabilities=["task.continue", "task.progress", "memory.manage", "evidence.record"],
            source_refs=_refs("ops/local-ai/minitz_commander_fabric.py", "ops/local-ai/biella_production_runner.py"),
            validation=["five-by-six partition test", "stale worker report rejection", "website projection contract"],
        ),
        _task(
            "BROWSER-SWARM-01", "Qualify thirty browser automation slots behind the MiniTZ control plane",
            dependencies=[
                _dep("HARD", "BOOST-FABRIC-01", "Browser automation slots are assigned through the Boost/Commander fabric."),
                _dep("HARD", "TRUST-NODE-01", "Authenticated browser/cloud connectors require qualified node trust."),
            ],
            paths=["src/biella/browser_adapter.py", "ops/workstation/minitz-browser-cloud.py", "ops/workstation/minitz-browser-swarm.py", "ops/workstation/provider-registry.json", "tests/test_minitz_browser_swarm.py"],
            objective="Represent up to thirty isolated browser automation slots as capability Resources with bounded handshakes, task-scoped leases and no progression authority.",
            deliverables=["browser swarm registry", "slot lease/heartbeat protocol", "timeout and recovery evidence"],
            acceptance=["thirty logical slots can be represented without claiming thirty live instances", "slot health is proven by bounded handshake evidence", "browser failures do not mutate canonical task status"],
            negative_controls=["no credential values in browser task packets", "no slot count inferred from Commander count alone"],
            capabilities=["resource.route", "workspace.isolate", "evidence.record"],
            source_refs=_refs("src/biella/browser_adapter.py", "ops/workstation/minitz-browser-cloud.py"),
            validation=["thirty-slot registry test", "handshake timeout test", "credential-isolation test"],
        ),
        _task(
            "SYSTEM-QUALIFY-01", "Qualify integrated HAL trust GPU Boost browser and cache behavior",
            dependencies=[
                _dep("HARD", "HAL-FOUNDER-01", "Integrated qualification requires Founder HAL."),
                _dep("HARD", "TRUST-NODE-01", "Integrated qualification requires node trust."),
                _dep("HARD", "GPU-RESIDENCY-01", "Integrated qualification requires GPU residency."),
                _dep("HARD", "BROWSER-SWARM-01", "Integrated qualification requires browser swarm semantics."),
            ],
            paths=["ops/local-ai/minitz_staged_audit.py", "tests/test_minitz_system_qualification.py"],
            objective="Functionally qualify the combined MiniTZ hardware, trust, local runtime, five-Boost, browser-resource and evidence/cache graph without promoting target metrics as observed facts.",
            deliverables=["integrated qualification matrix", "SHA-256 evidence-chain receipt", "recovery/failure matrix"],
            acceptance=["all Ready claims have functional evidence", "SHA-256 evidence links exact source/runtime identities", "cache efficiency is measured rather than assumed", "dynamic failures preserve root-cause evidence and bounded recovery"],
            negative_controls=["no 98-percent cache claim without measurement", "no bug-free claim from dependency presence alone", "no helper becomes acceptance authority"],
            capabilities=["system.integration.qualify", "change.cutover.qualify", "evidence.record"],
            source_refs=_refs("ops/local-ai/minitz_staged_audit.py", "ops/local-ai/minitz_boost_fabric.py", "ops/workstation/minitz-gpu-residency.json"),
            validation=["full integration test", "restart/recovery test", "evidence-chain readback", "measured cache report"],
        ),
    ]


def apply_extension(*, path: Path | None = None) -> dict[str, Any]:
    return minitz.insert_tasks_after(
        ANCHOR_TASK_ID,
        extension_tasks(),
        evidence=_OWNER_EVIDENCE,
        path=path,
    )
