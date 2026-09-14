from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ROOTS = (
    ROOT / "src" / "minitz_os",
    ROOT / "ops" / "local-ai",
    ROOT / "ops" / "workstation" / "minitz-os-sandbox",
    ROOT / "ops" / "control_gateway",
    ROOT / "website" / "src",
)
REMOVED = (
    "PAUSED_FOR_CUSTOMER", "customer-pause", "minitz-off-request", "minitz-off-ack",
    "Antigravity", "ANTIGRAVITY", "Gemini", "gemini", "Google Drive", "gdrive:", "rclone",
)
LEGACY_PATHS = ("/root/biella", "/mnt/biella-extra/biella-runtime")


def active_text():
    for root in ACTIVE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".sh", ".service", ".target", ".json", ".js", ".html", ".md"}:
                yield path, path.read_text(encoding="utf-8", errors="replace")


def test_removed_integrations_are_absent_from_active_minitz():
    failures = []
    for path, text in active_text():
        for marker in REMOVED + LEGACY_PATHS:
            if marker in text:
                failures.append(f"{path.relative_to(ROOT)} contains {marker!r}")
    assert not failures, "\n".join(failures[:80])


def test_legacy_product_package_and_active_names_are_gone():
    assert not (ROOT / "src" / "biella").exists()
    bad = []
    for root in (ROOT / "ops" / "local-ai", ROOT / "ops" / "control_gateway", ROOT / "ops" / "workstation"):
        for path in root.iterdir() if root.exists() else ():
            if path.name.startswith(("biella_", "biella-")):
                bad.append(str(path.relative_to(ROOT)))
    assert not bad, "legacy active MiniTZ names remain:\n" + "\n".join(bad[:80])


def test_active_runtime_source_has_no_predecessor_product_identity():
    failures=[]
    for path,text in active_text():
        if 'biella' in text.lower():
            failures.append(str(path.relative_to(ROOT)))
    assert not failures, 'predecessor identity remains in active MiniTZ source:\n'+'\n'.join(failures[:100])


def test_host_resource_code_has_no_stop_or_kill_controls():
    roots=(ROOT/'ops'/'local-ai', ROOT/'ops'/'workstation')
    failures=[]
    for root in roots:
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix not in {'.sh','.py','.service','.target'}:
                continue
            if 'minitz-os-sandbox/runtime.sh' in path.as_posix():
                continue
            text=path.read_text(encoding='utf-8',errors='replace')
            for marker in ('systemctl stop',' kill ','pkill','kill-session','docker stop'):
                if marker in text:
                    failures.append(f'{path.relative_to(ROOT)} contains {marker!r}')
    assert not failures, '\n'.join(failures[:100])
