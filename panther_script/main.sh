#!/usr/bin/env bash
MODEL=$1
METHOD=${2,,}
DATASET=$3
MODE=${4:-}

case "$METHOD" in
    ours) SCRIPT=ours.sh;;
    dbcopilot) SCRIPT=dbcopilot.sh;;
    iterjar) SCRIPT=iterjar.sh;;
    core-t) SCRIPT=core_t.sh;;
    qgpt) SCRIPT=qgpt.sh;;
esac

mkdir -p /export/bayan_Text2SQL/text2sql_azure/logs
if [[ "$MODE" == "--dry-run" ]]; then
    bash "/export/bayan_Text2SQL/text2sql_azure/panther_script/methods/$SCRIPT" "$MODEL" "$DATASET" --dry-run
else
    sbatch "/export/bayan_Text2SQL/text2sql_azure/panther_script/methods/$SCRIPT" "$MODEL" "$DATASET"
fi
