"""Load retrieval predictions exactly like the shared metrics evaluation."""

import json
from pathlib import Path


SEP = "#sep#"


def normalize(value):
    return str(value or "").strip().lower()


def split_table_id(value):
    """Return (database, table) from db#sep#table, db.table, or table."""
    value = str(value or "").strip()
    if SEP in value:
        database, table = value.split(SEP, 1)
        return normalize(database), normalize(table)
    if "." in value:
        database, table = value.split(".", 1)
        return normalize(database), normalize(table)
    return None, normalize(value)


def normalize_table_id(value):
    database, table = split_table_id(value)
    if not table:
        return ""
    return f"{database}{SEP}{table}" if database else table


def normalize_table_list(values):
    """Normalize and deduplicate tables while preserving retrieval order."""
    result = []
    for value in values if isinstance(values, list) else []:
        table_id = normalize_table_id(value)
        if table_id and table_id not in result:
            result.append(table_id)
    return result


def majority_vote_database(table_ids):
    """Same majority vote as paper-results-calculations/unified_compare.py."""
    counts = {}
    for table_id in table_ids:
        database, _ = split_table_id(table_id)
        if database:
            counts[database] = counts.get(database, 0) + 1
    if not counts:
        return None
    # Python keeps insertion order, so a tie goes to the earliest retrieved DB.
    return max(counts.items(), key=lambda item: item[1])[0]


def value_at_k(value, k):
    if isinstance(value, list):
        return value[:k]
    if isinstance(value, dict):
        return value.get(str(k), value.get(k, []))
    return []


def explicit_database(row):
    """Explicit DB fields recognized by the Ours metrics loader."""
    for key in (
        "pred_db", "db_pred", "predicted_db", "pred_database",
        "database_pred", "top_db", "db",
    ):
        if row.get(key) is not None:
            value = row[key]
            if isinstance(value, list):
                value = value[0] if value else None
            if isinstance(value, dict):
                value = next(
                    (value.get(x) for x in ("db_id", "database", "db", "name") if value.get(x)),
                    None,
                )
            return normalize(value) or None
    return None


def load_ours(row, k):
    for key in (
        "pred_table_ids_by_k", "table_ids_by_k", "tables_ranked_ids_by_k",
        "predicted_table_ids_by_k", "tables_ranked_by_k", "tables_by_k",
        "pred_tables_by_k", "predicted_tables_by_k", "table_predictions_by_k",
        "table_ks",
    ):
        if key in row:
            tables = value_at_k(row[key], k)
            break
    else:
        tables = next(
            (row[key] for key in (
                "pred_table_ids", "predicted_table_ids", "table_ids",
                "retrieved_table_ids", "top_table_ids", "ranked_table_ids",
                "pred_tables", "predicted_tables", "tables", "retrieved_tables",
                "top_tables", "table_predictions", "ranked_tables",
            ) if key in row),
            [],
        )

    database = explicit_database(row)
    table_ids = []
    for value in tables[:k]:
        table_db, table = split_table_id(value)
        if table:
            table_ids.append(f"{table_db or database}{SEP}{table}" if table_db or database else table)
    return database, table_ids


def load_dbcopilot(row, k):
    schemas = row.get("pred_schemas") or []
    database = normalize(schemas[0].get("database")) if schemas else None
    table_ids = []
    for schema in schemas:
        if not isinstance(schema, dict) or not schema.get("database"):
            continue

        for table_name in schema.get("tables") or []:
            table_id = normalize_table_id(f"{schema['database']}{SEP}{table_name}")
            if table_id and table_id not in table_ids:
                table_ids.append(table_id)
    return database, table_ids[:k]


def load_qgpt(row, k):
    stored = row.get("top_k_predictions")
    if isinstance(stored, dict):
        tables = stored.get(str(k), stored.get(k))
        if tables is None:
            choices = sorted((int(key), value) for key, value in stored.items() if str(key).isdigit())
            tables = next((value for stored_k, value in choices if stored_k >= k), choices[-1][1] if choices else [])
    else:
        tables = []
        for hit in row.get("results") or []:
            entity = hit.get("entity") or {}
            tables.append(entity.get("FileName", entity.get("SheetName")))
    return None, normalize_table_list(tables)[:k]


def load_predictions(path, method, k):
    """Load any method into the common structure used by metric calculation."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise ValueError(f"Prediction file must contain a JSON list: {path}")

    method = method.lower()
    predictions = []
    for row in data:
        if method == "ours":
            if isinstance(row, dict):
                database, table_ids = load_ours(row, k)
            else:
                database, table_ids = None, normalize_table_list(row)[:k]
        elif method == "dbcopilot":
            database, table_ids = load_dbcopilot(
                row if isinstance(row, dict) else {}, k
            )
        elif method == "iterjar":
            database, table_ids = None, normalize_table_list(row)[:k]
        elif method == "core-t":
            # CORE-T's metric loader preserves duplicates until after DB voting.
            database = None
            table_ids = [str(value) for value in row if str(value).strip()][:k] if isinstance(row, list) else []
        elif method == "qgpt":
            database, table_ids = load_qgpt(row if isinstance(row, dict) else {}, k)
        else:
            raise ValueError(f"Unknown method: {method}")

        database = normalize(database) or majority_vote_database(table_ids)
        final_ids = []
        for table_id in table_ids:
            table_db, table = split_table_id(table_id)
            if table and database and (table_db is None or table_db == database):
                full_id = f"{database}{SEP}{table}"
                if full_id not in final_ids:
                    final_ids.append(full_id)

        predictions.append({
            "database": database,
            "retrieved_table_ids": [normalize_table_id(value) for value in table_ids if normalize_table_id(value)],
            "table_ids": final_ids,
            "tables": [split_table_id(table_id)[1] for table_id in final_ids],
        })

    return predictions
