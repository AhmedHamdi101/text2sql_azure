#!/usr/bin/env bash

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)

MODEL=$1
DATASET=$2
MODE=
TOP_K_VALUES=(5 10 15)
shift 2
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            MODE=--dry-run
            shift
            ;;
        --top-k)
            if [[ $# -lt 2 || ! "$2" =~ ^(5|10|15)$ ]]; then
                echo "--top-k must be one of: 5, 10, 15" >&2
                exit 2
            fi
            TOP_K_VALUES=("$2")
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
    esac
done
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

for TOP_K in "${TOP_K_VALUES[@]}"; do
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
