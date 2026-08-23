# Text-to-SQL generation

This directory generates SQL from the schema-retrieval predictions of five methods:

- Ours
- DBCopilot
- IterJAR
- CORE-T
- QGpT

The retrieval predictions are normalized using the same database selection and table handling used by the shared metrics evaluation. The selected schema is then placed in a prompt and, unless dry-run mode is enabled, sent to an Azure AI Foundry model.

Commands using relative paths assume you are at the repository root:

```bash
cd path/to/text2sql_azure
```

## Directory layout

```text
text2sql_azure/
├── generate_sql.py          # SQL generation entry point
├── prediction_utils.py      # loaders, majority vote, and final table selection
├── data/                    # centralized prediction files
├── panther_script/          # SLURM/Panther launchers
├── local_script/            # local launchers
├── outputs/                 # generated SQL outputs
├── dry_run_outputs/         # validation and prompt outputs without API calls
├── logs/                    # SLURM output and error logs
├── test_foundry.py          # small Azure Foundry connectivity test
└── available_models.txt     # example Foundry deployment names
```

## Supported values

### Methods

The launcher accepts these method names:

```text
ours
dbcopilot
iterjar
core-t
qgpt
```

Method names passed to `main.sh` are converted to lowercase. When calling `generate_sql.py` directly, use the exact spelling accepted by its CLI:

```text
Ours
DBCopilot
IterJar
Core-t
QGpT
```

### Datasets

```text
spider
bird
beaver_dw
beaver_nw
```

The scripts automatically use:

- SQLite for `spider` and `bird`.
- MySQL for `beaver_dw` and `beaver_nw`.

### Top-K values

The shell launchers always run:

```text
K = 5, 10, 15
```

To run only one K, call `generate_sql.py` directly with `--top-k`.

## Prediction files

The launchers read predictions from this hierarchy:

```text
data/
├── datasets/<dataset>/test.json
├── datasets/<dataset>/schemas.json
├── ours/<dataset>/predictions.json
├── dbcopilot/<dataset>/predictions.json
├── qgpt/<dataset>/predictions.json
├── iterjar/<dataset>/greedy_k5.json
├── iterjar/<dataset>/greedy_k10.json
├── iterjar/<dataset>/greedy_k15.json
├── core-t/<dataset>/k_5.json
├── core-t/<dataset>/k_10.json
└── core-t/<dataset>/k_15.json
```

The `datasets` directory contains the questions and complete schemas used by SQL generation. The Ours files are the selected experiment outputs. IterJAR, CORE-T, and QGpT use the paper-reported prediction files.

## Environment setup

The supplied shell scripts use this Conda environment and executable:

```text
/export/home/aabdelmaguid/anaconda3/bin/conda
environment: text2sql_llm
```

A minimal environment can be created with:

```bash
conda create -n text2sql_llm python=3.11 -y
conda run -n text2sql_llm pip install openai
```

Dry-run mode does not import the OpenAI library and does not require API credentials. The shell launchers still expect the `text2sql_llm` Conda environment to exist.

## API configuration

Live SQL generation requires:

```bash
export AZURE_FOUNDRY_PROJECT_ENDPOINT="YOUR_ENDPOINT"
export AZURE_FOUNDRY_API_KEY="YOUR_API_KEY"
```

The model deployment name is passed as the first launcher argument. The launcher exports it as `AZURE_FOUNDRY_MODEL`.

Example deployment names currently listed in `available_models.txt` include:

```text
gpt-5-5-amr
gpt-5-4-mini-amr
gpt-5-4-amr
claude-opus-4-8-amr
claude-sonnet-4-6-amr
```

Use an exact deployment name available in your Foundry project.

## Recommended first run: no API

Use local dry-run mode from the repository directory to validate the entire input pipeline without generating SQL:

```bash
bash local_script/main.sh no-api ours bird --dry-run
```

The `no-api` value is only a placeholder model name. In dry-run mode it is not sent anywhere.

This command processes K=5, K=10, and K=15. It performs all of the following:

1. Loads the method's prediction file.
2. Checks that prediction and test row counts match.
3. Selects the predicted database.
4. Produces the final database-specific table set.
5. Validates every database and table against `schemas.json`.
6. Builds the complete SQL prompt.
7. Writes the inputs with `output: null`.

Dry-run output is written to:

