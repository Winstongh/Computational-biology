#!/usr/bin/env python3
"""
simulate_illumina.py — Pure-Python paired-end Illumina read simulator.

Replaces art_illumina on platforms where that tool is unavailable (e.g. Windows).
Generates reads that match the key statistical properties of HiSeq 2500 output:
  - Fixed 150 bp read length
  - Paired-end with Gaussian insert size
  - Position-dependent quality score profile (Q30+ early, degrading toward 3' end)
  - ~0.1–0.3 % base substitution error rate rising toward read end

Usage
-----
python scripts/simulate_illumina.py \
    --reference data/reference/ecoli.fasta \
    --coverage 30 \
    --read-length 150 \
    --insert-mean 350 \
    --insert-sd 50 \
    --output-prefix data/reads/illumina_30x_
"""

import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPLEMENT = str.maketrans("ACGTacgtNn", "TGCAtgcaNn")

# HiSeq 2500-like quality score profile: mean Q-score per read position.
# Starts at Q37, dips to Q30 around position 130, Q28 at position 150.
def _hs25_mean_q(pos: int, read_len: int) -> float:
    """Return mean Phred Q-score for a given 0-based read position."""
    frac = pos / max(read_len - 1, 1)
    # Smooth quadratic decay from Q37 → Q28 across the read
    return 37.0 - 9.0 * (frac ** 1.5)


# ---------------------------------------------------------------------------
# FASTA helpers
# ---------------------------------------------------------------------------


def load_fasta_sequence(filepath: str) -> str:
    """Read the first sequence from a FASTA file into a plain string."""
    parts: list[str] = []
    with open(filepath) as fh:
        for line in fh:
            if line.startswith(">"):
                if parts:
                    break  # only the first contig
                continue
            parts.append(line.rstrip())
    return "".join(parts).upper()


def reverse_complement(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


# ---------------------------------------------------------------------------
# Error / quality simulation
# ---------------------------------------------------------------------------


def simulate_read(template: str, read_len: int, rng: np.random.Generator) -> tuple[str, str]:
    """
    Apply position-dependent substitution errors to *template* and generate
    a matching quality string.

    Returns
    -------
    (read_sequence, quality_string)
        Quality string is FASTQ Phred+33 encoded.
    """
    bases = list(template)
    qual_chars = []

    for i, base in enumerate(bases):
        mean_q = _hs25_mean_q(i, read_len)
        # Sample Q from a tight normal around the mean (stdev ~2)
        q = int(round(rng.normal(mean_q, 2.0)))
        q = max(2, min(40, q))  # clamp to realistic range

        # Convert Q to error probability and decide whether to introduce error
        p_error = 10 ** (-q / 10.0)
        if base not in "ACGT" or rng.random() < p_error:
            # Substitution: pick any base other than the current one
            alts = [b for b in "ACGT" if b != base]
            bases[i] = rng.choice(alts) if alts else base

        qual_chars.append(chr(q + 33))  # Phred+33

    return "".join(bases), "".join(qual_chars)


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------


def simulate_illumina(
    reference_path: str,
    output_prefix: str,
    coverage: int = 30,
    read_len: int = 150,
    insert_mean: int = 350,
    insert_sd: int = 50,
    seed: int = 42,
) -> None:
    """
    Simulate paired-end Illumina reads and write two FASTQ files.

    Output files:
        {output_prefix}1.fastq  — forward (R1) reads
        {output_prefix}2.fastq  — reverse (R2) reads
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)

    print(f"Loading reference: {reference_path}", flush=True)
    genome = load_fasta_sequence(reference_path)
    genome_len = len(genome)
    print(f"  Genome length: {genome_len:,} bp", flush=True)

    # Total read pairs needed for target coverage
    # coverage = (n_pairs * 2 * read_len) / genome_len
    n_pairs = math.ceil(coverage * genome_len / (2 * read_len))
    print(f"  Target coverage: {coverage}x → {n_pairs:,} read pairs", flush=True)

    out_r1 = Path(output_prefix + "1.fastq")
    out_r2 = Path(output_prefix + "2.fastq")
    out_r1.parent.mkdir(parents=True, exist_ok=True)

    progress_interval = max(1, n_pairs // 20)  # report every 5 %

    with open(out_r1, "w", buffering=1 << 20) as f1, \
         open(out_r2, "w", buffering=1 << 20) as f2:

        for i in range(n_pairs):
            if i % progress_interval == 0:
                pct = 100 * i / n_pairs
                print(f"  Progress: {pct:5.1f}% ({i:,}/{n_pairs:,} pairs)\r",
                      end="", flush=True)

            # Sample insert size from truncated normal (must fit in genome)
            insert_size = int(rng.normal(insert_mean, insert_sd))
            insert_size = max(read_len + 1, min(insert_size, genome_len - 1))

            # Choose a random start position on either strand
            max_start = genome_len - insert_size
            if max_start <= 0:
                continue
            start = int(rng.integers(0, max_start))
            strand = rng.integers(0, 2)

            fragment = genome[start : start + insert_size]
            if strand == 1:
                fragment = reverse_complement(fragment)

            # R1: first read_len bases of fragment
            # R2: last read_len bases, reverse-complemented
            tmpl_r1 = fragment[:read_len]
            tmpl_r2 = reverse_complement(fragment[-read_len:])

            seq_r1, qual_r1 = simulate_read(tmpl_r1, read_len, rng)
            seq_r2, qual_r2 = simulate_read(tmpl_r2, read_len, rng)

            read_id = f"read_{i + 1}_pos{start}_ins{insert_size}"

            f1.write(f"@{read_id}/1\n{seq_r1}\n+\n{qual_r1}\n")
            f2.write(f"@{read_id}/2\n{seq_r2}\n+\n{qual_r2}\n")

    print(f"\n  Done. Wrote {n_pairs:,} pairs to:")
    print(f"    {out_r1}")
    print(f"    {out_r2}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pure-Python paired-end Illumina read simulator (HiSeq 2500 profile)"
    )
    parser.add_argument("--reference",      required=True,  help="Input FASTA reference")
    parser.add_argument("--coverage",       type=int,   default=30,  help="Target coverage (default: 30)")
    parser.add_argument("--read-length",    type=int,   default=150, help="Read length (default: 150)")
    parser.add_argument("--insert-mean",    type=int,   default=350, help="Mean insert size (default: 350)")
    parser.add_argument("--insert-sd",      type=int,   default=50,  help="Insert size stdev (default: 50)")
    parser.add_argument("--output-prefix",  required=True,  help="Output prefix (e.g. data/reads/illumina_30x_)")
    parser.add_argument("--seed",           type=int,   default=42,  help="Random seed (default: 42)")
    args = parser.parse_args()

    simulate_illumina(
        reference_path=args.reference,
        output_prefix=args.output_prefix,
        coverage=args.coverage,
        read_len=args.read_length,
        insert_mean=args.insert_mean,
        insert_sd=args.insert_sd,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
