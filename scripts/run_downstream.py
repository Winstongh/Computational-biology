#!/usr/bin/env python3
"""Run downstream utility checks: Prokka gene count and Clair3 wrapper."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
from pathlib import Path


DOWNSTREAM_FIELDS = (
    "run_id",
    "prokka_cds",
    "clair3_vcf",
    "notes",
)


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"Required downstream tool not found: {name}")
    return resolved


def run_prokka(assembly: str, out_dir: str | Path, prefix: str = "asm") -> Path:
    out = Path(out_dir)
    subprocess.run(
        [_tool("prokka"), "--outdir", str(out), "--prefix", prefix, "--force", assembly],
        check=True,
    )
    return out / f"{prefix}.gff"


def count_cds(gff_path: str | Path) -> int:
    count = 0
    with Path(gff_path).open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) > 2 and parts[2] == "CDS":
                count += 1
    return count


def run_clair3(command: str) -> Path:
    subprocess.run(["bash", "-lc", command], check=True)
    match = next(Path(".").glob("**/merge_output.vcf.gz"), None)
    if match is None:
        raise FileNotFoundError("Clair3 output merge_output.vcf.gz was not found")
    return match


def append_downstream_log(path: str | Path, row: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    exists = output.is_file()
    with output.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DOWNSTREAM_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in DOWNSTREAM_FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--assembly", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--clair3-command")
    parser.add_argument("--log", default="results/tables/downstream_metrics.csv")
    args = parser.parse_args()

    gff = run_prokka(args.assembly, args.out_dir)
    vcf = run_clair3(args.clair3_command) if args.clair3_command else None
    row = {
        "run_id": args.run_id,
        "prokka_cds": count_cds(gff),
        "clair3_vcf": vcf,
        "notes": "",
    }
    append_downstream_log(args.log, row)
    print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

