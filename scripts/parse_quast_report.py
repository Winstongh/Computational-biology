#!/usr/bin/env python3
"""Parse the relevant QUAST metrics into a stable, analysis-friendly CSV."""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

try:
    from scripts.benchmark_common import parse_run_id
except ModuleNotFoundError:
    from benchmark_common import parse_run_id


TECHNOLOGY_ORDER = ("Illumina", "Nanopore", "PacBio HiFi", "Hybrid")
LEGACY_CSV_FIELDS = (
    "technology",
    "n50",
    "contigs",
    "largest_contig",
    "total_length",
    "genome_fraction_pct",
    "mismatches_per_100_kbp",
    "indels_per_100_kbp",
    "misassemblies",
)
AXIS_FIELDS = (
    "run_id",
    "tech",
    "generation",
    "coverage",
    "assembler",
    "reference",
    "seed",
)
METRIC_FIELDS = LEGACY_CSV_FIELDS[1:]
EXTRA_FIELDS = (
    "busco_complete_pct",
    "merqury_qv",
    "ram_mb",
    "wall_sec",
)
CSV_FIELDS = AXIS_FIELDS + METRIC_FIELDS + EXTRA_FIELDS

METRIC_ALIASES = {
    "n50": "n50",
    "# contigs": "contigs",
    "# contigs (>= 0 bp)": "contigs",
    "largest contig": "largest_contig",
    "total length": "total_length",
    "genome fraction (%)": "genome_fraction_pct",
    "# mismatches per 100 kbp": "mismatches_per_100_kbp",
    "# indels per 100 kbp": "indels_per_100_kbp",
    "# misassemblies": "misassemblies",
}

INTEGER_FIELDS = {
    "n50",
    "contigs",
    "largest_contig",
    "total_length",
    "misassemblies",
}
REQUIRED_FIELDS = {
    "n50",
    "contigs",
    "largest_contig",
    "total_length",
}
OPTIONAL_ALIGNMENT_FIELDS = {
    "genome_fraction_pct",
    "mismatches_per_100_kbp",
    "indels_per_100_kbp",
    "misassemblies",
}


def _normalize_technology(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "", name.lower())
    aliases = {
        "illumina": "Illumina",
        "illumina30x": "Illumina",
        "nanopore": "Nanopore",
        "nanopore30x": "Nanopore",
        "pacbiohifi": "PacBio HiFi",
        "hifi": "PacBio HiFi",
        "hifi30x": "PacBio HiFi",
        "hybrid": "Hybrid",
        "hybridassembly": "Hybrid",
    }
    return aliases.get(key, name.strip().replace("_", " "))


def _parse_value(raw_value: str, field: str) -> int | float | None:
    value = raw_value.strip().replace(",", "")
    if value.lower() in {"", "-", "na", "n/a", "none"}:
        return None
    try:
        if field in INTEGER_FIELDS:
            return int(float(value))
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Cannot parse QUAST value {raw_value!r} for {field}") from exc


def parse_quast_report(
    report_path: str | Path,
    expected_assemblies: Iterable[str] | None = TECHNOLOGY_ORDER,
) -> list[dict[str, Any]]:
    """Parse one multi-assembly QUAST TSV report."""
    path = Path(report_path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))

    if not rows or len(rows[0]) < 2 or rows[0][0].strip().lower() != "assembly":
        raise ValueError(f"{path}: invalid QUAST report header")

    technologies = [_normalize_technology(value) for value in rows[0][1:]]
    expected = tuple(expected_assemblies) if expected_assemblies is not None else tuple(technologies)
    missing_assemblies = [name for name in expected if name not in technologies]
    if missing_assemblies:
        raise ValueError(
            "Expected assemblies are missing from the QUAST report: "
            + ", ".join(missing_assemblies)
        )

    values_by_technology: dict[str, dict[str, Any]] = {
        technology: {"technology": technology} for technology in technologies
    }
    found_fields: set[str] = set()

    for row in rows[1:]:
        if not row:
            continue
        metric_name = row[0].strip().lower()
        field = METRIC_ALIASES.get(metric_name)
        if field is None:
            continue
        # Prefer QUAST's plain "# contigs" metric if both variants are present.
        if field == "contigs" and field in found_fields and metric_name != "# contigs":
            continue

        found_fields.add(field)
        for technology, raw_value in zip(technologies, row[1:]):
            values_by_technology[technology][field] = _parse_value(raw_value, field)

    missing_fields = sorted(REQUIRED_FIELDS - found_fields)
    if missing_fields:
        display_names = {
            "n50": "N50",
            "contigs": "# contigs",
            "largest_contig": "Largest contig",
            "total_length": "Total length",
            "genome_fraction_pct": "Genome fraction (%)",
            "mismatches_per_100_kbp": "# mismatches per 100 kbp",
            "indels_per_100_kbp": "# indels per 100 kbp",
            "misassemblies": "# misassemblies",
        }
        raise ValueError(
            f"{path}: QUAST report is missing required metric(s): "
            + ", ".join(display_names[field] for field in missing_fields)
        )

    return [
        {field: values_by_technology[name].get(field) for field in LEGACY_CSV_FIELDS}
        for name in expected
    ]


def row_with_run_context(
    metric_row: dict[str, Any],
    run_id: str,
    generation: str | None = None,
    busco: float | None = None,
    merqury: float | None = None,
    ram_mb: float | None = None,
    wall_sec: float | None = None,
) -> dict[str, Any]:
    """Attach run-id axis fields and optional BUSCO/Merqury/resource metrics."""
    context = parse_run_id(run_id)
    row = {field: metric_row.get(field) for field in METRIC_FIELDS}
    return {
        "run_id": run_id,
        "generation": generation or context["tech"],
        **context,
        **row,
        "busco_complete_pct": busco,
        "merqury_qv": merqury,
        "ram_mb": ram_mb,
        "wall_sec": wall_sec,
    }


def write_metrics_csv(rows: Iterable[dict[str, Any]], output_path: str | Path) -> Path:
    """Write parsed QUAST rows while preserving missing values as blank cells."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(rows)
    fieldnames = (
        CSV_FIELDS
        if any("run_id" in row for row in materialized)
        else LEGACY_CSV_FIELDS
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in materialized:
            writer.writerow(
                {
                    field: "" if row.get(field) is None else row.get(field)
                    for field in fieldnames
                }
            )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="QUAST report.tsv")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results/tables/assembly_metrics.csv"),
    )
    parser.add_argument("--without-hybrid", action="store_true")
    args = parser.parse_args()

    expected = TECHNOLOGY_ORDER[:-1] if args.without_hybrid else TECHNOLOGY_ORDER
    rows = parse_quast_report(args.report, expected)
    write_metrics_csv(rows, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
