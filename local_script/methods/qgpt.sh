#!/usr/bin/env bash

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
METHOD=QGpT
DATASET=${2:-}

PREDICTIONS="$PROJECT_ROOT/data/qgpt/$DATASET/predictions.json"
prediction_for_k() { echo "$PREDICTIONS"; }
source "$SCRIPT_DIR/_run.sh"
