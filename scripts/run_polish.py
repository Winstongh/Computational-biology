#!/usr/bin/env python3
"""Polish ONT assemblies with Racon and Medaka, logging wall time."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import time
from pathlib import Path


POLISH_FIELDS = (
    "run_id",
    "method",
    "rounds",
    "input_assembly",
    "output_assembly",
    "wall_sec",
)


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"Required polishing tool not found: {name}")
    return resolved


def racon_round(assembly: str, reads: str, out_dir: str | Path) -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paf = out / "ovl.paf"
    polished = out / "racon.fasta"
    with paf.open("w", encoding="utf-8") as handle:
        subprocess.run(
            [_tool("minimap2"), "-x", "map-ont", assembly, reads],
            stdout=handle,
            check=True,
        )
    with polished.open("w", encoding="ascii") as handle:
        subprocess.run([_tool("racon"), reads, str(paf), assembly], stdout=handle, check=True)
    return str(polished)


def medaka_round(
    assembly: str,
    reads: str,
    out_dir: str | Path,
    model: str = "r1041_e82_400bps_sup_v4.2.0",
    threads: int = 4,
) -> tuple[str, float]:
    out = Path(out_dir)
    t0 = time.time()
    subprocess.run(
        [
            _tool("medaka_consensus"),
            "-i",
            reads,
            "-d",
            assembly,
            "-o",
            str(out),
            "-m",
            model,
            "-t",
            str(threads),
        ],
        check=True,
    )
    return str(out / "consensus.fasta"), time.time() - t0


def append_polish_log(path: str | Path, row: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    exists = output.is_file()
    with output.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=POLISH_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in POLISH_FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--assembly", required=True)
    parser.add_argument("--reads", required=True)
    parser.add_argument("--method", choices=["racon", "medaka"], required=True)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--out-dir", default="polished")
    parser.add_argument("--log", default="results/tables/polish_metrics.csv")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    current = args.assembly
    total = 0.0
    for round_index in range(1, args.rounds + 1):
        round_dir = Path(args.out_dir) / f"{args.method}_r{round_index}"
        t0 = time.time()
        if args.method == "racon":
            current = racon_round(current, args.reads, round_dir)
            total += time.time() - t0
        else:
            current, elapsed = medaka_round(current, args.reads, round_dir, threads=args.threads)
            total += elapsed
    append_polish_log(
        args.log,
        {
            "run_id": args.run_id,
            "method": args.method,
            "rounds": args.rounds,
            "input_assembly": args.assembly,
            "output_assembly": current,
            "wall_sec": round(total, 2),
        },
    )
    print(current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

