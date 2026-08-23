#!/usr/bin/env bash
#SBATCH --job-name=foundry-dbcopilot
#SBATCH --partition=cpu-all
#SBATCH --time=24:00:00
#SBATCH --output=/export/bayan_Text2SQL/text2sql_azure/logs/%x-%j.out
#SBATCH --error=/export/bayan_Text2SQL/text2sql_azure/logs/%x-%j.err

ROOT=/export/bayan_Text2SQL
METHOD=DBCopilot

PREDICTIONS="$ROOT/text2sql_azure/data/dbcopilot/$2/predictions.json"
prediction_for_k() { echo "$PREDICTIONS"; }
source "$ROOT/text2sql_azure/local_script/methods/_run.sh"
