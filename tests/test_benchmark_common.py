from scripts.benchmark_common import expand_matrix, make_run_id, parse_run_id


def test_make_and_parse_run_id_roundtrip():
    rid = make_run_id(
        tech="ont_r10",
        coverage=30,
        assembler="flye",
        reference="orig",
        seed=13,
    )
    assert rid == "ont_r10_30x_flye_orig_s13"
    parts = parse_run_id(rid)
    assert parts == {
        "tech": "ont_r10",
        "coverage": 30,
        "assembler": "flye",
        "reference": "orig",
        "seed": 13,
    }


def test_parse_run_id_accepts_reference_with_underscore():
    rid = "illumina_10x_spades_rep_v1_s17"
    assert parse_run_id(rid) == {
        "tech": "illumina",
        "coverage": 10,
        "assembler": "spades",
        "reference": "rep_v1",
        "seed": 17,
    }


def test_expand_matrix_l1_counts():
    cfg = {
        "technologies": {
            "hifi": {"kind": "long"},
            "illumina": {"kind": "short"},
        },
        "assemblers": {
            "hifi": ["hifiasm"],
            "illumina": ["spades"],
        },
        "layers": {
            "L1_main": {
                "reference": "orig",
                "coverages": [10, 30],
            }
        },
        "multi_seed_subset": [],
    }
    rows = expand_matrix(cfg, default_seed=13)
    assert len(rows) == 4
    assert all(row["seed"] == 13 for row in rows)


def test_expand_matrix_adds_extra_multi_seed_rows_without_duplicates():
    cfg = {
        "technologies": {"hifi": {"kind": "long"}},
        "assemblers": {"hifi": ["hifiasm"]},
        "layers": {"L1_main": {"reference": "orig", "coverages": [30]}},
        "multi_seed_subset": [
            {"tech": "hifi", "coverage": 30, "assembler": "hifiasm", "reference": "orig"}
        ],
    }
    rows = expand_matrix(cfg, default_seed=13, seeds=[13, 17, 19])
    assert [row["seed"] for row in rows] == [13, 17, 19]

