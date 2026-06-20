from scripts.analyze_benchmark import min_viable_coverage, pareto_front, variance_attribution


def test_min_viable_coverage_finds_knee():
    rows = [
        {"coverage": 5, "genome_fraction_pct": 60, "contigs": 40},
        {"coverage": 10, "genome_fraction_pct": 85, "contigs": 10},
        {"coverage": 20, "genome_fraction_pct": 99.2, "contigs": 1},
        {"coverage": 30, "genome_fraction_pct": 99.9, "contigs": 1},
    ]
    assert min_viable_coverage(rows, gf_threshold=99, max_contigs=1) == 20


def test_pareto_front_keeps_nondominated():
    rows = [
        {"label": "a", "cost": 1, "quality": 90},
        {"label": "b", "cost": 2, "quality": 95},
        {"label": "c", "cost": 2, "quality": 80},
    ]
    front = set(pareto_front(rows, cost="cost", quality="quality", label="label"))
    assert "a" in front and "b" in front and "c" not in front


def test_variance_attribution_returns_factor_shares():
    rows = [
        {"tech": "illumina", "assembler": "spades", "n50": 100},
        {"tech": "illumina", "assembler": "spades", "n50": 120},
        {"tech": "hifi", "assembler": "hifiasm", "n50": 1000},
        {"tech": "hifi", "assembler": "flye", "n50": 900},
    ]
    shares = variance_attribution(rows)
    assert shares["tech"] > 0
    assert shares["assembler"] > 0

