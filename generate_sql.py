"""Generate SQL with Azure AI Foundry from any schema-retrieval method."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from prediction_utils import load_predictions


class QueryFailure(ValueError):
    """A failure that applies to one query rather than the whole run."""

    status = "query_failure"


class EmptyModelOutput(QueryFailure):
    status = "empty_model_output"


class InvalidModelOutput(QueryFailure):
    status = "invalid_model_output"


class MalformedModelResponse(QueryFailure):
    status = "malformed_model_response"


def selected_schema(pairs, all_schemas):
    """Attach canonical columns to valid tables and report invalid table names."""
    database_names = {name.lower(): name for name in all_schemas}
    result = {}
    invalid_tables = []

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
            invalid_tables.append(predicted_table)
            continue
        columns = []
        column_types = []
        primary_keys = []
        foreign_keys = []
        for column in table.get("columns", []):
            if isinstance(column, dict):
                columns.append(column["name"])
                column_types.append(str(column.get("type") or "unknown"))
                if column.get("primary_key"):
                    primary_keys.append(column["name"])
                foreign_key = column.get("foreign_key")
                if (
                    isinstance(foreign_key, dict)
                    and foreign_key.get("table")
                    and foreign_key.get("column")
                ):
                    foreign_keys.append({
                        "column": column["name"],
                        "table": foreign_key["table"],
                        "referenced_column": foreign_key["column"],
                    })
            else:
                columns.append(column)
                column_types.append("unknown")
        result.setdefault(database, [])
        if not any(x["name"] == table["name"] for x in result[database]):
            selected_table = {
                "name": table["name"],
                "columns": columns,
                "column_types": column_types,
            }
            if primary_keys:
                selected_table["primary_keys"] = primary_keys
            if foreign_keys:
                selected_table["foreign_keys"] = foreign_keys
            result[database].append(selected_table)

    schema = [{"name": database, "tables": tables} for database, tables in result.items()]
    return schema, invalid_tables


def make_prompt(question, schema, dialect):
    schema_lines = []
    for database in schema:
        schema_lines.append(f'Database: {database["name"]}')
        selected_tables = {
            table["name"].lower()
            for table in database["tables"]
        }
        for table in database["tables"]:
            column_types = table.get("column_types", [])
            columns = ", ".join(
                f'"{column}" {column_types[index] if index < len(column_types) else "unknown"}'
                for index, column in enumerate(table["columns"])
            )
            schema_lines.append(f'{table["name"]}({columns})')
            for column in table.get("primary_keys", []):
                schema_lines.append(f'Primary key: {table["name"]}.{column}')
            for foreign_key in table.get("foreign_keys", []):
                if foreign_key["table"].lower() in selected_tables:
                    schema_lines.append(
                        f'Foreign key: {table["name"]}.{foreign_key["column"]} '
                        f'-> {foreign_key["table"]}.{foreign_key["referenced_column"]}'
                    )

    schema_text = "\n".join(schema_lines)
#     return f"""You are given a database schema and a natural-language question.

# Generate a valid {dialect} SQL query that answers the question.

# Rules:

# - Use only the provided tables and columns.
# - Do not invent table or column names.
# - Use joins when multiple tables are required.
# - Return only the SQL query without explanation.

# Database schema:
# {schema_text}

# Question:
# {question}

# SQL:"""
    return f"""You are given a database schema and a natural-language question.

    Generate a valid {dialect} SQL query that answers the question.

    Rules:

    - Identify the tables and columns needed to answer the question.
    - Use only the provided tables and columns. Do not invent table or column names.
    - Use explicit JOIN ... ON when multiple tables are required.
    - Do not use SELECT *. If the question requests specific attributes, explicitly select those attributes.
      If the question asks for information, details, or records about an entity without specifying particular attributes, 
      explicitly list all columns of that entity in the order shown in the schema.
      Tables used only for joins should not contribute output columns unless their information is also requested.
    - Apply filtering, grouping, aggregation, ordering, and limits as required by the question.
    - Return only the SQL query without explanation.

    Database schema:
    {schema_text}

    Question:
    {question}

    SQL:"""


