#!/usr/bin/env python3
"""Small, dependency-free FASTA helpers used by the Part C pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


VALID_FASTA_BASES = frozenset("ACGTRYSWKMBDHVN-.")


def read_fasta(path: str | Path) -> dict[str, str]:
    """Read all FASTA records into an ordered ``{name: sequence}`` mapping."""
    fasta_path = Path(path)
    records: dict[str, list[str]] = {}
    current_name: str | None = None

    with fasta_path.open(encoding="ascii") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                current_name = line[1:].strip().split()[0]
                if not current_name:
                    current_name = f"record_{line_number}"
                if current_name in records:
                    raise ValueError(f"{fasta_path}: duplicate FASTA record {current_name!r}")
                records[current_name] = []
                continue
            if current_name is None:
                raise ValueError(
                    f"{fasta_path}: sequence data appears before the first FASTA header"
                )
            sequence = "".join(line.split()).upper()
            invalid = sorted(set(sequence) - VALID_FASTA_BASES)
            if invalid:
                raise ValueError(
                    f"{fasta_path}: invalid FASTA character(s) "
                    f"{''.join(invalid)!r} at line {line_number}"
                )
            records[current_name].append(sequence)

    if not records:
        raise ValueError(f"{fasta_path}: contains no FASTA sequences")

    joined = {name: "".join(parts) for name, parts in records.items()}
    empty = [name for name, sequence in joined.items() if not sequence]
    if empty:
        raise ValueError(f"{fasta_path}: FASTA record {empty[0]!r} has no sequence")
    return joined


def write_fasta(records: dict[str, str], path: str | Path, line_width: int = 80) -> Path:
    """Write FASTA records with wrapped sequence lines."""
    fasta_path = Path(path)
    fasta_path.parent.mkdir(parents=True, exist_ok=True)
    with fasta_path.open("w", encoding="ascii", newline="\n") as handle:
        for name, sequence in records.items():
            seq = "".join(sequence.split()).upper()
            invalid = sorted(set(seq) - VALID_FASTA_BASES)
            if invalid:
                raise ValueError(
                    f"{name}: invalid FASTA character(s) {''.join(invalid)!r}"
                )
            handle.write(f">{name}\n")
            for start in range(0, len(seq), line_width):
                handle.write(seq[start : start + line_width] + "\n")
    return fasta_path


def fasta_lengths(path: str | Path) -> list[int]:
    """Return sequence lengths from a FASTA file after validating its records."""
    fasta_path = Path(path)
    lengths: list[int] = []
    current_header: str | None = None
    current_length = 0

    with fasta_path.open(encoding="ascii") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith(">"):
                if current_header is not None:
                    if current_length == 0:
                        raise ValueError(
                            f"{fasta_path}: FASTA record {current_header!r} has no sequence"
                        )
                    lengths.append(current_length)

                current_header = line[1:].strip()
                if not current_header:
                    current_header = f"record at line {line_number}"
                current_length = 0
                continue

            if current_header is None:
                raise ValueError(
                    f"{fasta_path}: sequence data appears before the first FASTA header"
                )

            sequence = "".join(line.split()).upper()
            invalid = sorted(set(sequence) - VALID_FASTA_BASES)
            if invalid:
                raise ValueError(
                    f"{fasta_path}: invalid FASTA character(s) "
                    f"{''.join(invalid)!r} at line {line_number}"
                )
            current_length += len(sequence)

    if current_header is None:
        raise ValueError(f"{fasta_path}: contains no FASTA sequences")
    if current_length == 0:
        raise ValueError(f"{fasta_path}: FASTA record {current_header!r} has no sequence")

    lengths.append(current_length)
    return lengths


def assembly_stats(lengths: Iterable[int]) -> dict[str, int]:
    """Compute sequence count, total length, largest contig, and N50."""
    values = list(lengths)
    if not values:
        raise ValueError("Cannot calculate assembly statistics without sequences")
    if any(length <= 0 for length in values):
        raise ValueError("FASTA sequence lengths must be positive")

    total_length = sum(values)
    threshold = total_length / 2
    cumulative = 0
    n50 = 0
    for length in sorted(values, reverse=True):
        cumulative += length
        if cumulative >= threshold:
            n50 = length
            break

    return {
        "sequences": len(values),
        "total_length": total_length,
        "largest_contig": max(values),
        "n50": n50,
    }
