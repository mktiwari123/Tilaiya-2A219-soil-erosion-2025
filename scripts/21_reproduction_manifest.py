"""Checksum inventory of the files needed to reproduce the manuscript tables.

This script does not upload anything. It records what is on disk.
"""

from hashlib import sha256
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "tables" / "reproduction_manifest.csv"

RELATIVE_DIRS = (
    "scripts",
    "tilaiya",
    "tests",
    "output/tables",
    "output/figures/maps",
    "output/rasters",
    "data/dem",
)
EXTRA = (
    "config.py",
    "README.md",
    "requirements.txt",
    "pytest.ini",
)


def files():
    found = []
    for relative in RELATIVE_DIRS:
        folder = ROOT / relative
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.name == "reproduction_manifest.csv":
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            found.append(path)
    for relative in EXTRA:
        path = ROOT / relative
        if path.is_file():
            found.append(path)
    return sorted(set(found))


def digest(path):
    hasher = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main():
    rows = []
    for path in files():
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} files -> {OUT}")


if __name__ == "__main__":
    main()