def extract_sql(text):
    """Extract SQL without modifying SQL literals or structure."""
    if text is None or (isinstance(text, str) and not text.strip()):
        raise EmptyModelOutput("The model returned empty SQL")
    if not isinstance(text, str):
        raise MalformedModelResponse(
            f"The model returned non-text content: {type(text).__name__}"
        )

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
        raise InvalidModelOutput(f"No SQL statement found: {text!r}")

    sql = text[start.start():].strip()

    if not sql.endswith(";"):
        sql += ";"

    return sql


def response_content(response):
    """Return completion text or classify an unusable API response."""
    if response is None:
        raise EmptyModelOutput("The API returned no response")

    choices = getattr(response, "choices", None)
    if not choices:
        raise MalformedModelResponse("The model response has no choices")

    try:
        first_choice = choices[0]
    except (IndexError, KeyError, TypeError) as error:
        raise MalformedModelResponse(
            "The model response choices are unusable"
        ) from error

    message = getattr(first_choice, "message", None)
    if message is None:
        raise MalformedModelResponse(
            "The first model response choice has no message content"
        )

    missing = object()
    content = getattr(message, "content", missing)
    if content is missing or content is None or not isinstance(content, str):
        raise MalformedModelResponse(
            "The first model response choice contains unusable message content"
        )
    return content


def make_result(
    args,
    example,
    prediction,
    status,
    *,
    schema=None,
    prompt=None,
    invalid_predicted_tables=None,
    raw_output=None,
    sql=None,
):
    """Build one output row with a consistent success/failure structure."""
    schema = schema or []
    invalid_predicted_tables = invalid_predicted_tables or []
    return {
        "method": args.method,
        "dry_run": args.dry_run,
        "status": status,
        "input": {
            "question": example["question"],
            "predicted_database": prediction["database"],
            "retrieved_table_ids": prediction["retrieved_table_ids"],
            "predicted_table_ids": prediction["table_ids"],
            "invalid_predicted_tables": invalid_predicted_tables,
            "num_requested_tables": len(prediction["retrieved_table_ids"]),
            "num_valid_tables": sum(
                len(database["tables"])
                for database in schema
            ),
            "schema": schema,
            "prompt": prompt,
        },
        "raw_output": raw_output,
        "output": sql,
    }


def write_result(output_file, result):
    output_file.write(json.dumps(result, ensure_ascii=False) + "\n")
    output_file.flush()


ALIGNMENT_ID_KEYS = (
    "question_id", "query_id", "example_id", "instance_id", "sample_id",
    "query_index", "question_index", "example_index", "index", "idx", "id",
)
ALIGNMENT_INDEX_KEYS = {
    "query_index", "question_index", "example_index", "index", "idx",
}


def _first_alignment_value(row, keys):
    if not isinstance(row, dict):
        return None, None
    for key in keys:
        if row.get(key) is not None:
            return key, row[key]
    return None, None