```text
dry_run_outputs/<method>/<dataset>/<method>_top<K>.jsonl
```

For example:

```text
dry_run_outputs/ours/bird/ours_top5.jsonl
dry_run_outputs/ours/bird/ours_top10.jsonl
dry_run_outputs/ours/bird/ours_top15.jsonl
```

## Run locally with the API

```bash
bash local_script/main.sh MODEL METHOD DATASET
```

Example:

```bash
bash local_script/main.sh gpt-5-5-amr ours bird
```

Local execution runs K=5, K=10, and K=15 sequentially in the current terminal. It makes one API request per dataset example for each K.

Normal output is written to:

```text
outputs/<model>/<dataset>/<method>_top<K>.jsonl
```

Example:

```text
outputs/gpt-5-5-amr/bird/ours_top5.jsonl
```

## Submit through Panther/SLURM

```bash
bash /export/bayan_Text2SQL/text2sql_azure/panther_script/main.sh \
    MODEL METHOD DATASET
```

Example:

```bash
bash /export/bayan_Text2SQL/text2sql_azure/panther_script/main.sh \
    gpt-5-5-amr core-t spider
```

The Panther method scripts request:

```text
partition: cpu-all
time limit: 24 hours
```

Check jobs with:

```bash
squeue -u "$USER"
```

SLURM logs are written to:

```text
text2sql_azure/logs/<job-name>-<job-id>.out
text2sql_azure/logs/<job-name>-<job-id>.err
```

The API environment variables must be exported before submitting the job so SLURM can pass them into the job environment.

### Panther dry run

Adding `--dry-run` makes the Panther main launcher execute locally instead of submitting a job:

```bash
bash /export/bayan_Text2SQL/text2sql_azure/panther_script/main.sh \
    no-api qgpt beaver_nw --dry-run
```

For clarity, `local_script/main.sh` is preferred for local dry runs.

## Run an individual method script

Each launcher directory also contains one script per method:

```text
methods/ours.sh
methods/dbcopilot.sh
methods/iterjar.sh
methods/core_t.sh
methods/qgpt.sh
```

Local example:

```bash
bash local_script/methods/iterjar.sh \
    gpt-5-5-amr bird
```

Local dry-run example:

```bash
bash local_script/methods/iterjar.sh \
    no-api bird --dry-run
```

Direct SLURM example:

```bash
sbatch text2sql_azure/panther_script/methods/iterjar.sh \
    gpt-5-5-amr bird
```

## Direct Python usage

Calling Python directly provides control over one K, the dialect, temperature, seed, and query limit.

### Direct dry run

```bash
conda run -n text2sql_llm python generate_sql.py \
    --method Ours \
    --predictions data/ours/bird/predictions.json \
    --test data/datasets/bird/test.json \
    --schemas data/datasets/bird/schemas.json \
    --output /tmp/ours_bird_k5.jsonl \
    --top-k 5 \
    --dialect SQLite \
    --limit 10 \
    --dry-run
```

### Direct API generation

```bash
export AZURE_FOUNDRY_MODEL="gpt-5-5-amr"

conda run -n text2sql_llm python generate_sql.py \
    --method DBCopilot \
    --predictions data/dbcopilot/spider/predictions.json \
    --test data/datasets/spider/test.json \
    --schemas data/datasets/spider/schemas.json \
    --output outputs/gpt-5-5-amr/spider/dbcopilot_top5.jsonl \
    --top-k 5 \
    --dialect SQLite \
    --temperature 0 \
    --seed 42
```

## `generate_sql.py` options

| Option | Required | Default | Meaning |
|---|---:|---:|---|
| `--method` | Yes | — | One of `Ours`, `DBCopilot`, `IterJar`, `Core-t`, or `QGpT`. |
| `--predictions` | Yes | — | Path to the method's JSON prediction file. |
| `--test` | Yes | — | DBCopilot-format test JSON containing questions. |
| `--schemas` | Yes | — | DBCopilot-format schema JSON containing databases, tables, and columns. |
| `--output` | Yes | — | Destination JSONL file. Parent directories are created automatically. |
| `--top-k` | No | `5` | Number of retrieved table predictions used for each example. |
| `--dialect` | No | `SQLite` | SQL dialect named in the prompt, such as `SQLite` or `MySQL`. |
| `--temperature` | No | `0.0` | Sampling temperature passed to the API. |
| `--seed` | No | `42` | Seed passed to the API. |
| `--limit` | No | all rows | Process only the first N examples. Useful for testing. |
| `--dry-run` | No | disabled | Build and save prompts without importing the API client or generating SQL. |

