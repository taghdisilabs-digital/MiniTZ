"""Content-addressed donor extraction; never execute or retire donor code."""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
from .source import canonical, sha, SECRET

PROTECTED_NAMES = {"auth.json", "id_rsa", "id_ed25519", "credentials.json", "broker.token"}
PROTECTED_DIRS = {".ssh", ".codex", "credentials", "secrets"}


def _paths(root: Path) -> list[str]:
    if (root / ".git").exists():
        result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, timeout=30, check=True)
        return sorted(set(item for item in result.stdout.decode().split("\0") if item))
    result = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in {".git", "__pycache__", ".venv", ".pytest_cache"}]
        result.extend((Path(current) / name).relative_to(root).as_posix() for name in files)
    return sorted(result)


def _extract(raw: bytes) -> dict:
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError, UnicodeError) as exc:
        return {"parse_state": "REQUIRES_SOURCE_REVIEW", "error_type": type(exc).__name__, "symbols": [], "imports": []}
    symbols, imports = [], []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"kind": "function", "name": node.name, "line": node.lineno, "arguments": [arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]})
        elif isinstance(node, ast.ClassDef):
            symbols.append({"kind": "class", "name": node.name, "line": node.lineno, "methods": [item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]})
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append("." * node.level + (node.module or ""))
    return {"parse_state": "EXTRACTED_NOT_SEMANTICALLY_QUALIFIED", "symbols": symbols, "imports": sorted(set(imports))}


def inventory(donor: Path, source: Path, output: Path) -> dict:
    donor, source, output = Path(donor).resolve(), Path(source).resolve(), Path(output).resolve()
    if donor == source or not donor.is_dir() or not source.is_dir():
        raise ValueError("Donor and canonical source must be distinct existing directories")
    if output.is_relative_to(donor):
        raise ValueError("Evidence output must not mutate the donor")
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = output.parent / "parsed-source-cache"
    cache.mkdir(exist_ok=True)
    cache.chmod(0o700)
    parser_digest = sha(Path(__file__))
    rows = []
    created = reused = 0
    for relative in _paths(donor):
        path = donor / relative
        row = {"path": relative, "semantic_validation": "PENDING", "retirement_allowed": False}
        if path.is_symlink():
            row["classification"] = "SYMLINK_REFERENCE_ONLY"; rows.append(row); continue
        if Path(relative).is_absolute() or ".." in Path(relative).parts or not path.resolve().is_relative_to(donor):
            row["classification"] = "OUT_OF_SCOPE_REFERENCE"; rows.append(row); continue
        if not path.is_file():
            row["classification"] = "MISSING_FROM_DONOR_WORKTREE"; rows.append(row); continue
        row["size"] = path.stat().st_size
        if path.name in PROTECTED_NAMES or path.name.startswith(".env") or path.suffix in {".key", ".pem"} or PROTECTED_DIRS.intersection(path.relative_to(donor).parts):
            row["classification"] = "PROTECTED_CREDENTIAL_REFERENCE"; rows.append(row); continue
        if row["size"] > 64 * 1024 * 1024:
            row["classification"] = "LARGE_DONOR_OBJECT_REQUIRES_SCOPED_TRANSFER"; rows.append(row); continue
        raw = path.read_bytes()
        if SECRET.search(raw):
            row["classification"] = "PROTECTED_CONTENT_REQUIRES_CREDENTIAL_REVIEW"; rows.append(row); continue
        digest = hashlib.sha256(raw).hexdigest(); row["donor_sha256"] = digest
        target = source / relative
        if target.is_file() and not target.is_symlink() and target.resolve().is_relative_to(source):
            current = sha(target); row["canonical_sha256"] = current
            row["classification"] = "BYTE_EQUIVALENT_PRESENT" if current == digest else "DIVERGENT_REQUIRES_SEMANTIC_RESOLUTION"
            row["candidate_destination"] = relative
        else:
            row["classification"] = "UNMAPPED_DONOR_VALUE"
        if path.suffix == ".py":
            key = hashlib.sha256(canonical({"source": digest, "parser": parser_digest})).hexdigest()
            parsed_path = cache / (key + ".json")
            try:
                parsed = json.loads(parsed_path.read_text())
                if parsed.get("source_sha256") != digest or parsed.get("parser_sha256") != parser_digest:
                    raise ValueError("Parse cache identity mismatch")
                reused += 1
            except (OSError, ValueError):
                parsed = {**_extract(raw), "source_sha256": digest, "parser_sha256": parser_digest}
                temporary = parsed_path.with_suffix(".tmp")
                temporary.write_bytes(canonical(parsed) + b"\n"); temporary.chmod(0o600); os.replace(temporary, parsed_path)
                created += 1
            row.update({key: parsed[key] for key in ("parse_state", "symbols", "imports")})
            row["parsed_source_ref"] = str(parsed_path)
        rows.append(row)
    counts = dict(Counter(row["classification"] for row in rows))
    inputs = [{key: row.get(key) for key in ("path", "size", "donor_sha256", "canonical_sha256", "classification")} for row in rows]
    result = {"schema": "minitz.donor-extraction/v1", "authority": "DONOR_EVIDENCE_ONLY", "product": "MiniTZ OS",
        "donor_root": os.environ.get("MINITZ_DONOR_ORIGIN", str(donor)),
        "canonical_source_root": os.environ.get("MINITZ_CANONICAL_ORIGIN", str(source)),
        "input_digest": hashlib.sha256(canonical(inputs)).hexdigest(), "file_count": len(rows), "classification_counts": counts,
        "parses_created": created, "parses_reused": reused, "files": rows, "retirement_allowed": False,
        "semantic_transfer_complete": False,
        "next_required_operation": "Resolve unique donor value against current owner direction; normalize, validate, integrate and record provenance before retirement"}
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(canonical(result) + b"\n"); temporary.chmod(0o600); os.replace(temporary, output)
    return result
