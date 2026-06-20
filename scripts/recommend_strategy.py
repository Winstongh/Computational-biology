#!/usr/bin/env python3
"""Recommend a sequencing strategy from benchmark metrics and a cost model."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def load_costs(path: str | Path) -> dict[str, float]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return {row["tech"]: float(row["usd_per_gb"]) for row in csv.DictReader(handle)}


def recommend(
    metrics_path: str | Path,
    cost_model_path: str | Path,
    genome_mbp: float,
    budget_usd: float,
    min_genome_fraction: float = 99.0,
    max_contigs: int | None = 1,
) -> dict[str, Any]:
    costs = load_costs(cost_model_path)
    genome_gb = genome_mbp / 1000
    candidates = []
    with Path(metrics_path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            tech = (row.get("tech") or row.get("technology") or "").lower()
            coverage = _num(row.get("coverage")) or 30.0
            cost = costs.get(tech, costs.get("nanopore", 10.0)) * genome_gb * coverage
            gf = _num(row.get("genome_fraction_pct")) or 0.0
            n50 = _num(row.get("n50")) or 0.0
            contigs = _num(row.get("contigs"))
            passes_contigs = max_contigs is None or contigs is None or contigs <= max_contigs
            if cost <= budget_usd and gf >= min_genome_fraction and passes_contigs:
                item = dict(row)
                item["estimated_cost_usd"] = round(cost, 2)
                item["_score"] = (-cost, gf, n50)
                candidates.append(item)
    if not candidates:
        raise ValueError("No strategy satisfies the budget and quality constraints")
    return max(candidates, key=lambda row: row["_score"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", default="results/tables/assembly_metrics.csv")
    parser.add_argument("--cost-model", default="config/cost_model.csv")
    parser.add_argument("--genome-mbp", type=float, default=4.6)
    parser.add_argument("--budget-usd", type=float, default=10.0)
    parser.add_argument("--min-genome-fraction", type=float, default=99.0)
    parser.add_argument("--max-contigs", type=int, default=1)
    parser.add_argument("--output", default="results/tables/final_recommendation.csv")
    args = parser.parse_args()
    row = recommend(
        args.metrics,
        args.cost_model,
        args.genome_mbp,
        args.budget_usd,
        args.min_genome_fraction,
        args.max_contigs,
    )
    label = row.get("run_id") or row.get("technology") or row.get("tech")
    print(f"recommendation={label}")
    print(f"estimated_cost_usd={row['estimated_cost_usd']}")
    print(f"genome_fraction_pct={row.get('genome_fraction_pct')}")
    print(f"n50={row.get('n50')}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    public_row = {key: value for key, value in row.items() if not key.startswith("_")}
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(public_row))
        writer.writeheader()
        writer.writerow(public_row)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
