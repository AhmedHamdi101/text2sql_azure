#!/usr/bin/env bash

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
METHOD=IterJar
DATASET=${2:-}

prediction_for_k() { echo "$PROJECT_ROOT/data/iterjar/$DATASET/greedy_k$1.json"; }
source "$SCRIPT_DIR/_run.sh"
