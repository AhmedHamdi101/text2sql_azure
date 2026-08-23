#!/usr/bin/env bash
#SBATCH --job-name=foundry-iterjar
#SBATCH --partition=cpu-all
#SBATCH --time=24:00:00
#SBATCH --output=/export/bayan_Text2SQL/text2sql_azure/logs/%x-%j.out
#SBATCH --error=/export/bayan_Text2SQL/text2sql_azure/logs/%x-%j.err

ROOT=/export/bayan_Text2SQL
METHOD=IterJar
DATASET=${2:-}

prediction_for_k() { echo "$ROOT/text2sql_azure/data/iterjar/$DATASET/greedy_k$1.json"; }
source "$ROOT/text2sql_azure/panther_script/methods/_run.sh"
