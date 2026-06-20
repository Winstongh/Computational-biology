#!/usr/bin/env python3
"""Dispatch assemblers by run axes and normalize output to assembly.fasta."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts.benchmark_common import make_run_id
except ModuleNotFoundError:
    from benchmark_common import make_run_id


GENOME_SIZE = "4.6m"
RESOURCE_FIELDS = (
    "run_id",
    "tech",
    "coverage",
    "assembler",
    "reference",
    "seed",
    "ram_mb",
    "wall_sec",
)


def gfa_to_fasta(gfa_path: str | Path, fasta_path: str | Path) -> Path:
    """Convert GFA segment records to FASTA."""
    gfa = Path(gfa_path)
    fasta = Path(fasta_path)
    fasta.parent.mkdir(parents=True, exist_ok=True)
    with gfa.open(encoding="utf-8") as src, fasta.open("w", encoding="ascii") as dst:
        for line in src:
            if not line.startswith("S\t"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                dst.write(f">{parts[1]}\n{parts[2]}\n")
    if not fasta.is_file() or fasta.stat().st_size == 0:
        raise FileNotFoundError(f"No GFA segment records found in {gfa}")
    return fasta


def _which(tool: str) -> str:
    env_tool = Path(sys.executable).resolve().parent / tool
    resolved = str(env_tool) if env_tool.is_file() else shutil.which(tool)
    if not resolved:
        raise FileNotFoundError(f"Required assembler not found on PATH: {tool}")
    return resolved


def _assembler_cmd(
    tech: str,
    assembler: str,
    reads_prefix: str,
    outdir: Path,
    threads: int,
) -> tuple[list[str], str | None]:
    r1 = f"{reads_prefix}_1.fastq"
    r2 = f"{reads_prefix}_2.fastq"
    long_reads = f"{reads_prefix}.fastq"
    if assembler == "spades":
        return (
            [
                _which("spades.py"),
                "-1",
                r1,
                "-2",
                r2,
                "-o",
                str(outdir),
                "-t",
                str(threads),
                "-m",
                "8",
            ],
            None,
        )
    if assembler == "flye":
        flag = "--pacbio-hifi" if tech == "hifi" else "--nano-raw"
        return (
            [
                _which("flye"),
                flag,
                long_reads,
                "--out-dir",
                str(outdir),
                "--threads",
                str(threads),
                "--genome-size",
                GENOME_SIZE,
            ],
            None,
        )
    if assembler == "raven":
        return ([_which("raven"), "-t", str(threads), long_reads], "stdout")
    if assembler == "miniasm":
        shell_cmd = (
            f"{_which('minimap2')} -x ava-ont {long_reads} {long_reads} > {outdir}/ovl.paf && "
            f"{_which('miniasm')} -f {long_reads} {outdir}/ovl.paf > {outdir}/asm.gfa"
        )
        return (["bash", "-c", shell_cmd], None)
    if assembler == "hifiasm":
        return (
            [_which("hifiasm"), "-o", str(outdir / "asm"), "-t", str(threads), long_reads],
            None,
        )
    if assembler == "unicycler":
        return (
            [
                _which("unicycler"),
                "-1",
                r1,
                "-2",
                r2,
                "-l",
                long_reads,
                "-o",
                str(outdir),
                "-t",
                str(threads),
            ],
            None,
        )
    raise ValueError(f"Unsupported assembler: {assembler}")


def _normalize_output(assembler: str, outdir: Path, stdout: str) -> Path:
    target = outdir / "assembly.fasta"
    if assembler == "spades":
        shutil.copyfile(outdir / "contigs.fasta", target)
    elif assembler in {"flye", "unicycler"}:
        source = outdir / "assembly.fasta"
        if source != target:
            shutil.copyfile(source, target)
    elif assembler == "raven":
        target.write_text(stdout, encoding="ascii")
    elif assembler == "miniasm":
        gfa_to_fasta(outdir / "asm.gfa", target)
    elif assembler == "hifiasm":
        gfa_to_fasta(outdir / "asm.bp.p_ctg.gfa", target)
    if not target.is_file() or target.stat().st_size == 0:
        raise FileNotFoundError(f"Assembler did not produce {target}")
    return target


def _parse_elapsed(raw: str) -> float | None:
    parts = raw.strip().split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        return float(parts[0])
    except ValueError:
        return None


def parse_time_v(stderr: str) -> tuple[float | None, float | None]:
    ram_kb = None
    wall_sec = None
    ram_match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", stderr)
    if ram_match:
        ram_kb = int(ram_match.group(1))
    wall_match = re.search(r"Elapsed .*: ([\d:.]+)", stderr)
    if wall_match:
        wall_sec = _parse_elapsed(wall_match.group(1))
    return (round(ram_kb / 1024, 2) if ram_kb else None, wall_sec)


def _append_resource_log(path: str | Path, row: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    exists = output.is_file()
    with output.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESOURCE_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in RESOURCE_FIELDS})


def run_one(
    tech: str,
    coverage: int,
    assembler: str,
    reference: str,
    seed: int,
    threads: int,
    log_path: str | Path = "results/tables/resource_log.csv",
    reads_prefix: str | None = None,
    skip_existing: bool = False,
) -> str:
    """Run one assembler and return its run-id."""
    run_id = make_run_id(tech, coverage, assembler, reference, seed)
    outdir = Path("assemblies") / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    if skip_existing and (outdir / "assembly.fasta").is_file() and (outdir / "assembly.fasta").stat().st_size > 0:
        return run_id
    prefix = reads_prefix or f"data/reads/{tech}_{coverage}x"
    cmd, stdout_mode = _assembler_cmd(tech, assembler, prefix, outdir, threads)
    timed = ["/usr/bin/time", "-v", *cmd]
    env = os.environ.copy()
    env_bin = str(Path(sys.executable).resolve().parent)
    env["PATH"] = env_bin + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(timed, capture_output=True, text=True, env=env)
    (outdir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (outdir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, timed, proc.stdout, proc.stderr)
    _normalize_output(assembler, outdir, proc.stdout if stdout_mode == "stdout" else "")
    ram_mb, wall_sec = parse_time_v(proc.stderr)
    _append_resource_log(
        log_path,
        {
            "run_id": run_id,
            "tech": tech,
            "coverage": coverage,
            "assembler": assembler,
            "reference": reference,
            "seed": seed,
            "ram_mb": ram_mb,
            "wall_sec": wall_sec,
        },
    )
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tech", required=True)
    parser.add_argument("--coverage", type=int, required=True)
    parser.add_argument("--assembler", required=True)
    parser.add_argument("--reference", default="orig")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--reads-prefix")
    parser.add_argument("--log", default="results/tables/resource_log.csv")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    run_id = run_one(
        args.tech,
        args.coverage,
        args.assembler,
        args.reference,
        args.seed,
        args.threads,
        args.log,
        args.reads_prefix,
        args.skip_existing,
    )
    print(run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
