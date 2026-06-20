#!/usr/bin/env python3
"""Generate the four core Part C figures from assembly_metrics.csv."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-part-c")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/part-c-cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


FIGURE_FILENAMES = (
    "n50_comparison.png",
    "contig_count_comparison.png",
    "genome_fraction_comparison.png",
    "error_comparison.png",
)

TECH_COLORS = ("#2878B5", "#D9534F", "#3A923A", "#7A5195")


def _read_metrics(path: str | Path) -> list[dict[str, Any]]:
    numeric_fields = {
        "n50",
        "contigs",
        "largest_contig",
        "total_length",
        "genome_fraction_pct",
        "mismatches_per_100_kbp",
        "indels_per_100_kbp",
        "misassemblies",
    }
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError(f"{path}: metrics CSV has no data rows")

    parsed: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = dict(row)
        item["technology"] = (
            row.get("technology")
            or row.get("tech")
            or row.get("run_id")
            or "unknown"
        )
        for field in numeric_fields:
            value = (row.get(field) or "").strip()
            item[field] = None if not value else float(value)
        parsed.append(item)
    return parsed


def _finish_bar_plot(
    fig: plt.Figure,
    ax: plt.Axes,
    output_path: Path,
    integer_labels: bool = False,
    annotations: list[list[str]] | None = None,
) -> None:
    for index, container in enumerate(ax.containers):
        if annotations is not None:
            labels = annotations[index]
        else:
            labels = []
            for bar in container:
                height = bar.get_height()
                if height != height:
                    labels.append("NA")
                elif integer_labels:
                    labels.append(f"{height:,.0f}")
                else:
                    labels.append(f"{height:,.2f}")
        ax.bar_label(container, labels=labels, padding=3, fontsize=8)

    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.margins(y=0.16)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def generate_plots(
    metrics_path: str | Path,
    output_dir: str | Path,
) -> list[str]:
    """Write all required Part C figures and return their filenames."""
    rows = _read_metrics(metrics_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    labels = [str(row["technology"]) for row in rows]
    colors = [TECH_COLORS[index % len(TECH_COLORS)] for index in range(len(rows))]

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    n50_mbp = [(row["n50"] or 0) / 1_000_000 for row in rows]
    ax.bar(labels, n50_mbp, color=colors, width=0.68)
    ax.set_title("Assembly N50 Comparison", fontsize=14, weight="bold")
    ax.set_ylabel("N50 (Mbp)")
    _finish_bar_plot(
        fig,
        ax,
        destination / FIGURE_FILENAMES[0],
        annotations=[
            [
                "NA" if row["n50"] is None else f"{row['n50']:,.0f} bp"
                for row in rows
            ]
        ],
    )

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    contigs = [row["contigs"] or 0 for row in rows]
    ax.bar(labels, contigs, color=colors, width=0.68)
    ax.set_title("Assembly Fragmentation", fontsize=14, weight="bold")
    ax.set_ylabel("Number of contigs (lower is better)")
    _finish_bar_plot(
        fig,
        ax,
        destination / FIGURE_FILENAMES[1],
        integer_labels=True,
    )

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    genome_fraction = [row["genome_fraction_pct"] or 0 for row in rows]
    ax.bar(labels, genome_fraction, color=colors, width=0.68)
    ax.set_title("Reference Genome Recovered", fontsize=14, weight="bold")
    ax.set_ylabel("Genome fraction (%)")
    lower_bound = max(0, min(genome_fraction) - 2)
    ax.set_ylim(lower_bound, 100.5)
    _finish_bar_plot(
        fig,
        ax,
        destination / FIGURE_FILENAMES[2],
        annotations=[[f"{value:.3f}" for value in genome_fraction]],
    )

    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    positions = list(range(len(rows)))
    width = 0.36
    mismatches = [
        float("nan") if row["mismatches_per_100_kbp"] is None
        else row["mismatches_per_100_kbp"]
        for row in rows
    ]
    indels = [
        float("nan") if row["indels_per_100_kbp"] is None
        else row["indels_per_100_kbp"]
        for row in rows
    ]
    ax.bar(
        [position - width / 2 for position in positions],
        mismatches,
        width,
        color="#C44E52",
        label="Mismatches",
    )
    ax.bar(
        [position + width / 2 for position in positions],
        indels,
        width,
        color="#4C72B0",
        label="Indels",
    )
    ax.set_xticks(positions, labels)
    ax.set_title("Assembly Base-level Errors", fontsize=14, weight="bold")
    ax.set_ylabel("Errors per 100 kbp (lower is better)")
    ax.legend(frameon=False)
    _finish_bar_plot(fig, ax, destination / FIGURE_FILENAMES[3])

    return list(FIGURE_FILENAMES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "metrics",
        nargs="?",
        type=Path,
        default=Path("results/tables/assembly_metrics.csv"),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("results/figures"),
    )
    args = parser.parse_args()

    generated = generate_plots(args.metrics, args.output_dir)
    for filename in generated:
        print(f"Wrote {args.output_dir / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
