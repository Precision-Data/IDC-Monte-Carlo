"""Verify the canonical Parquet matches the blessed checksum.

Reads ``outputs/checksums.txt`` (lines of '<sha256>  <filename>',
'#' lines ignored) and verifies that each named file under
``outputs/`` hashes to the recorded value. Exits non-zero on any
mismatch. Used by the CI reproducibility workflow.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

CHECKSUM_FILE = Path("outputs/checksums.txt")
OUTPUTS_DIR = Path("outputs")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not CHECKSUM_FILE.is_file():
        print(f"ERROR: missing checksum file {CHECKSUM_FILE}", file=sys.stderr)
        return 2
    failures: list[str] = []
    checked = 0
    for line in CHECKSUM_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, filename = line.split(maxsplit=1)
        except ValueError:
            print(f"ERROR: malformed line: {line!r}", file=sys.stderr)
            return 2
        target = OUTPUTS_DIR / filename
        if not target.is_file():
            failures.append(f"missing: {target}")
            continue
        actual = _sha256(target)
        if actual != expected:
            failures.append(f"mismatch: {filename}\n  expected {expected}\n  actual   {actual}")
        else:
            print(f"OK  {filename}  {actual}")
        checked += 1
    if not checked:
        print("ERROR: no checksum entries to verify", file=sys.stderr)
        return 2
    if failures:
        print("\nCHECKSUM VERIFICATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"\nAll {checked} checksum(s) verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
