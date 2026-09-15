from pathlib import Path

from minitz_os.source import source_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_connectors_are_owned_by_canonical_minitz_source():
    manifest = source_manifest(ROOT)
    files = set(manifest["files"])
    assert "ops/connectors/reconcile.py" in files
    assert "ops/connectors/minitz-connectors.py" in files
    assert "ops/connectors/minitz-private-secret-verifier.py" in files
    assert "ops/connectors/install-minitz-connectors.sh" in files


def test_connector_reconcile_uses_only_minitz_runtime_paths_and_env():
    text = (ROOT / "ops/connectors/reconcile.py").read_text(encoding="utf-8")
    assert "MINITZ_AI_RUNTIME_ENV" in text
    assert "/usr/local/lib/minitz-workstation/minitz-provider-check.sh" in text
    for retired in ("BIELLA_AI_RUNTIME_ENV", "/usr/local/lib/biella-workstation", "/root/biella", "/mnt/biella"):
        assert retired not in text


def test_connector_installer_links_command_to_canonical_source():
    text = (ROOT / "ops/connectors/install-minitz-connectors.sh").read_text(encoding="utf-8")
    assert 'SOURCE_ROOT="${MINITZ_SOURCE_ROOT:-' in text
    assert 'readonly ENTRY="$SOURCE_ROOT/ops/connectors/reconcile.py"' in text
    assert 'ln -s "$ENTRY" "$CLI_LINK"' in text
    assert "/usr/lib/minitz/connectors" not in text
