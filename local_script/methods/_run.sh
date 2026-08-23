#!/usr/bin/env bash

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)

MODEL=$1
DATASET=$2
MODE=${3:-}
DATA_DIR="$PROJECT_ROOT/data/datasets/$DATASET"
MODEL_DIR=$(basename "$MODEL")
CONDA_BIN=${CONDA_EXE:-conda}

if [[ "$DATASET" == "spider" || "$DATASET" == "bird" ]]; then
    DIALECT=SQLite
else
    DIALECT=MySQL
fi

export AZURE_FOUNDRY_MODEL="$MODEL"
if [[ "$MODE" == "--dry-run" ]]; then
    OUTPUT_DIR="$PROJECT_ROOT/dry_run_outputs/${METHOD,,}/$DATASET"
    EXTRA_ARGS=(--dry-run)
else
    OUTPUT_DIR="$PROJECT_ROOT/outputs/$MODEL_DIR/$DATASET"
    EXTRA_ARGS=()
fi
mkdir -p "$PROJECT_ROOT/logs" "$OUTPUT_DIR"

for TOP_K in 5 10 15; do
    PREDICTIONS=$(prediction_for_k "$TOP_K")
    OUTPUT="$OUTPUT_DIR/${METHOD,,}_top${TOP_K}.jsonl"

    "$CONDA_BIN" run -n text2sql_llm \
        python "$PROJECT_ROOT/generate_sql.py" \
        --method "$METHOD" \
        --predictions "$PREDICTIONS" \
        --test "$DATA_DIR/test.json" \
        --schemas "$DATA_DIR/schemas.json" \
        --output "$OUTPUT" \
        --top-k "$TOP_K" \
        --dialect "$DIALECT" \
        "${EXTRA_ARGS[@]}"
done
