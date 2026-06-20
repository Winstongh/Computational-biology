#!/usr/bin/env python3
"""Answer the Part C acceptance questions from the metrics table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


NUMERIC_FIELDS = {
    "n50",
    "contigs",
    "largest_contig",
    "total_length",
    "genome_fraction_pct",
    "mismatches_per_100_kbp",
    "indels_per_100_kbp",
    "misassemblies",
}


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _join_names(rows: list[dict[str, Any]]) -> str:
    return "、".join(str(_row_name(row)) for row in rows)


def _row_name(row: dict[str, Any]) -> str:
    return str(row.get("run_id") or row.get("technology") or row.get("tech") or "unknown")


def _is_hybrid(row: dict[str, Any]) -> bool:
    name = _row_name(row).lower()
    tech = str(row.get("tech") or row.get("technology") or "").lower()
    return name == "hybrid" or tech == "hybrid"


def build_summary(rows: list[dict[str, Any]]) -> str:
    """Build a Chinese summary that directly answers the four project questions."""
    if not rows:
        raise ValueError("Cannot summarize an empty metrics table")

    valid_n50 = [row for row in rows if _as_number(row.get("n50")) is not None]
    best_n50_value = max(_as_number(row["n50"]) for row in valid_n50)
    best_n50 = [
        row for row in valid_n50 if _as_number(row["n50"]) == best_n50_value
    ]
    n50_wording = "并列最高" if len(best_n50) > 1 else "最高"

    valid_contigs = [
        row for row in rows if _as_number(row.get("contigs")) is not None
    ]
    most_contigs_value = max(_as_number(row["contigs"]) for row in valid_contigs)
    most_fragmented = [
        row
        for row in valid_contigs
        if _as_number(row["contigs"]) == most_contigs_value
    ]

    error_rows: list[tuple[dict[str, Any], float]] = []
    missing_error_names: list[str] = []
    for row in rows:
        mismatches = _as_number(row.get("mismatches_per_100_kbp"))
        indels = _as_number(row.get("indels_per_100_kbp"))
        if mismatches is None or indels is None:
            missing_error_names.append(_row_name(row))
            continue
        error_rows.append((row, mismatches + indels))

    if error_rows:
        worst_error_value = max(value for _, value in error_rows)
        worst_error_rows = [
            row for row, value in error_rows if value == worst_error_value
        ]
        max_mismatch = max(
            _as_number(row["mismatches_per_100_kbp"]) for row, _ in error_rows
        )
        max_indel = max(
            _as_number(row["indels_per_100_kbp"]) for row, _ in error_rows
        )
        worst_mismatch_rows = [
            row
            for row, _ in error_rows
            if _as_number(row["mismatches_per_100_kbp"]) == max_mismatch
        ]
        worst_indel_rows = [
            row
            for row, _ in error_rows
            if _as_number(row["indels_per_100_kbp"]) == max_indel
        ]
        error_line = (
            f"3. 准确性：{_join_names(worst_error_rows)} 的错误最多，"
            f"mismatches + indels 为 {worst_error_value:.2f}/100 kbp；"
            f"{_join_names(worst_mismatch_rows)} 的 mismatch 最高，"
            f"{_join_names(worst_indel_rows)} 的 indel 最高。"
        )
    else:
        error_line = "3. 准确性：没有完整的 mismatch/indel 数据，无法判断错误最多的组装。"

    missing_line = ""
    if missing_error_names:
        unique_missing = list(dict.fromkeys(missing_error_names))
        missing_line = (
            "\n   注意：" + "、".join(unique_missing)
            + " 的错误指标缺失，未按 0 处理，也未参与错误率排名。"
        )

    hybrids = [row for row in rows if _is_hybrid(row)]
    singles = [row for row in rows if not _is_hybrid(row)]
    if not hybrids:
        hybrid_line = "4. Hybrid：未提供 Hybrid 组装，无法与单一 reads 比较。"
    else:
        hybrid = max(
            hybrids,
            key=lambda row: (
                _as_number(row.get("n50")) or 0,
                -(_as_number(row.get("contigs")) or float("inf")),
            ),
        )
        hybrid_n50 = _as_number(hybrid.get("n50"))
        hybrid_contigs = _as_number(hybrid.get("contigs"))
        best_single_n50 = max(
            _as_number(row.get("n50"))
            for row in singles
            if _as_number(row.get("n50")) is not None
        )
        best_single_contigs = min(
            _as_number(row.get("contigs"))
            for row in singles
            if _as_number(row.get("contigs")) is not None
        )
        better_n50 = hybrid_n50 is not None and hybrid_n50 > best_single_n50
        fewer_contigs = (
            hybrid_contigs is not None and hybrid_contigs < best_single_contigs
        )
        if better_n50 and fewer_contigs:
            verdict = "是，Hybrid 在 N50 和 contig 数量上优于所有单一 reads"
        elif better_n50 or fewer_contigs:
            verdict = "部分优于，但没有同时改善 N50 和 contig 数量"
        else:
            verdict = (
                "否，Hybrid 的 contig 数量只与最佳单一 reads 并列，"
                "且 N50 未超过 PacBio HiFi"
            )
        hybrid_line = f"4. Hybrid 是否比单一 reads 更好：{verdict}。"

    return (
        "# Part C 组装质量初步结论\n\n"
        f"1. N50：{_join_names(best_n50)} 的 N50 {n50_wording}"
        f"（{best_n50_value:,.0f} bp）。\n"
        f"2. 连续性：{_join_names(most_fragmented)} 拼得最碎"
        f"（{most_contigs_value:,.0f} 个 contigs）。\n"
        f"{error_line}{missing_line}\n"
        f"{hybrid_line}\n"
    )


def read_metrics_csv(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in NUMERIC_FIELDS:
            row[field] = _as_number(row.get(field))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "metrics",
        nargs="?",
        type=Path,
        default=Path("results/tables/assembly_metrics.csv"),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results/tables/part_c_summary.md"),
    )
    args = parser.parse_args()

    summary = build_summary(read_metrics_csv(args.metrics))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
