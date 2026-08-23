"""Generate SQL with Azure AI Foundry from any schema-retrieval method."""

import argparse
import json
import os
import re
from pathlib import Path

from prediction_utils import load_predictions


def selected_schema(pairs, all_schemas):
    """Group valid predicted tables by database and attach their columns."""
    database_names = {name.lower(): name for name in all_schemas}
    result = {}

    for predicted_database, predicted_table in pairs:
        database = database_names.get(predicted_database.lower())
        if database is None:
            raise ValueError(f"Predicted database not found in schemas.json: {predicted_database}")
        tables = all_schemas[database]
        table = next(
            (x for x in tables if x["name"].lower() == predicted_table.lower()),
            None,
        )
        if table is None:
            raise ValueError(f"Predicted table not found in {database}: {predicted_table}")
        columns = [
            column["name"] if isinstance(column, dict) else column
            for column in table.get("columns", [])
        ]
        result.setdefault(database, [])
        if not any(x["name"] == table["name"] for x in result[database]):
            result[database].append({"name": table["name"], "columns": columns})

    return [{"name": database, "tables": tables} for database, tables in result.items()]


def make_prompt(question, schema, dialect):
    lines = [
        f"### Complete {dialect} SQL query only and with no explanation",
        f"### {dialect} SQL databases, with their tables and properties:",
        "#",
    ]
    for database in schema:
        lines.append(f'# {database["name"]}')
        for table in database["tables"]:
            columns = ", ".join(f'"{column}"' for column in table["columns"])
            lines.append(f'# {table["name"]}({columns})')
    lines += [f"### {question}", "SELECT"]
    return "\n".join(lines)


def extract_sql(text):
    """Extract SQL without modifying SQL literals or structure."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The model returned empty SQL")

    text = text.strip()

    fenced = re.search(
        r"```(?:sql)?\s*(.*?)```",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        text = fenced.group(1).strip()

    text = re.sub(
        r"^\s*(?:SQL\s*:\s*)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    start = re.search(
        r"(?im)^\s*(SELECT|WITH)\b",
        text,
    )
    if not start:
        raise ValueError(f"No SQL statement found: {text!r}")

    sql = text[start.start():].strip()

    if not sql.endswith(";"):
        sql += ";"

    return sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True, choices=["Ours", "DBCopilot", "IterJar", "Core-t", "QGpT"])
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--test", required=True, type=Path, help="DBCopilot-format test.json")
    parser.add_argument("--schemas", required=True, type=Path, help="DBCopilot-format schemas.json")
    parser.add_argument("--output", required=True, type=Path, help="Output .jsonl file")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved tables, matching the shared metrics evaluation",
    )
    parser.add_argument("--dialect", default="SQLite")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, help="Only run the first N queries")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and save the selected schemas/prompts without calling the API",
    )
    args = parser.parse_args()

    predictions = load_predictions(args.predictions, args.method, args.top_k)
    test = json.loads(args.test.read_text())
    schemas = json.loads(args.schemas.read_text())
    if len(predictions) != len(test):
        raise ValueError(f"Predictions and test data have different lengths: {len(predictions)} != {len(test)}")

    client = None
    if not args.dry_run:
        from openai import OpenAI

        client = OpenAI(
            base_url=os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"].rstrip("/") + "/openai/v1/",
            api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
        )
    model = os.getenv("AZURE_FOUNDRY_MODEL", "gpt-5-5-amr")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = zip(test, predictions)
    if args.limit is not None:
        rows = list(rows)[: args.limit]

    with args.output.open("w") as output_file:
        for index, (example, prediction) in enumerate(rows):
            if not prediction["database"]:
                raise ValueError(f"Prediction {index} has no majority-voted database")
            if not prediction["tables"]:
                raise ValueError(f"Prediction {index} has no tables in database {prediction['database']}")
            pairs = [
                (prediction["database"], table)
                for table in prediction["tables"]
            ]
            schema = selected_schema(pairs, schemas)
            prompt = make_prompt(example["question"], schema, args.dialect)
            raw_output = None
            sql = None
            if not args.dry_run:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=args.temperature,
                    seed=args.seed,
                )
                raw_output = response.choices[0].message.content
                sql = extract_sql(raw_output)

            result = {
                "method": args.method,
                "dry_run": args.dry_run,
                "input": {
                    "question": example["question"],
                    "predicted_database": prediction["database"],
                    "retrieved_table_ids": prediction["retrieved_table_ids"],
                    "predicted_table_ids": prediction["table_ids"],
                    "schema": schema,
                    "prompt": prompt,
                },
                "raw_output": raw_output,
                "output": sql,
            }
            output_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            output_file.flush()
            print(f"{index + 1}: {'validated' if args.dry_run else sql}")


if __name__ == "__main__":
    main()
