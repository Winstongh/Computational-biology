#!/usr/bin/env bash
# Run Part C: QUAST evaluation, metrics table, figures, and conclusions.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_PREFIX="${PART_C_ENV:-$PROJECT_ROOT/.conda/part-c}"
PYTHON="$ENV_PREFIX/bin/python"
QUAST="$ENV_PREFIX/bin/quast.py"
QUAST_OUTPUT="quast_reports/all_assemblies"

if [[ ! -x "$PYTHON" || ! -x "$QUAST" ]]; then
    echo "Part C environment is missing at: $ENV_PREFIX" >&2
    echo "Create it with:" >&2
    echo "  conda env create -p \"$ENV_PREFIX\" -f environment-part-c.yml" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
export MPLCONFIGDIR="$PROJECT_ROOT/.matplotlib"
export XDG_CACHE_HOME="$PROJECT_ROOT/.cache"
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME" logs

"$PYTHON" scripts/run_part_c.py \
    --project-root "$PROJECT_ROOT" \
    --quast "$QUAST" \
    --quast-output "$QUAST_OUTPUT" \
    --threads "${PART_C_THREADS:-4}" \
    2>&1 | tee logs/part_c.log
