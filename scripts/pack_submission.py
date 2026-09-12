from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "code.zip"

INCLUDE_ROOT_FILES = {
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "main.py",
    "problem_statement.md",
    ".env.example",
}

INCLUDE_DIRS = (
    "src",
    "code",
    "tests",
    "evaluation",
    "scripts",
)

SKIP_PARTS = {
    ".git",
    ".venv",
    ".cache",
    ".pytest_cache",
    "__pycache__",
    ".cursor",
}

SKIP_FILES = {
    ".env",
    "log.txt",
    "output.csv",
    "sample_output.csv",
    "code.zip",
}


def _keep(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    return not any(part in SKIP_PARTS for part in path.parts)


def main() -> None:
    files: list[Path] = []
    for name in INCLUDE_ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            files.append(path)
    for folder in INCLUDE_DIRS:
        root = ROOT / folder
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and _keep(path.relative_to(ROOT)):
                files.append(path)

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
    names = zipfile.ZipFile(OUT).namelist()
    print(f"wrote {OUT} ({len(names)} files, {OUT.stat().st_size} bytes)")
    required = [
        "evaluation/usage_report.md",
        "code/main.py",
        "code/README.md",
        "README.md",
        "src/pipeline.py",
    ]
    missing = [item for item in required if item not in names]
    if missing:
        raise SystemExit(f"missing from zip: {missing}")
    leaked = [item for item in names if item.endswith(".env") or item == "log.txt"]
    if leaked:
        raise SystemExit(f"secrets leaked into zip: {leaked}")


if __name__ == "__main__":
    main()
