#!/usr/bin/env python3
"""Shared helpers for run-id handling and experiment-matrix expansion."""

from __future__ import annotations

import re
from itertools import product
from typing import Any, Iterable


RUN_ID_RE = re.compile(
    r"^(?P<tech>.+)_(?P<coverage>\d+)x_(?P<body>.+)_s(?P<seed>\d+)$"
)
KNOWN_REFERENCES = ("rep_v1", "rep_v2", "plasmid", "orig")


def make_run_id(
    tech: str,
    coverage: int,
    assembler: str,
    reference: str,
    seed: int,
) -> str:
    """Build the canonical run-id string."""
    return f"{tech}_{int(coverage)}x_{assembler}_{reference}_s{int(seed)}"


def parse_run_id(run_id: str) -> dict[str, Any]:
    """Parse a canonical run-id into axis fields."""
    match = RUN_ID_RE.match(run_id)
    if not match:
        raise ValueError(f"bad run_id: {run_id}")
    parts = match.groupdict()
    body = parts["body"]
    assembler = ""
    reference = ""
    for candidate in KNOWN_REFERENCES:
        suffix = f"_{candidate}"
        if body.endswith(suffix):
            assembler = body[: -len(suffix)]
            reference = candidate
            break
    if not assembler:
        try:
            assembler, reference = body.split("_", 1)
        except ValueError as exc:
            raise ValueError(f"bad run_id body: {run_id}") from exc
    return {
        "tech": parts["tech"],
        "coverage": int(parts["coverage"]),
        "assembler": assembler,
        "reference": reference,
        "seed": int(parts["seed"]),
    }


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["tech"],
        row["coverage"],
        row["assembler"],
        row["reference"],
        row["seed"],
    )


def expand_matrix(
    cfg: dict[str, Any],
    default_seed: int,
    seeds: Iterable[int] | None = None,
) -> list[dict[str, Any]]:
    """Expand matrix.yaml-style config into run dictionaries.

    Ordinary layer rows use ``default_seed``. Entries in ``multi_seed_subset``
    get additional seed rows when ``seeds`` is provided.
    """
    rows: list[dict[str, Any]] = []

    for layer in cfg["layers"].values():
        references = _as_list(layer["reference"])
        coverages = _as_list(layer["coverages"])
        for tech, reference, coverage in product(
            cfg["assemblers"],
            references,
            coverages,
        ):
            if tech not in cfg.get("technologies", {}) and tech != "hybrid":
                continue
            for assembler in cfg["assemblers"][tech]:
                rows.append(
                    {
                        "tech": tech,
                        "coverage": int(coverage),
                        "assembler": assembler,
                        "reference": reference,
                        "seed": int(default_seed),
                    }
                )

    seen = {_row_key(row) for row in rows}
    all_seeds = [int(seed) for seed in seeds] if seeds is not None else [int(default_seed)]
    for item in cfg.get("multi_seed_subset", []):
        for seed in all_seeds:
            row = {
                "tech": item["tech"],
                "coverage": int(item["coverage"]),
                "assembler": item["assembler"],
                "reference": item["reference"],
                "seed": seed,
            }
            key = _row_key(row)
            if key not in seen:
                rows.append(row)
                seen.add(key)

    return rows
