#!/usr/bin/env python3
"""Collect assembly GFA files and optionally render them with Bandage."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


GFA_CANDIDATES = (
    "assembly_graph.gfa",
    "assembly.gfa",
    "asm.gfa",
    "asm.bp.p_ctg.gfa",
)


def find_graph(assembly_dir: str | Path) -> Path | None:
    root = Path(assembly_dir)
    for candidate in GFA_CANDIDATES:
        path = root / candidate
        if path.is_file():
            return path
    return None


def export_graph(
    assembly_dir: str | Path,
    output_dir: str | Path = "results/figures",
    render: bool = True,
) -> Path | None:
    """Copy a GFA graph and render a PNG if Bandage is available."""
    graph = find_graph(assembly_dir)
    if graph is None:
        return None
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    label = Path(assembly_dir).name
    copied = out / f"graph_{label}.gfa"
    shutil.copyfile(graph, copied)
    if render:
        bandage = shutil.which("Bandage") or shutil.which("bandage")
        if bandage:
            subprocess.run(
                [bandage, "image", str(copied), str(out / f"graph_{label}.png")],
                check=True,
            )
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly_dirs", nargs="+")
    parser.add_argument("--output-dir", default="results/figures")
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()

    for assembly_dir in args.assembly_dirs:
        path = export_graph(assembly_dir, args.output_dir, render=not args.no_render)
        if path:
            print(path)
        else:
            print(f"No graph found: {assembly_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