def validate_row_alignment(prediction_rows, test_rows):
    """Fail on identifiable row mismatches; warn when only position is available."""
    rows_without_id = 0
    for index, (prediction_row, test_row) in enumerate(zip(prediction_rows, test_rows)):
        has_usable_identifier = False
        for prediction_key in ALIGNMENT_ID_KEYS:
            if (
                not isinstance(prediction_row, dict)
                or prediction_row.get(prediction_key) is None
            ):
                continue
            prediction_id = prediction_row[prediction_key]
            if isinstance(test_row, dict) and test_row.get(prediction_key) is not None:
                expected = test_row[prediction_key]
                expected_key = prediction_key
            elif prediction_key in ALIGNMENT_INDEX_KEYS:
                expected = index
                expected_key = "test row index"
            else:
                continue

            has_usable_identifier = True
            if str(prediction_id) != str(expected):
                raise ValueError(
                    f"Prediction/test row alignment mismatch at row {index}: "
                    f"prediction {prediction_key}={prediction_id!r}, "
                    f"{expected_key}={expected!r}"
                )

        # Existing files often retain the question text rather than a separate ID.
        if not has_usable_identifier:
            prediction_key, prediction_question = _first_alignment_value(
                prediction_row, ("question", "query")
            )
            test_key, test_question = _first_alignment_value(
                test_row, ("question", "query")
            )
            if prediction_key is not None and test_key is not None:
                if str(prediction_question).strip() != str(test_question).strip():
                    raise ValueError(
                        f"Prediction/test row alignment mismatch at row {index}: "
                        f"prediction {prediction_key}={prediction_question!r}, "
                        f"test {test_key}={test_question!r}"
                    )
                has_usable_identifier = True

        if not has_usable_identifier:
            rows_without_id += 1

    if rows_without_id:
        print(
            f"WARNING: Prediction file contains no question/query ID for "
            f"{rows_without_id} row(s); continuing with unchanged positional "
            "alignment. Question text was compared where available.",
            file=sys.stderr,
        )


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
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, help="Only run the first N queries")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and save the selected schemas/prompts without calling the API",
    )
    args = parser.parse_args()

    prediction_rows = json.loads(args.predictions.read_text())
    predictions = load_predictions(args.predictions, args.method, args.top_k)
    test = json.loads(args.test.read_text())
    schemas = json.loads(args.schemas.read_text())
    if len(predictions) != len(test):
        raise ValueError(f"Predictions and test data have different lengths: {len(predictions)} != {len(test)}")
    validate_row_alignment(prediction_rows, test)

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
                result = make_result(
                    args,
                    example,
                    prediction,
                    "no_valid_database",
                )
                write_result(output_file, result)
                print(f"{index + 1}: no_valid_database")
                continue
            if not prediction["tables"]:
                result = make_result(
                    args,
                    example,
                    prediction,
                    "no_valid_tables",
                )
                write_result(output_file, result)
                print(
                    f"{index + 1}: no_valid_tables "
                    f"(predicted database: {prediction['database']})"
                )
                continue
            pairs = [
                (prediction["database"], table)
                for table in prediction["tables"]
            ]
            schema, invalid_predicted_tables = selected_schema(pairs, schemas)
            num_valid_tables = sum(
                len(database["tables"])
                for database in schema
            )
            if not num_valid_tables:
                result = make_result(
                    args,
                    example,
                    prediction,
                    "no_valid_tables",
                    invalid_predicted_tables=invalid_predicted_tables,
                )
                write_result(output_file, result)
                print(
                    f"{index + 1}: no_valid_tables "
                    f"(predicted database: {prediction['database']})"
                )
                continue
            prompt = make_prompt(example["question"], schema, args.dialect)
            raw_output = None
            sql = None
            if not args.dry_run:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    seed=args.seed,
                )
                try:
                    raw_output = response_content(response)
                    sql = extract_sql(raw_output)
                except QueryFailure as error:
                    result = make_result(
                        args,
                        example,
                        prediction,
                        error.status,
                        schema=schema,
                        prompt=prompt,
                        invalid_predicted_tables=invalid_predicted_tables,
                        raw_output=raw_output,
                    )
                    write_result(output_file, result)
                    print(f"{index + 1}: {error.status}")
                    continue

            result = make_result(
                args,
                example,
                prediction,
                "ok",
                schema=schema,
                prompt=prompt,
                invalid_predicted_tables=invalid_predicted_tables,
                raw_output=raw_output,
                sql=sql,
            )
            write_result(output_file, result)
            print(f"{index + 1}: {'validated' if args.dry_run else sql}")


if __name__ == "__main__":
    main()
