#!/usr/bin/env bash
# run_pipeline.sh — Full Part-A pipeline: simulate reads, compute stats, plot.
# All output is tee'd to logs/pipeline.log.
# Run from the project root:
#   bash run_pipeline.sh &

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PYTHON="D:/Anaconda/envs/genome_asm/python.exe"
BADREAD="D:/Anaconda/envs/genome_asm/Scripts/badread.exe"
REFERENCE="data/reference/ecoli.fasta"
READS_DIR="data/reads"
LOG_DIR="logs"
LOG="$LOG_DIR/pipeline.log"

mkdir -p "$READS_DIR" "$LOG_DIR" results/tables results/figures

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
section() {
    echo "" | tee -a "$LOG"
    echo "================================================================" | tee -a "$LOG"
    echo "  $*" | tee -a "$LOG"
    echo "================================================================" | tee -a "$LOG"
}

# Redirect all subsequent stdout+stderr through tee so every command is logged
exec > >(tee -a "$LOG") 2>&1

log "Pipeline started (PID $$)"
log "Log file: $LOG"

# ---------------------------------------------------------------------------
# Step 1 — Illumina simulation (pure-Python, HiSeq 2500 profile)
# ---------------------------------------------------------------------------
section "Step 1/5 — Illumina paired-end simulation"
log "Tool: scripts/simulate_illumina.py"
log "Params: 30x coverage, 150 bp reads, insert 350±50 bp"

T0=$SECONDS
"$PYTHON" scripts/simulate_illumina.py \
    --reference "$REFERENCE" \
    --coverage 30 \
    --read-length 150 \
    --insert-mean 350 \
    --insert-sd 50 \
    --output-prefix "$READS_DIR/illumina_30x_"

log "Illumina done in $(( SECONDS - T0 )) s"
log "Output: $READS_DIR/illumina_30x_1.fastq  $READS_DIR/illumina_30x_2.fastq"

# ---------------------------------------------------------------------------
# Step 2 — Nanopore simulation (badread, ONT error profile)
# ---------------------------------------------------------------------------
section "Step 2/5 — Nanopore long-read simulation"
log "Tool: badread v0.4.2"
log "Params: 30x, length 10000±5000 bp, default nanopore2023 error model"

T0=$SECONDS
"$BADREAD" simulate \
    --reference "$REFERENCE" \
    --quantity 30x \
    --length 10000,5000 \
    2>>"$LOG" \
    > "$READS_DIR/nanopore_30x.fastq"

log "Nanopore done in $(( SECONDS - T0 )) s"
log "Output: $READS_DIR/nanopore_30x.fastq"

# ---------------------------------------------------------------------------
# Step 3 — PacBio HiFi simulation (badread, random error model, 99.5% identity)
# ---------------------------------------------------------------------------
section "Step 3/5 — PacBio HiFi simulation"
log "Tool: badread v0.4.2"
log "Params: 30x, length 15000±3000 bp, identity 99.5/99.9/0.5, error_model random"

T0=$SECONDS
"$BADREAD" simulate \
    --reference "$REFERENCE" \
    --quantity 30x \
    --length 15000,3000 \
    --identity 99.5,99.9,0.5 \
    --error_model random \
    --qscore_model random \
    2>>"$LOG" \
    > "$READS_DIR/hifi_30x.fastq"

log "HiFi done in $(( SECONDS - T0 )) s"
log "Output: $READS_DIR/hifi_30x.fastq"

# ---------------------------------------------------------------------------
# Step 4 — Read statistics
# ---------------------------------------------------------------------------
section "Step 4/5 — Computing read statistics"
log "Script: scripts/stat_reads.py"

T0=$SECONDS
"$PYTHON" scripts/stat_reads.py
log "Stats done in $(( SECONDS - T0 )) s"
log "Output: results/tables/read_stats.csv"

# ---------------------------------------------------------------------------
# Step 5 — Read length distribution plot
# ---------------------------------------------------------------------------
section "Step 5/5 — Plotting read length distributions"
log "Script: scripts/plot_read_lengths.py"

T0=$SECONDS
"$PYTHON" scripts/plot_read_lengths.py
log "Plot done in $(( SECONDS - T0 )) s"
log "Output: results/figures/read_length_distribution.png"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section "Pipeline complete"
log "All steps finished successfully."
log ""
log "Generated files:"
for f in \
    "$READS_DIR/illumina_30x_1.fastq" \
    "$READS_DIR/illumina_30x_2.fastq" \
    "$READS_DIR/nanopore_30x.fastq" \
    "$READS_DIR/hifi_30x.fastq" \
    "results/tables/read_stats.csv" \
    "results/figures/read_length_distribution.png"; do
    if [ -f "$f" ]; then
        SIZE=$(du -h "$f" | cut -f1)
        log "  [OK]  $f  ($SIZE)"
    else
        log "  [MISSING]  $f"
    fi
done
