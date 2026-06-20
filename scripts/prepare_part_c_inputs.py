#!/usr/bin/env python3
"""Discover the assembly files produced by the earlier project stages."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

try:
    from scripts.fasta_utils import assembly_stats, fasta_lengths
except ModuleNotFoundError:
    from fasta_utils import assembly_stats, fasta_lengths


ASSEMBLY_CANDIDATES = OrderedDict(
    [
        (
            "Illumina",
            (
                "assemblies/illumina_30x/contigs.fasta",
                "assemblies/illumina_30x/illumina_30x.fasta",
            ),
        ),
        (
            "Nanopore",
            (
                "assemblies/nanopore_30x/assembly.fasta",
                "assemblies/nanopore_30x/nanopore_30x.fasta",
                "assemblies/nanopore_30x/nanopore_polished_assembly_v2.fasta",
                "assemblies/nanopore_30x/nanopore_polished_assembly.fasta",
            ),
        ),
        (
            "PacBio HiFi",
            (
                "assemblies/hifi_30x/assembly.fasta",
                "assemblies/hifi_30x/hifi_30x.fasta",
            ),
        ),
        (
            "Hybrid",
            (
                "assemblies/hybrid/assembly.fasta",
                "assemblies/hybrid/hybrid_assembly.fasta",
            ),
        ),
    ]
)


def discover_assembly_paths(
    project_root: str | Path = ".",
    include_hybrid: bool = True,
) -> OrderedDict[str, Path]:
    """Return the first valid assembly path found for each technology."""
    root = Path(project_root).resolve()
    discovered: OrderedDict[str, Path] = OrderedDict()
    missing: list[str] = []

    for technology, candidates in ASSEMBLY_CANDIDATES.items():
        if technology == "Hybrid" and not include_hybrid:
            continue

        selected = next((root / path for path in candidates if (root / path).is_file()), None)
        if selected is None:
            missing.append(f"{technology}: {', '.join(candidates)}")
            continue

        # Validate inputs before QUAST starts so failures are immediate and clear.
        assembly_stats(fasta_lengths(selected))
        discovered[technology] = selected

    required = {"Illumina", "Nanopore", "PacBio HiFi"}
    if include_hybrid:
        required.add("Hybrid")
    required_missing = required - set(discovered)
    if required_missing:
        details = "\n  ".join(missing)
        raise FileNotFoundError(f"Missing Part C assembly input(s):\n  {details}")

    return discovered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--without-hybrid", action="store_true")
    args = parser.parse_args()

    paths = discover_assembly_paths(
        args.project_root,
        include_hybrid=not args.without_hybrid,
    )
    for technology, path in paths.items():
        stats = assembly_stats(fasta_lengths(path))
        print(
            f"{technology}\t{path}\t"
            f"{stats['sequences']} contigs\t{stats['total_length']} bp"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
