import csv
from pathlib import Path

from scripts.recommend_strategy import recommend


def test_recommend_selects_best_affordable_strategy(tmp_path: Path):
    metrics = tmp_path / "metrics.csv"
    with metrics.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["run_id", "tech", "coverage", "genome_fraction_pct", "n50"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_id": "cheap",
                "tech": "ont_r10",
                "coverage": 10,
                "genome_fraction_pct": 99.1,
                "n50": 1000,
            }
        )
        writer.writerow(
            {
                "run_id": "expensive",
                "tech": "hifi",
                "coverage": 50,
                "genome_fraction_pct": 100,
                "n50": 2000,
            }
        )
    costs = tmp_path / "cost.csv"
    costs.write_text("tech,usd_per_gb\nont_r10,10\nhifi,100\nnanopore,10\n", encoding="utf-8")
    row = recommend(metrics, costs, genome_mbp=4.6, budget_usd=1.0)
    assert row["run_id"] == "cheap"

