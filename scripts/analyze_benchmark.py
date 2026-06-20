#!/usr/bin/env python3
"""Benchmark analysis: viability, Pareto front, variance attribution, plots."""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-benchmark")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/benchmark-cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


NUMERIC_FIELDS = {
    "coverage",
    "seed",
    "n50",
    "contigs",
    "largest_contig",
    "total_length",
    "genome_fraction_pct",
    "mismatches_per_100_kbp",
    "indels_per_100_kbp",
    "misassemblies",
    "busco_complete_pct",
    "merqury_qv",
    "ram_mb",
    "wall_sec",
}


def _records(rows: Any) -> list[dict[str, Any]]:
    """Accept a pandas-like DataFrame or a list of dictionaries."""
    if hasattr(rows, "to_dict"):
        return list(rows.to_dict("records"))
    return [dict(row) for row in rows]


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def read_csv_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in NUMERIC_FIELDS:
            if field in row:
                row[field] = _num(row[field])
    return rows


def min_viable_coverage(
    rows: Any,
    gf_threshold: float = 99.0,
    max_contigs: int = 1,
) -> int | None:
    """Return the minimum coverage meeting genome-fraction and contig targets."""
    candidates = []
    for row in _records(rows):
        genome_fraction = _num(row.get("genome_fraction_pct"))
        contigs = _num(row.get("contigs"))
        coverage = _num(row.get("coverage"))
        if genome_fraction is None or contigs is None or coverage is None:
            continue
        if genome_fraction >= gf_threshold and contigs <= max_contigs:
            candidates.append(int(coverage))
    return min(candidates) if candidates else None


def variance_attribution(
    rows: Any,
    value: str = "n50",
    factors: Iterable[str] = ("tech", "assembler"),
) -> dict[str, float]:
    """Compute a simple between-group sum-of-squares share for each factor."""
    records = [row for row in _records(rows) if _num(row.get(value)) is not None]
    if not records:
        return {factor: 0.0 for factor in factors}
    values = [_num(row[value]) for row in records]
    grand = sum(values) / len(values)
    total_ss = sum((value_ - grand) ** 2 for value_ in values)
    out: dict[str, float] = {}
    for factor in factors:
        groups: dict[Any, list[float]] = defaultdict(list)
        for row in records:
            groups[row.get(factor)].append(_num(row[value]))
        ss = sum(len(group) * (sum(group) / len(group) - grand) ** 2 for group in groups.values())
        out[factor] = float(ss / total_ss) if total_ss else 0.0
    return out


def pareto_front(rows: Any, cost: str, quality: str, label: str) -> list[Any]:
    """Return labels for non-dominated rows, minimizing cost and maximizing quality."""
    records = [
        row
        for row in _records(rows)
        if _num(row.get(cost)) is not None and _num(row.get(quality)) is not None
    ]
    keep: list[Any] = []
    for row in records:
        row_cost = _num(row[cost])
        row_quality = _num(row[quality])
        dominated = False
        for other in records:
            other_cost = _num(other[cost])
            other_quality = _num(other[quality])
            if (
                other_cost <= row_cost
                and other_quality >= row_quality
                and (other_cost < row_cost or other_quality > row_quality)
            ):
                dominated = True
                break
        if not dominated:
            keep.append(row[label])
    return keep


def add_costs(rows: list[dict[str, Any]], cost_model_path: str | Path) -> list[dict[str, Any]]:
    """Attach estimated sequencing cost from cost_model.csv."""
    with Path(cost_model_path).open(encoding="utf-8", newline="") as handle:
        costs = {
            row["tech"]: float(row["usd_per_gb"])
            for row in csv.DictReader(handle)
        }
    enriched = []
    for row in rows:
        item = dict(row)
        tech = str(item.get("tech") or item.get("technology") or "").lower()
        gb = (_num(item.get("total_length")) or 0.0) / 1_000_000_000
        item["estimated_cost_usd"] = gb * costs.get(tech, costs.get("nanopore", 0.0))
        enriched.append(item)
    return enriched


def generate_analysis_outputs(
    metrics_path: str | Path,
    output_dir: str | Path = "results/figures",
    cost_model_path: str | Path | None = None,
) -> list[Path]:
    """Generate extended benchmark figures from the metrics CSV."""
    rows = read_csv_records(metrics_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if any(row.get("coverage") is not None for row in rows):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("tech") or row.get("technology"))].append(row)
        fig, ax = plt.subplots(figsize=(8.8, 5.4))
        for label, items in sorted(grouped.items()):
            points = sorted(
                (
                    (int(_num(row["coverage"])), _num(row.get("genome_fraction_pct")))
                    for row in items
                    if _num(row.get("coverage")) is not None
                    and _num(row.get("genome_fraction_pct")) is not None
                ),
                key=lambda x: x[0],
            )
            if points:
                ax.plot(
                    [x for x, _ in points],
                    [y for _, y in points],
                    marker="o",
                    label=label,
                )
        ax.set_title("Coverage Saturation: Genome Fraction")
        ax.set_xlabel("Coverage (x)")
        ax.set_ylabel("Genome fraction (%)")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        path = out / "coverage_genome_fraction_curve.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    if cost_model_path and Path(cost_model_path).is_file():
        enriched = add_costs(rows, cost_model_path)
        fig, ax = plt.subplots(figsize=(8.8, 5.4))
        labels = [
            row.get("run_id") or row.get("technology") or row.get("tech")
            for row in enriched
        ]
        for row, label in zip(enriched, labels):
            row["_label"] = label
        front = set(
            pareto_front(
                enriched,
                cost="estimated_cost_usd",
                quality="genome_fraction_pct",
                label="_label",
            )
        )
        for row in enriched:
            label = row["_label"]
            ax.scatter(
                row["estimated_cost_usd"],
                _num(row.get("genome_fraction_pct")) or 0,
                s=80 if label in front else 45,
                marker="*" if label in front else "o",
                label=label if label in front else None,
            )
        ax.set_title("Quality-Cost Pareto Front")
        ax.set_xlabel("Estimated sequencing cost (USD)")
        ax.set_ylabel("Genome fraction (%)")
        ax.grid(alpha=0.25)
        if front:
            ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        path = out / "pareto_quality_cost.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "metrics",
        nargs="?",
        default="results/tables/assembly_metrics.csv",
    )
    parser.add_argument("--output-dir", default="results/figures")
    parser.add_argument("--cost-model", default="config/cost_model.csv")
    args = parser.parse_args()

    rows = read_csv_records(args.metrics)
    print(f"min_viable_coverage={min_viable_coverage(rows)}")
    print(f"variance_attribution={variance_attribution(rows)}")
    written = generate_analysis_outputs(args.metrics, args.output_dir, args.cost_model)
    for path in written:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
