from scripts.build_reference_variants import append_plasmid, inject_tandem_repeat


def test_inject_tandem_repeat_increases_length():
    seq = "ACGT" * 1000
    out = inject_tandem_repeat(seq, unit_len=300, copies=5, at=500)
    assert len(out) == len(seq) + 300 * 5
    inserted = out[500 : 500 + 300 * 5]
    assert inserted[:300] == inserted[300:600]


def test_append_plasmid_adds_deterministic_record():
    records = append_plasmid({"chr": "ACGT" * 1000}, plasmid_len=2000, seed=13)
    again = append_plasmid({"chr": "ACGT" * 1000}, plasmid_len=2000, seed=13)
    assert "plasmid" in records
    assert len(records["plasmid"]) == 2000
    assert records["plasmid"] == again["plasmid"]

