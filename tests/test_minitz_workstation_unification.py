from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_workstation_cli_is_minitz_native_and_cannot_stop_or_kill_host_resources():
    cli = text('ops/workstation/minitz-workstation')
    lib = text('ops/workstation/minitz-lib.sh')
    combined = cli + '\n' + lib
    assert 'Usage: minitz-workstation' in cli
    assert '/usr/local/bin/biella' not in combined
    assert 'biella_' not in combined
    for forbidden in ('systemctl stop', 'systemctl start', 'systemctl restart', 'kill ', 'pkill', 'tmux kill', 'cleanup)', 'down)'):
        assert forbidden not in combined
    assert 'qwen3-coder-next:minitz' in combined
    assert '/root/attached-storage/minitz-os-sandbox/state/workstation' in combined


def test_workstation_installer_does_not_manage_host_services():
    installer = text('ops/workstation/install-minitz-workstation.sh')
    assert '/usr/local/lib/minitz-workstation' in installer
    assert '/usr/local/bin/minitz-workstation' in installer
    for forbidden in ('systemctl ', '/etc/systemd/system', '/usr/local/bin/biella', '/mnt/biella-extra', '/root/biella'):
        assert forbidden not in installer


def test_ai_installer_contains_only_current_minitz_runtime_files():
    installer = text('ops/local-ai/install-minitz-ai.sh')
    for forbidden in ('biella_customer_handoff', 'biella_drive_package', 'biella-project-cell', 'biella-ai', '/usr/local/bin/biella'):
        assert forbidden not in installer
    assert 'minitz_production_runner.py' in installer
    assert 'minitz-production.service' in installer


def test_control_installer_uses_only_minitz_control_names_and_state():
    installer = text('ops/control_gateway/install-minitz-control-gateway.sh')
    service = text('ops/control_gateway/minitz-control-gateway.service')
    combined = installer + '\n' + service
    assert 'minitz_base_projection.py' in installer
    assert 'biella_live_projection.py' not in combined
    assert '/usr/local/lib/biella-control' not in combined
    assert '/var/lib/biella-control' not in combined
    assert '/root/.config/biella-control' not in combined
    assert '/root/attached-storage/minitz-os-sandbox/state/control' in combined
