from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_one_repo_contains_games_website_and_reusable_schema():
    assert (ROOT / "projects/biella-games/BiellaGames.uproject").is_file()
    assert (ROOT / "website/src/control/index.html").is_file()
    assert (ROOT / "schemas/source_record.schema.json").is_file()


def test_future_aaa_program_is_preserved_but_blocked():
    master = ROOT / "docs/future/aaa-challenger-solo-founder/AAA_SF_MASTER_PLAN.md"
    assert master.is_file()
    text = master.read_text(encoding="utf-8")
    assert "FUTURE_PROGRAM_BLOCKED" in text
    assert "no `AAA-SF-*` task may become active" in text


def test_migration_provenance_names_exact_preserved_sources():
    provenance = ROOT / "docs/migration/ONE_REPO_PROVENANCE_2026-09-05.md"
    text = provenance.read_text(encoding="utf-8")
    assert "f7e74205988cb48946e62efeffe5c5330ec6437b" in text
    assert "aa718584a99c0cee1884488bb4dafec4d2e94c05" in text
    assert "b621a0680c5586a1502558efb81ff084f8d1da74" in text
    assert "297129637fded33dc0e3636954645e5655803928" in text
