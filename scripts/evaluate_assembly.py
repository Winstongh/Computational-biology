#!/usr/bin/env python3
"""Evaluate one assembly with QUAST plus optional BUSCO and Merqury metrics."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.parse_quast_report import parse_quast_report, row_with_run_context
except ModuleNotFoundError:
    from parse_quast_report import parse_quast_report, row_with_run_context


def _tool(name: str) -> str:
    env_tool = Path(sys.executable).resolve().parent / name
    resolved = str(env_tool) if env_tool.is_file() else shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"Required evaluation tool not found: {name}")
    return resolved


def run_quast(assembly: str, reference: str, out_dir: str, threads: int = 4) -> Path:
    out = Path(out_dir)
    cache_dir = Path(".cache").resolve()
    (cache_dir / "matplotlib").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MPLCONFIGDIR"] = str(cache_dir / "matplotlib")
    env["XDG_CACHE_HOME"] = str(cache_dir)
    subprocess.run(
        [_tool("quast.py"), assembly, "-r", reference, "-o", str(out), "-t", str(threads)],
        check=True,
        env=env,
    )
    return out / "report.tsv"


def run_busco(assembly: str, out_dir: str, lineage: str = "bacteria_odb10") -> Path:
    out = Path(out_dir)
    subprocess.run(
        [
            _tool("busco"),
            "-i",
            assembly,
            "-l",
            lineage,
            "-m",
            "genome",
            "-o",
            "busco",
            "--out_path",
            str(out),
            "-f",
        ],
        check=True,
    )
    matches = sorted(out.glob("busco/short_summary*.txt"))
    if not matches:
        matches = sorted(out.glob("short_summary*.txt"))
    if not matches:
        raise FileNotFoundError(f"BUSCO summary not found under {out}")
    return matches[0]


def parse_busco_complete(summary_path: str | Path) -> float | None:
    text = Path(summary_path).read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"C:([0-9.]+)%", text)
    return float(match.group(1)) if match else None


def parse_merqury_qv(path: str | Path) -> float | None:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    numbers = [float(value) for value in re.findall(r"\bQV\b[^0-9]*([0-9.]+)", text)]
    if numbers:
        return numbers[-1]
    for line in text.splitlines():
        parts = line.split()
        for part in reversed(parts):
            try:
                value = float(part)
            except ValueError:
                continue
            if 0 <= value <= 100:
                return value
    return None


def append_metrics_row(row: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow({key: "" if value is None else value for key, value in row.items()})
    return path


def evaluate_one(
    run_id: str,
    assembly: str,
    reference: str,
    out_dir: str,
    threads: int = 4,
    skip_busco: bool = False,
    busco_lineage: str = "bacteria_odb10",
    merqury_qv_file: str | None = None,
) -> dict[str, Any]:
    root = Path(out_dir)
    quast_report = run_quast(assembly, reference, str(root / "quast"), threads)
    metric_row = parse_quast_report(quast_report, expected_assemblies=None)[0]
    metric_row.pop("technology", None)

    busco = None
    if not skip_busco:
        busco = parse_busco_complete(run_busco(assembly, str(root), busco_lineage))
    merqury = parse_merqury_qv(merqury_qv_file) if merqury_qv_file else None
    return row_with_run_context(metric_row, run_id=run_id, busco=busco, merqury=merqury)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--assembly", required=True)
    parser.add_argument("--reference", default="data/reference/ecoli.fasta")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--skip-busco", action="store_true")
    parser.add_argument("--busco-lineage", default="bacteria_odb10")
    parser.add_argument("--merqury-qv-file")
    parser.add_argument("--append-csv", default="results/tables/assembly_metrics.csv")
    args = parser.parse_args()

    row = evaluate_one(
        args.run_id,
        args.assembly,
        args.reference,
        args.out_dir,
        args.threads,
        args.skip_busco,
        args.busco_lineage,
        args.merqury_qv_file,
    )
    append_metrics_row(row, args.append_csv)
    print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
