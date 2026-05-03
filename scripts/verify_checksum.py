"""Verify the canonical simulation output against the blessed checksum.

Reads ``outputs/checksums.txt`` (lines of '<sha256>  <filename>',
'#' lines ignored) and verifies that each named file under
``outputs/`` matches its recorded hash. For ``.parquet`` files the
hash is computed over a canonical, sorted, fixed-precision CSV
serialisation (sha256_dataframe_content) so the verification survives
platform-dependent Parquet metadata, dictionary encoding, and
compression variation. For all other files the hash is the standard
file SHA256.

Exits non-zero on any mismatch. Used by the CI reproducibility
workflow.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path so the script runs from a clean checkout without an
# editable install. CI installs the package, but local invocations of
# this script before `pip install -e .` should still work.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from idc_simulation.run_log import (  # noqa: E402
    sha256_cell_summaries,
    sha256_dataframe_content,
    sha256_file,
)

CHECKSUM_FILE = Path("outputs/checksums.txt")
OUTPUTS_DIR = Path("outputs")


def _hash_for(path: Path) -> str:
    # Parquet outputs are dispatched by filename. Each is hashed via the
    # most cross-platform-stable function for its content shape.
    name = path.name
    if name == "severity_weighted.parquet":
        # Already-aggregated summary table; hash with 6-sig-fig CSV
        # canonicalisation per plan Section 6.3. Under plan v2.0 the
        # leading sort key is `regime` (the table is regime-stratified).
        return sha256_dataframe_content(
            path,
            sort_keys=("regime", "prior_set", "horizon", "tier_option"),
            float_precision=6,
        )
    if name.startswith("contamination_seed") and name.endswith(".parquet"):
        # Raw per-sample data; aggregate to per-cell summary vector and
        # hash that (averages out sub-ULP RNG differences across CPUs).
        return sha256_cell_summaries(path)
    if path.suffix == ".parquet":
        # Defensive default for any future Parquet output.
        return sha256_cell_summaries(path)
    return sha256_file(path)


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
        actual = _hash_for(target)
        if actual != expected:
            failures.append(f"mismatch: {filename}\n  expected {expected}\n  actual   {actual}")
        else:
            kind = "summary" if target.suffix == ".parquet" else "file"
            print(f"OK  {filename}  ({kind})  {actual}")
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
