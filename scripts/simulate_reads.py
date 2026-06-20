#!/usr/bin/env python3
"""Drive ART or Badread read simulation from config/matrix.yaml."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - environment message
    raise SystemExit("PyYAML is required. Install environment-bench.yml first.") from exc


def _require_tool(tool: str) -> str:
    env_tool = Path(sys.executable).resolve().parent / tool
    resolved = str(env_tool) if env_tool.is_file() else shutil.which(tool)
    if not resolved:
        raise FileNotFoundError(f"Required simulator not found on PATH: {tool}")
    return resolved


def _resolve_tool(tool: str, dry_run: bool) -> str:
    env_tool = Path(sys.executable).resolve().parent / tool
    if env_tool.is_file():
        return str(env_tool)
    return (shutil.which(tool) or tool) if dry_run else _require_tool(tool)


def _nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _expected_outputs(tech_cfg: dict, out_prefix: str) -> list[Path]:
    if tech_cfg["kind"] == "short":
        return [Path(f"{out_prefix}_{read_no}.fastq") for read_no in (1, 2)]
    return [Path(f"{out_prefix}.fastq")]


def simulate_one(
    tech: str,
    tech_cfg: dict,
    ref_path: str,
    coverage: int,
    out_prefix: str,
    seed: int,
    dry_run: bool = False,
    skip_existing: bool = False,
    quiet: bool = False,
) -> list[str]:
    """Return and optionally run the simulator command for one tech/coverage."""
    out = Path(out_prefix)
    out.parent.mkdir(parents=True, exist_ok=True)
    expected_outputs = _expected_outputs(tech_cfg, out_prefix)
    if skip_existing and all(_nonempty(path) for path in expected_outputs):
        return ["#", "SKIP", out_prefix]

    if tech_cfg["kind"] == "short":
        tool = _resolve_tool("art_illumina", dry_run)
        cmd = [
            tool,
            "-ss",
            "HS25",
            "-i",
            ref_path,
            "-p",
            "-l",
            "150",
            "-f",
            str(coverage),
            "-m",
            "350",
            "-s",
            "50",
            "-rs",
            str(seed),
            "-o",
            out_prefix,
        ]
        if not dry_run:
            run_kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL} if quiet else {}
            subprocess.run(cmd, check=True, **run_kwargs)
            for read_no in (1, 2):
                art_path = Path(f"{out_prefix}{read_no}.fq")
                normalized_path = Path(f"{out_prefix}_{read_no}.fastq")
                if art_path.exists():
                    art_path.replace(normalized_path)
        return cmd

    tool = _resolve_tool("badread", dry_run)
    cmd = [
        tool,
        "simulate",
        "--reference",
        ref_path,
        "--quantity",
        f"{coverage}x",
        "--seed",
        str(seed),
    ]
    if tech_cfg["generation"] == "hifi":
        cmd += [
            "--length",
            "15000,3000",
            "--identity",
            tech_cfg["identity"],
            "--error_model",
            "random",
            "--qscore_model",
            "random",
        ]
    else:
        cmd += [
            "--length",
            "10000,5000",
            "--identity",
            tech_cfg["identity"],
        ]

    if not dry_run:
        output_path = Path(f"{out_prefix}.fastq")
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            stderr = subprocess.DEVNULL if quiet else None
            subprocess.run(cmd, stdout=handle, stderr=stderr, check=True)
        tmp_path.replace(output_path)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/matrix.yaml")
    parser.add_argument("--seeds", default="config/seeds.yaml")
    parser.add_argument("--only-tech")
    parser.add_argument("--only-coverage", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Suppress simulator progress output")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    seeds_cfg = yaml.safe_load(Path(args.seeds).read_text(encoding="utf-8"))
    seed = int(seeds_cfg["default_seed"])
    ref = cfg["reference"]["orig"]

    for tech, tech_cfg in cfg["technologies"].items():
        if args.only_tech and tech != args.only_tech:
            continue
        for coverage in cfg["coverages"]:
            if args.only_coverage and coverage != args.only_coverage:
                continue
            out_prefix = f"data/reads/{tech}_{coverage}x"
            cmd = simulate_one(
                tech,
                tech_cfg,
                ref,
                int(coverage),
                out_prefix,
                seed,
                dry_run=args.dry_run,
                skip_existing=args.skip_existing,
                quiet=args.quiet,
            )
            print(" ".join(cmd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
