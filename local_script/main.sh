#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 MODEL METHOD DATASET [--dry-run] [--top-k {5,10,15}]" >&2
    exit 2
fi

MODEL=$1
METHOD=${2,,}
DATASET=$3

case "$METHOD" in
    ours) SCRIPT=ours.sh;;
    dbcopilot) SCRIPT=dbcopilot.sh;;
    iterjar) SCRIPT=iterjar.sh;;
    core-t) SCRIPT=core_t.sh;;
    qgpt) SCRIPT=qgpt.sh;;
    *)
        echo "Unknown method: $METHOD" >&2
        exit 2
        ;;
esac

mkdir -p "$PROJECT_ROOT/logs"
bash "$SCRIPT_DIR/methods/$SCRIPT" "$MODEL" "$DATASET" "${@:4}"
