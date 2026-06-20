import csv
from pathlib import Path

import pytest

from scripts.parse_quast_report import parse_quast_report, row_with_run_context, write_metrics_csv


REPORT = """Assembly\tHybrid\tPacBio_HiFi\tNanopore\tIllumina
# contigs\t1\t1\t1\t128
Largest contig\t4641523\t4641654\t4641639\t327173
Total length\t4641523\t4641654\t4641639\t4575250
N50\t4641523\t4641654\t4641639\t175919
Genome fraction (%)\t99.98\t100.00\t99.99\t98.55
# mismatches per 100 kbp\t0.45\t0.02\t8.25\t0.08
# indels per 100 kbp\t0.11\t0.00\t12.50\t-
# misassemblies\t0\t0\t1\t2
"""


def test_parse_quast_report_normalizes_order_names_and_types(tmp_path: Path):
    report = tmp_path / "report.tsv"
    report.write_text(REPORT, encoding="utf-8")
    rows = parse_quast_report(report)
    assert [row["technology"] for row in rows] == [
        "Illumina",
        "Nanopore",
        "PacBio HiFi",
        "Hybrid",
    ]
    assert rows[0]["n50"] == 175919
    assert rows[0]["indels_per_100_kbp"] is None
    assert rows[2]["mismatches_per_100_kbp"] == 0.02


def test_row_with_run_context_adds_axis_columns():
    base = {"n50": 100, "contigs": 1}
    out = row_with_run_context(base, run_id="hifi_30x_hifiasm_orig_s13")
    assert out["tech"] == "hifi"
    assert out["coverage"] == 30
    assert out["assembler"] == "hifiasm"
    assert out["reference"] == "orig"
    assert out["seed"] == 13
    assert out["run_id"] == "hifi_30x_hifiasm_orig_s13"


def test_write_metrics_csv_uses_expanded_schema_when_run_id_present(tmp_path: Path):
    row = row_with_run_context(
        {"n50": 100, "contigs": 1},
        run_id="ont_r10_30x_flye_rep_v1_s17",
        busco=99.0,
    )
    output = tmp_path / "metrics.csv"
    write_metrics_csv([row], output)
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["run_id"] == "ont_r10_30x_flye_rep_v1_s17"
    assert rows[0]["busco_complete_pct"] == "99.0"


def test_parse_quast_report_requires_n50(tmp_path: Path):
    report = tmp_path / "report.tsv"
    report.write_text(REPORT.replace("N50\t", "N60\t"), encoding="utf-8")
    with pytest.raises(ValueError, match="N50"):
        parse_quast_report(report)

