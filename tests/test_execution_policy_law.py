from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / "ops/workstation/AGENTS.md"
LEGACY = [
    ROOT / "docs/project-state/00_MINITZ_PROJECT_OPERATING_CONTRACT.md",
    ROOT / "docs/project-state/MINITZ_PROJECT_INSTRUCTIONS.md",
    ROOT / "docs/project-state/MINITZ_DURABLE_SOURCE_AND_SYNC_RULES.md",
    ROOT / "projects/minitz-games/AGENTS.md",
]

def test_current_minitz_os_execution_policy_is_os_only_and_hardened():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "BUILD MINITZ OS ONLY",
        "Runtime lifecycle",
        "Five Boosts / thirty Commanders",
        "BOOST-01", "BOOST-02", "BOOST-03", "BOOST-04", "BOOST-05",
        "CMD-01", "CMD-30",
        "Legacy one/two TaskBooster policy is retired",
        "Raw API keys",
        "Lossless compaction",
    ):
        assert marker.lower() in text.lower(), marker
    assert "game delivery is priority number 1" not in text.lower()
    assert "execution is unrestricted" not in text.lower()

def test_legacy_policy_files_have_no_current_authority():
    text = ACTIVE.read_text(encoding="utf-8")
    assert "provenance only" in text.lower()
    assert "only MiniTZ task/order/status/progression authority" in text


def test_persistent_booster_policy_owns_channels_and_main_coder_only_consumes_handoffs():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "Persistent Booster work queues",
        "BOOST-01 — Contract / Authority",
        "BOOST-02 — Core Engineering",
        "BOOST-03 — Runtime / Integration",
        "BOOST-04 — Qualification",
        "BOOST-05 — Continuity / Delivery",
        "main coder does not launch, schedule, or supervise Commander lanes",
        "shared Booster ledger",
        "idle Booster capacity must not be wasted",
    ):
        assert marker.lower() in text.lower(), marker

def test_google_drive_and_rclone_are_absent_from_active_policy():
    text = ACTIVE.read_text(encoding="utf-8").lower()
    for removed in ("gdrive:", "google drive", "drive worker", "rclone"):
        assert removed not in text


def test_bounded_request_execution_collapses_scope_and_stops_after_artifact():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "Bounded request discipline",
        "ONE COMMAND -> VERIFY ONLY NECESSARY SYNTAX -> RETURN EXECUTABLE ARTIFACT -> STOP",
        "Do not inspect live infrastructure unless the requested artifact materially depends on it",
        "A user correction that narrows scope must collapse execution to that narrower scope immediately",
        "Never place descriptive prose inside an executable code block",
        "Unknown product/version behavior remains UNKNOWN until the smallest necessary verification establishes it",
    ):
        assert marker.lower() in text.lower(), marker


def test_resolved_failure_logs_are_compacted_into_never_rules_before_eviction():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "Failure-log compaction",
        "unique unresolved failure evidence remains durable until root cause is closed",
        "resolved repetitive failures must be reduced to signature, root cause, repair, and regression guard",
        "raw duplicate failure logs are evicted after the durable guard exists",
        "raw logs are not long-term MiniTZ memory",
    ):
        assert marker.lower() in text.lower(), marker


def test_p1_qualification_gates_do_not_replay_predecessor_suites_inside_full_pytest():
    replay_files = (
        ROOT / "tests/test_p1_02_run_memory.py",
        ROOT / "tests/test_p1_03_project_memory.py",
        ROOT / "tests/test_p1_04_engine_knowledge.py",
        ROOT / "tests/test_p1_05_call_ledger.py",
        ROOT / "tests/test_p1_06_checkpoint_resume.py",
    )
    for path in replay_files:
        text = path.read_text(encoding="utf-8")
        assert "predecessor.countTestCases()" in text, path.name
        assert "predecessor.run(result)" not in text, path.name


def test_windows_vps_is_never_a_minitz_worker():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "WINDOWS_VPS_IS_NOT_A_WORKER",
        "Windows VPS must never be scheduled as a MiniTZ worker",
        "owner-explicit auxiliary endpoint only",
        "L40 is the primary compute and execution host",
    ):
        assert marker.lower() in text.lower(), marker


def test_work_mode_startup_runs_canonical_execution_until_owner_explicitly_stops():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "WORK_MODE_STARTUP_ORDER",
        "local LLM and GPU residency",
        "attach memory, cache, and Task Program without advancing tasks",
        "connect and synchronize control/resource portals",
        "bring Codex writer resource online only after those prerequisites are ready",
        "When MiniTZ is ON, canonical task execution proceeds automatically unless the owner explicitly stops or replaces it",
        "OWNER_ONLY_PRODUCTION_STOP",
    ):
        assert marker.lower() in text.lower(), marker


def test_single_minitz_os_final_authority_is_one_private_main_source_and_boot_artifact():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "SINGLE_MINITZ_OS_FINAL_AUTHORITY",
        "one canonical source tree",
        "one private GitHub repository",
        "exactly one active branch: main",
        "no fork, no parallel repository, no split source",
        "Ubuntu 24.04 VPS remains the host OS",
        "Ubuntu 26.04 sandbox is the isolated MiniTZ OS build and qualification environment",
        "the canonical source tree is the source that is installed",
        "one bootable/installable MiniTZ OS artifact",
        "all capabilities, APIs, credential/secret behavior, resource behavior, memory behavior, and task behavior",
    ):
        assert marker.lower() in text.lower(), marker


def test_raw_image_boot_requires_explicit_owner_command():
    text = ACTIVE.read_text(encoding="utf-8")
    for marker in (
        "RAW_IMAGE_BOOT_REQUIRES_EXPLICIT_OWNER_COMMAND",
        "A .raw MiniTZ image must never be booted, emulated, or started",
        "validation, qualification, testing, repair, or status request alone is not boot authorization",
    ):
        assert marker.lower() in text.lower(), marker
