#!/usr/bin/env python3
"""
plot_read_lengths.py — Visualise read length distributions for three
sequencing technologies: Illumina, Nanopore, and PacBio HiFi.

To keep memory use bounded, a reservoir-sampling approach is applied: at most
MAX_SAMPLE read lengths are retained per dataset regardless of file size.
For Illumina (all reads are 150 bp), only the histogram is drawn without a
KDE overlay, since a KDE on a point-mass distribution is misleading.

Output
------
results/figures/read_length_distribution.png  (DPI=300, academic style)
"""

import os
import random
import sys
from pathlib import Path

# MKL's multi-threaded dispatcher crashes on this system when calling Level-3
# BLAS routines (dgemm etc.).  Sequential mode avoids thread initialization.
os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
Path(".cache/matplotlib").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(Path(".cache/matplotlib").resolve()))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(".cache").resolve()))

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — safe for headless/HPC runs
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_SAMPLE = 50_000  # max read lengths kept per dataset (reservoir sampling)

DATASETS = [
    {
        "label":     "Illumina (PE 150 bp)",
        "filepaths": [
            "data/reads/illumina_30x_1.fastq",
            "data/reads/illumina_30x_2.fastq",
        ],
        "color":     "#2196F3",   # blue
        "kde":       False,       # point-mass — KDE not meaningful
        "binwidth":  1,
    },
    {
        "label":     "ONT R9 20x (~10 kbp)",
        "filepaths": ["data/reads/ont_r9_20x.fastq"],
        "color":     "#FF9800",   # orange
        "kde":       True,
        "binwidth":  500,         # 500-bp bins for long reads
    },
    {
        "label":     "PacBio HiFi (~15 kbp)",
        "filepaths": ["data/reads/hifi_30x.fastq"],
        "color":     "#4CAF50",   # green
        "kde":       True,
        "binwidth":  500,
    },
]

OUTPUT_PATH = Path("results/figures/read_length_distribution.png")

# ---------------------------------------------------------------------------
# Streaming sampler
# ---------------------------------------------------------------------------


def reservoir_sample_lengths(filepaths: list[str], k: int) -> list[int]:
    """
    Stream one or more FASTQ files and return a reservoir sample of up to *k*
    read lengths using Vitter's Algorithm R.

    This guarantees a uniform random sample without knowing the total count
    in advance, and without loading the full file into memory.

    Parameters
    ----------
    filepaths : list[str]
        Paths to FASTQ files to sample from (concatenated logically).
    k : int
        Maximum number of lengths to retain.

    Returns
    -------
    list[int]
        Sampled read lengths (unordered).  Length is min(total_reads, k).
    """
    reservoir: list[int] = []
    n = 0  # total records seen so far

    for fp in filepaths:
        path = Path(fp)
        if not path.exists():
            print(f"  WARNING: File not found, skipping: {fp}", file=sys.stderr)
            continue

        with open(path, "r", buffering=1 << 20) as fh:
            while True:
                header   = fh.readline()
                if not header:
                    break
                sequence = fh.readline().rstrip("\n")
                fh.readline()   # '+' separator
                fh.readline()   # quality scores

                length = len(sequence)
                n += 1

                if n <= k:
                    # Fill the reservoir for the first k items
                    reservoir.append(length)
                else:
                    # Replace a random element with decreasing probability
                    j = random.randint(1, n)
                    if j <= k:
                        reservoir[j - 1] = length

    return reservoir


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------


def plot_distribution(
    ax: plt.Axes,
    lengths: list[int],
    label: str,
    color: str,
    kde: bool,
    binwidth: int,
) -> None:
    """
    Draw a histogram (with optional KDE) of *lengths* on *ax*.

    For Illumina data (point-mass at 150 bp, kde=False), the histogram is
    drawn with a tight x-axis window to make the bar visible and annotated
    with the fixed read length.

    Parameters
    ----------
    ax       : Axes to draw on.
    lengths  : Sampled read lengths.
    label    : Dataset label for the title.
    color    : Bar / line colour (hex string).
    kde      : Whether to overlay a kernel density estimate.
    binwidth : Histogram bin width in bp.
    """
    if not lengths:
        ax.set_title(f"{label}\n(no data)", fontsize=11)
        return

    if len(set(lengths)) == 1:
        fixed_len = lengths[0]
        bins = [fixed_len - 0.5, fixed_len + 0.5]
    else:
        lower = max(0, min(lengths) - binwidth)
        upper = max(lengths) + binwidth
        bins = list(range(lower, upper + binwidth, binwidth))

    ax.hist(
        lengths,
        bins=bins,
        color=color,
        alpha=0.75,
        edgecolor="white",
        linewidth=0.4,
    )

    ax.set_title(label, fontsize=11, fontweight="bold", pad=8)
    ax.set_xlabel("Read Length (bp)", fontsize=10)
    ax.set_ylabel("Read Count", fontsize=10)

    # Thousands separator on both axes for readability
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"{int(x):,}"
    ))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"{int(x):,}"
    ))

    # For Illumina point-mass, zoom x-axis to ±20 bp around the fixed length
    if not kde and len(set(lengths)) == 1:
        fixed_len = lengths[0]
        ax.set_xlim(fixed_len - 20, fixed_len + 20)
        ax.annotate(
            f"All reads = {fixed_len} bp",
            xy=(fixed_len, ax.get_ylim()[1] * 0.8),
            ha="center",
            fontsize=9,
            color="black",
        )

    # Descriptive stats in the subplot
    mean_l = sum(lengths) / len(lengths)
    ax.axvline(
        mean_l,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"Mean = {mean_l:,.0f} bp",
    )
    ax.legend(fontsize=8, framealpha=0.8)

    ax.tick_params(labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linewidth=0.8)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Sample lengths, build the 3-panel figure, and save to disk."""
    if not Path("data/reference/ecoli.fasta").exists():
        print(
            "ERROR: Run this script from the project root directory.\n"
            "    cd /path/to/genome_project && python scripts/plot_read_lengths.py",
            file=sys.stderr,
        )
        return 1

    plt.rcParams.update(
        {
            "axes.grid": True,
            "grid.alpha": 0.25,
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    fig, axes = plt.subplots(
        nrows=1,
        ncols=3,
        figsize=(15, 5.5),
    )
    fig.subplots_adjust(top=0.85, hspace=0.35, wspace=0.35)

    fig.suptitle(
        "Read Length Distributions — 30x Simulated Sequencing\n"
        r"$\it{Escherichia\ coli}$ K-12 MG1655",
        fontsize=13,
        fontweight="bold",
    )

    any_data = False

    for ax, cfg in zip(axes, DATASETS):
        label     = cfg["label"]
        filepaths = cfg["filepaths"]
        color     = cfg["color"]
        kde       = cfg["kde"]
        binwidth  = cfg["binwidth"]

        print(f"Sampling lengths for: {label} …", flush=True)
        lengths = reservoir_sample_lengths(filepaths, MAX_SAMPLE)

        if lengths:
            any_data = True
            print(
                f"  {len(lengths):,} lengths sampled  |  "
                f"mean = {sum(lengths)/len(lengths):,.0f} bp  |  "
                f"max = {max(lengths):,} bp"
            )
        else:
            print(f"  No reads found — panel will be blank.")

        plot_distribution(ax, lengths, label, color, kde, binwidth)

    if not any_data:
        print(
            "WARNING: No FASTQ files found. "
            "Please run the simulation commands before plotting.",
            file=sys.stderr,
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"\nFigure saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
