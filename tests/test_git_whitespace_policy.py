from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RAW_RELATIVE = (
    Path("projects/biella-games/Build/Presentation/sample/runtime.engine.log"),
    Path("projects/biella-games/Build/Presentation/sample/native-views.csv"),
    Path("projects/biella-games/Build/Presentation/sample/readback.txt"),
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_raw_unreal_evidence_is_exempt_but_authored_source_stays_strict(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0

    attributes = ROOT / ".gitattributes"
    if attributes.exists():
        shutil.copy2(attributes, repo / ".gitattributes")

    for relative in RAW_RELATIVE:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"raw evidence with trailing whitespace  \r\n")

    authored = repo / "tests/authored.py"
    authored.parent.mkdir(parents=True)
    authored.write_text("value = 1  \n", encoding="utf-8")
    authored_receipt = repo / "projects/biella-games/Build/Presentation/sample/receipt.json"
    authored_receipt.write_text("{}  \n", encoding="utf-8")

    assert _git(repo, "add", ".").returncode == 0
    first = _git(repo, "diff", "--cached", "--check")
    assert first.returncode != 0
    assert "tests/authored.py" in first.stdout
    assert "projects/biella-games/Build/Presentation/sample/receipt.json" in first.stdout
    for relative in RAW_RELATIVE:
        assert str(relative) not in first.stdout

    authored.write_text("value = 1\n", encoding="utf-8")
    authored_receipt.write_text("{}\n", encoding="utf-8")
    assert _git(repo, "add", "tests/authored.py", str(authored_receipt.relative_to(repo))).returncode == 0
    clean = _git(repo, "diff", "--cached", "--check")
    assert clean.returncode == 0, clean.stdout
