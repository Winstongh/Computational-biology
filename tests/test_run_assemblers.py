from pathlib import Path

from scripts.run_assemblers import gfa_to_fasta, parse_time_v


def test_gfa_to_fasta_converts_segment_records(tmp_path: Path):
    gfa = tmp_path / "asm.gfa"
    gfa.write_text("H\tVN:Z:1.0\nS\tcontig1\tACGT\nS\tcontig2\tTTAA\n", encoding="utf-8")
    fasta = gfa_to_fasta(gfa, tmp_path / "assembly.fasta")
    assert fasta.read_text(encoding="ascii") == ">contig1\nACGT\n>contig2\nTTAA\n"


def test_parse_time_v_extracts_ram_and_elapsed_seconds():
    stderr = (
        "Maximum resident set size (kbytes): 204800\n"
        "Elapsed (wall clock) time (h:mm:ss or m:ss): 1:02.50\n"
    )
    assert parse_time_v(stderr) == (200.0, 62.5)

