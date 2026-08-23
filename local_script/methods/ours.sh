#!/usr/bin/env bash

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
METHOD=Ours
DATASET=${2:-}

PREDICTIONS="$PROJECT_ROOT/data/ours/$DATASET/predictions.json"
prediction_for_k() { echo "$PREDICTIONS"; }
source "$SCRIPT_DIR/_run.sh"
