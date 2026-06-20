#!/usr/bin/env python3
"""Build repeat-injected and plasmid-bearing reference variants."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

try:
    from scripts.fasta_utils import read_fasta, write_fasta
except ModuleNotFoundError:
    from fasta_utils import read_fasta, write_fasta


def inject_tandem_repeat(seq: str, unit_len: int, copies: int, at: int) -> str:
    """Insert ``copies`` copies of the sequence window ``seq[at:at+unit_len]``."""
    if unit_len <= 0:
        raise ValueError("unit_len must be positive")
    if copies <= 0:
        raise ValueError("copies must be positive")
    if at < 0 or at + unit_len > len(seq):
        raise ValueError("repeat insertion window is outside the sequence")
    unit = seq[at : at + unit_len]
    return seq[:at] + unit * copies + seq[at:]


def append_plasmid(
    records: dict[str, str],
    plasmid_len: int,
    seed: int,
    name: str = "plasmid",
) -> dict[str, str]:
    """Append one deterministic synthetic plasmid record."""
    if plasmid_len <= 0:
        raise ValueError("plasmid_len must be positive")
    rng = random.Random(seed)
    plasmid = "".join(rng.choice("ACGT") for _ in range(plasmid_len))
    out = dict(records)
    out[name] = plasmid
    return out


def build_variants(
    reference: str | Path = "data/reference/ecoli.fasta",
    out_dir: str | Path = "data/reference",
    seed: int = 13,
) -> dict[str, Path]:
    """Build the three L3 reference variants from the original reference."""
    records = read_fasta(reference)
    first_name, seq = next(iter(records.items()))
    out = Path(out_dir)

    rep_v1 = inject_tandem_repeat(seq, unit_len=5_000, copies=3, at=1_000_000)

    rng = random.Random(seed)
    rep_v2 = seq
    for _ in range(6):
        at = rng.randrange(0, len(rep_v2) - 2_000)
        rep_v2 = inject_tandem_repeat(rep_v2, unit_len=1_500, copies=2, at=at)

    paths = {
        "rep_v1": write_fasta({first_name: rep_v1}, out / "ecoli_rep_v1.fasta"),
        "rep_v2": write_fasta({first_name: rep_v2}, out / "ecoli_rep_v2.fasta"),
        "plasmid": write_fasta(
            append_plasmid(records, plasmid_len=50_000, seed=seed),
            out / "ecoli_plasmid.fasta",
        ),
    }
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="data/reference/ecoli.fasta")
    parser.add_argument("--out-dir", default="data/reference")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    paths = build_variants(args.reference, args.out_dir, args.seed)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

