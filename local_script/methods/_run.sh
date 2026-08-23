#!/usr/bin/env bash

ROOT=/export/bayan_Text2SQL
MODEL=$1
DATASET=$2
MODE=${3:-}
DATA_DIR="$ROOT/text2sql_azure/data/datasets/$DATASET"
MODEL_DIR=$(basename "$MODEL")

if [[ "$DATASET" == "spider" || "$DATASET" == "bird" ]]; then
    DIALECT=SQLite
else
    DIALECT=MySQL
fi

export AZURE_FOUNDRY_MODEL="$MODEL"
if [[ "$MODE" == "--dry-run" ]]; then
    OUTPUT_DIR="$ROOT/text2sql_azure/dry_run_outputs/${METHOD,,}/$DATASET"
    EXTRA_ARGS=(--dry-run)
else
    OUTPUT_DIR="$ROOT/text2sql_azure/outputs/$MODEL_DIR/$DATASET"
    EXTRA_ARGS=()
fi
mkdir -p "$ROOT/text2sql_azure/logs" "$OUTPUT_DIR"

for TOP_K in 5 10 15; do
    PREDICTIONS=$(prediction_for_k "$TOP_K")
    OUTPUT="$OUTPUT_DIR/${METHOD,,}_top${TOP_K}.jsonl"

    /export/home/aabdelmaguid/anaconda3/bin/conda run -n text2sql_llm \
        python "$ROOT/text2sql_azure/generate_sql.py" \
        --method "$METHOD" \
        --predictions "$PREDICTIONS" \
        --test "$DATA_DIR/test.json" \
        --schemas "$DATA_DIR/schemas.json" \
        --output "$OUTPUT" \
        --top-k "$TOP_K" \
        --dialect "$DIALECT" \
        "${EXTRA_ARGS[@]}"
done
