#!/usr/bin/env python3
"""Compute read statistics for all simulated FASTQ datasets."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required. Install environment-bench.yml first.") from exc

DEFAULT_GENOME_SIZE = 4_641_652
FIELDNAMES = [
    "dataset",
    "tech",
    "coverage",
    "reference",
    "read_files",
    "total_reads",
    "total_bases",
    "avg_read_length",
    "n50",
    "estimated_coverage",
]
DATASET_RE = re.compile(
    r"^(?P<tech>illumina|ont_r9|ont_r10|hifi)_(?P<coverage>\d+)x(?:_(?P<reference>.+))?$"
)


def parse_fastq_lengths(path: Path):
    with path.open("r", buffering=1 << 20, encoding="utf-8") as handle:
        while True:
            header = handle.readline()
            if not header:
                return
            sequence = handle.readline().rstrip("\n")
            plus = handle.readline()
            quality = handle.readline()
            if not header.startswith("@") or not plus.startswith("+") or not quality:
                raise ValueError(f"Malformed FASTQ record in {path}")
            yield len(sequence)


def compute_n50(lengths: list[int]) -> int:
    if not lengths:
        return 0
    half = sum(lengths) / 2
    cumulative = 0
    for length in sorted(lengths, reverse=True):
        cumulative += length
        if cumulative >= half:
            return length
    return 0


def dataset_files(tech: str, coverage: int) -> list[Path]:
    prefix = Path("data/reads") / f"{tech}_{coverage}x"
    if tech == "illumina":
        return [Path(f"{prefix}_1.fastq"), Path(f"{prefix}_2.fastq")]
    return [Path(f"{prefix}.fastq")]


def compute_stats(
    dataset: str,
    tech: str,
    coverage: int,
    reference: str,
    files: list[Path],
    genome_size: int,
) -> dict:
    lengths: list[int] = []
    for path in files:
        print(f"  Parsing {path}", flush=True)
        lengths.extend(parse_fastq_lengths(path))
    total_reads = len(lengths)
    total_bases = sum(lengths)
    return {
        "dataset": dataset,
        "tech": tech,
        "coverage": coverage,
        "reference": reference,
        "read_files": ";".join(str(path) for path in files),
        "total_reads": total_reads,
        "total_bases": total_bases,
        "avg_read_length": round(total_bases / total_reads, 2) if total_reads else 0,
        "n50": compute_n50(lengths),
        "estimated_coverage": round(total_bases / genome_size, 2),
    }


def _dataset_from_path(path: Path) -> tuple[str, str, int, str] | None:
    stem = path.name.removesuffix(".fastq")
    if stem.startswith("illumina_") and (stem.endswith("_1") or stem.endswith("_2")):
        stem = stem[:-2]
    match = DATASET_RE.match(stem)
    if not match:
        return None
    tech = match.group("tech")
    coverage = int(match.group("coverage"))
    reference = match.group("reference") or "orig"
    return stem, tech, coverage, reference


def scan_existing_datasets(reads_dir: Path = Path("data/reads")) -> list[tuple[str, str, int, str, list[Path]]]:
    grouped: dict[str, tuple[str, int, str, list[Path]]] = {}
    for path in sorted(reads_dir.glob("*.fastq")):
        parsed = _dataset_from_path(path)
        if parsed is None:
            continue
        dataset, tech, coverage, reference = parsed
        if dataset not in grouped:
            grouped[dataset] = (tech, coverage, reference, [])
        grouped[dataset][3].append(path)

    datasets: list[tuple[str, str, int, str, list[Path]]] = []
    for dataset, (tech, coverage, reference, files) in grouped.items():
        files = sorted(files)
        if tech == "illumina":
            expected = {f"{dataset}_1.fastq", f"{dataset}_2.fastq"}
            present = {path.name for path in files}
            if not expected.issubset(present):
                continue
            files = [Path("data/reads") / name for name in sorted(expected)]
        datasets.append((dataset, tech, coverage, reference, files))
    return sorted(datasets, key=lambda item: (item[3], item[1], item[2], item[0]))


def load_datasets_from_config(config_path: Path, only_existing: bool) -> list[tuple[str, str, int, str, list[Path]]]:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    datasets: list[tuple[str, str, int, str, list[Path]]] = []
    for tech in cfg["technologies"]:
        for coverage in cfg["coverages"]:
            files = dataset_files(tech, int(coverage))
            if only_existing and not all(path.is_file() for path in files):
                continue
            datasets.append((f"{tech}_{int(coverage)}x", tech, int(coverage), "orig", files))
    return datasets


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def print_table(rows: list[dict]) -> None:
    print("dataset,total_reads,total_bases,n50,estimated_coverage")
    for row in rows:
        print(
            f"{row['dataset']},{row['total_reads']},{row['total_bases']},"
            f"{row['n50']},{row['estimated_coverage']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/matrix.yaml")
    parser.add_argument("--output", default="results/tables/read_stats.csv")
    parser.add_argument("--genome-size", type=int, default=DEFAULT_GENOME_SIZE)
    parser.add_argument(
        "--only-existing",
        action="store_true",
        help="Skip datasets whose FASTQ files are not present.",
    )
    parser.add_argument(
        "--from-config",
        action="store_true",
        help="Use config-defined main-matrix datasets instead of scanning data/reads.",
    )
    args = parser.parse_args()

    if not Path("data/reference/ecoli.fasta").is_file():
        print("Run from project root; data/reference/ecoli.fasta was not found.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    datasets = (
        load_datasets_from_config(Path(args.config), args.only_existing)
        if args.from_config
        else scan_existing_datasets()
    )
    for dataset, tech, coverage, reference, files in datasets:
        missing = [str(path) for path in files if not path.is_file()]
        if missing:
            print(f"Missing FASTQ files for {tech}_{coverage}x: {', '.join(missing)}", file=sys.stderr)
            return 1
        rows.append(compute_stats(dataset, tech, coverage, reference, files, args.genome_size))

    if not rows:
        print("No read datasets found.", file=sys.stderr)
        return 1

    write_csv(rows, Path(args.output))
    print_table(rows)
    print(f"Results saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
