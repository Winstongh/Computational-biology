#!/usr/bin/env python3
"""Run QUAST, parse its report, generate figures, and write conclusions."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

try:
    from scripts.parse_quast_report import (
        parse_quast_report,
        row_with_run_context,
        write_metrics_csv,
    )
    from scripts.plot_quast_metrics import generate_plots
    from scripts.prepare_part_c_inputs import discover_assembly_paths
    from scripts.summarize_assembly_results import build_summary
except ModuleNotFoundError:
    from parse_quast_report import parse_quast_report, row_with_run_context, write_metrics_csv
    from plot_quast_metrics import generate_plots
    from prepare_part_c_inputs import discover_assembly_paths
    from summarize_assembly_results import build_summary


def _resolve_quast(requested: str | None) -> str:
    if requested:
        candidate = Path(requested)
        if candidate.is_file():
            return str(candidate)
        resolved = shutil.which(requested)
        if resolved:
            return resolved
        raise FileNotFoundError(f"QUAST executable not found: {requested}")

    for command in ("quast.py", "quast"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    raise FileNotFoundError(
        "QUAST is not installed. Create the environment with environment-part-c.yml."
    )


def run_pipeline(
    project_root: str | Path,
    quast_command: str | None = None,
    quast_output: str | Path = "quast_reports/all_assemblies",
    threads: int = 4,
    include_hybrid: bool = True,
    skip_quast: bool = False,
) -> Path:
    root = Path(project_root).resolve()
    output_dir = root / quast_output
    report_path = output_dir / "report.tsv"
    assemblies = discover_assembly_paths(root, include_hybrid=include_hybrid)

    if not skip_quast:
        quast = _resolve_quast(quast_command)
        reference = root / "data/reference/ecoli.fasta"
        if not reference.is_file():
            raise FileNotFoundError(f"Reference genome not found: {reference}")

        command = [
            quast,
            *[str(path) for path in assemblies.values()],
            "-r",
            str(reference),
            "-o",
            str(output_dir),
            "-t",
            str(threads),
            "--labels",
            ",".join(name.replace(" ", "_") for name in assemblies),
        ]
        print("Running:", " ".join(command), flush=True)
        subprocess.run(command, cwd=root, check=True)
    elif not report_path.is_file():
        raise FileNotFoundError(f"Cannot skip QUAST; report is missing: {report_path}")

    rows = parse_quast_report(report_path, assemblies.keys())
    sample_context = {
        "Illumina": ("illumina_30x_spades_orig_s13", "illumina"),
        "Nanopore": ("ont_r10_30x_flye_orig_s13", "ont_r10"),
        "PacBio HiFi": ("hifi_30x_flye_orig_s13", "hifi"),
        "Hybrid": ("hybrid_30x_unicycler_orig_s13", "hybrid"),
    }
    rows = [
        row_with_run_context(
            {key: value for key, value in row.items() if key != "technology"},
            run_id=sample_context[row["technology"]][0],
            generation=sample_context[row["technology"]][1],
        )
        if row.get("technology") in sample_context
        else row
        for row in rows
    ]
    metrics_path = root / "results/tables/assembly_metrics.csv"
    write_metrics_csv(rows, metrics_path)

    figure_dir = root / "results/figures"
    generate_plots(metrics_path, figure_dir)

    summary_path = root / "results/tables/part_c_summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(build_summary(rows), encoding="utf-8")

    print(f"Metrics: {metrics_path}")
    print(f"Figures: {figure_dir}")
    print(f"Summary: {summary_path}")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--quast")
    parser.add_argument(
        "--quast-output",
        default="quast_reports/all_assemblies",
    )
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--without-hybrid", action="store_true")
    parser.add_argument("--skip-quast", action="store_true")
    args = parser.parse_args()

    run_pipeline(
        project_root=args.project_root,
        quast_command=args.quast,
        quast_output=args.quast_output,
        threads=args.threads,
        include_hybrid=not args.without_hybrid,
        skip_quast=args.skip_quast,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