Environment variables used by `generate_sql.py`:

| Variable | Required | Meaning |
|---|---:|---|
| `AZURE_FOUNDRY_PROJECT_ENDPOINT` | Live runs only | Azure AI Foundry project endpoint. |
| `AZURE_FOUNDRY_API_KEY` | Live runs only | Azure AI Foundry API key. |
| `AZURE_FOUNDRY_MODEL` | No | Model deployment name; defaults to `gpt-5-5-amr` for direct Python runs. |

## Database and table selection

The logic in `prediction_utils.py` mirrors the shared metrics evaluation:

- DBCopilot uses the database from its first predicted schema.
- Table-only predictions use a majority vote over the database portion of the top-K table IDs.
- Ours uses an explicit recognized database field when one exists; otherwise it uses the same majority vote.
- If database vote counts tie, the database appearing earliest in retrieval order wins.
- After selecting one database, only predicted tables belonging to that database are used for SQL generation.
- Duplicate final table IDs are removed while preserving their first occurrence.
- CORE-T duplicates remain present during database voting, matching its metric loader, and are removed from the final SQL schema afterward.

The generator never uses the gold database to choose the prompt schema.

## Prompt format

The prompt contains:

1. The SQL dialect.
2. The predicted database.
3. Every selected table and its columns.
4. The natural-language question.
5. A final `SELECT` prefix.

The model is instructed to return SQL only, without an explanation.

## Output format

Each line of the output is one JSON object:

```json
{
  "method": "Ours",
  "dry_run": false,
  "input": {
    "question": "...",
    "predicted_database": "...",
    "retrieved_table_ids": ["db#sep#table"],
    "predicted_table_ids": ["db#sep#table"],
    "schema": [
      {
        "name": "database",
        "tables": [
          {
            "name": "table",
            "columns": ["column_1", "column_2"]
          }
        ]
      }
    ],
    "prompt": "..."
  },
  "output": "SELECT ...;"
}
```

Field meanings:

- `retrieved_table_ids`: the top-K retrieval input used by the metrics-compatible loader.
- `predicted_table_ids`: the final deduplicated tables belonging to the selected database.
- `schema`: the database/table/column schema shown to the model.
- `prompt`: the exact prompt sent to the model.
- `output`: cleaned SQL, or `null` during a dry run.

Live SQL output is normalized to begin with `SELECT` and end with a semicolon. Markdown fences and leading `SQL:` text are removed.

## Validation and failure behavior

The program stops with an error when:

- Prediction and test files have different numbers of rows.
- A prediction has no selected database.
- No retrieved tables belong to the selected database.
- A predicted database is absent from `schemas.json`.
- A predicted table is absent from the selected database schema.
- The model returns an empty SQL completion.
- Required API variables are missing during a live run.

The output file is opened in write mode, so rerunning the same method/model/dataset/K overwrites that output file. If a run fails partway through, the file contains the rows completed before the failure.

## Test the Foundry connection

`test_foundry.py` sends a small request to the deployment hardcoded in its `MODEL` variable:

```bash
conda run -n text2sql_llm python test_foundry.py
```

Set the two API environment variables first. Change `MODEL` inside `test_foundry.py` if you want to test another deployment.

## Common examples

Validate Ours on BIRD without API calls:

```bash
bash local_script/main.sh no-api ours bird --dry-run
```

Generate DBCopilot SQL for Spider locally:

```bash
bash local_script/main.sh gpt-5-5-amr dbcopilot spider
```

Submit CORE-T on Beaver-DW through SLURM:

```bash
bash text2sql_azure/panther_script/main.sh gpt-5-5-amr core-t beaver_dw
```

Validate QGpT on only ten Spider examples and K=10:

```bash
conda run -n text2sql_llm python generate_sql.py \
    --method QGpT \
    --predictions data/qgpt/spider/predictions.json \
    --test data/datasets/spider/test.json \
    --schemas data/datasets/spider/schemas.json \
    --output /tmp/qgpt_spider_k10.jsonl \
    --top-k 10 \
    --limit 10 \
    --dry-run
```
