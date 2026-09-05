from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
required = [
    "BiellaGames.uproject",
    "Source/BiellaGames/Public/BiellaDemoPawn.h",
    "Source/BiellaGames/Private/BiellaDemoPawn.cpp",
    "Source/BiellaGames/Public/BiellaInfected.h",
    "Source/BiellaGames/Private/BiellaInfected.cpp",
    "Source/BiellaGames/Public/BiellaRival.h",
    "Source/BiellaGames/Private/BiellaRival.cpp",
    "Config/DefaultInput.ini",
    "Content/Maps/BiellaGameplayMap.umap",
    "docs/PRODUCTION.md",
]
missing = [p for p in required if not (root / p).is_file()]
if missing:
    print("MISSING:", ", ".join(missing))
    sys.exit(1)

source = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("Source/BiellaGames/**/*") if p.suffix in {".h", ".cpp"})
for token in ("D01_SIGNAL", "FireWeapon", "ABiellaInfected", "TryMeleeTarget"):
    assert token in source, token

production = (root / "docs/PRODUCTION.md").read_text(encoding="utf-8")
ids = re.findall(r"^- \[[ xX]\] (D01-\d{3}) \|", production, re.M)
assert ids == [f"D01-{i:03d}" for i in range(1, 51)]
completed = re.findall(r"^- \[[xX]\] (D01-\d{3}) \|", production, re.M)
incomplete = re.findall(r"^- \[ \] (D01-\d{3}) \|", production, re.M)
match = re.search(r"^Current task: `([^`]+)`$", production, re.M)
assert match, "current task metadata missing"
current = match.group(1)
assert incomplete and current == incomplete[0], (current, incomplete[:1])
assert completed == [f"D01-{i:03d}" for i in range(1, len(completed) + 1)]
print(f"DEMO01_STRUCTURE_PASS completed={len(completed)}/50 current={current}")
