from pathlib import Path

from scripts.evaluate_assembly import parse_busco_complete, parse_merqury_qv


def test_parse_busco_complete_reads_short_summary(tmp_path: Path):
    summary = tmp_path / "short_summary.txt"
    summary.write_text("C:98.7%[S:98.0%,D:0.7%],F:0.4%,M:0.9%,n:124\n", encoding="utf-8")
    assert parse_busco_complete(summary) == 98.7


def test_parse_merqury_qv_falls_back_to_numeric_value(tmp_path: Path):
    qv = tmp_path / "qv.txt"
    qv.write_text("assembly only 99.9 42.3\n", encoding="utf-8")
    assert parse_merqury_qv(qv) == 42.3

