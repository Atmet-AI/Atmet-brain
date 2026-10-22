"""Bounded pure Python recipes. No model, filesystem, network or shell access."""

from decimal import Context, Decimal, localcontext
import json
import re

RUNTIME_VERSION = 1
MAX_ROWS = 500


def records_input(inputs):
    if not isinstance(inputs, dict) or set(inputs) != {"records"}:
        raise ValueError("Provide a records object.")
    rows = inputs["records"]
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("Provide at most 500 records.")
    for row in rows:
        if not isinstance(row, dict) or not 1 <= len(row) <= 20:
            raise ValueError("Records need 1 to 20 fields.")
        if any(not isinstance(k, str) or not 1 <= len(k) <= 80
               or not isinstance(v, str) or len(v) > 500 for k, v in row.items()):
            raise ValueError("Record keys and values must be bounded strings.")
    if len(json.dumps(inputs, ensure_ascii=False)) > 30_000:
        raise ValueError("Input exceeds the recipe budget.")
    return rows


def validate_recipe(template, parameters):
    if not isinstance(parameters, dict):
        raise ValueError("Recipe parameters must be an object.")
    if template == "records.normalize":
        if set(parameters) != {"fields", "lowercase_fields", "sort_by", "deduplicate"}:
            raise ValueError("Invalid normalization parameters.")
        fields, lower = parameters["fields"], parameters["lowercase_fields"]
        if not isinstance(fields, list) or not 1 <= len(fields) <= 20 \
                or any(not isinstance(x, str) or not 1 <= len(x) <= 80 for x in fields) \
                or len(set(fields)) != len(fields):
            raise ValueError("Provide unique field names.")
        if not isinstance(lower, list) or any(x not in fields for x in lower) or len(set(lower)) != len(lower):
            raise ValueError("Lowercase fields must be selected fields.")
        if parameters["sort_by"] is not None and parameters["sort_by"] not in fields:
            raise ValueError("Sort by a selected field.")
        if type(parameters["deduplicate"]) is not bool:
            raise ValueError("deduplicate must be boolean.")
    elif template == "records.aggregate":
        if set(parameters) != {"group_by", "value_field"} \
                or any(not isinstance(v, str) or not 1 <= len(v) <= 80 for v in parameters.values()) \
                or parameters["group_by"] == parameters["value_field"]:
            raise ValueError("Provide different grouping and decimal-value fields.")
    else:
        raise ValueError("Unsupported recipe template.")


def recipe_inputs(template, parameters, inputs):
    validate_recipe(template, parameters)
    rows = records_input(inputs)
    required = set(parameters["fields"]) if template == "records.normalize" else {parameters["group_by"], parameters["value_field"]}
    for row in rows:
        if not required <= set(row):
            raise ValueError("A required field is missing.")
        if template == "records.aggregate" and not re.fullmatch(r"-?[0-9]{1,12}(?:\.[0-9]{1,2})?", row[parameters["value_field"]]):
            raise ValueError("Amounts must be decimal strings with at most two places.")
    return rows


def run_recipe(template, parameters, inputs):
    rows = recipe_inputs(template, parameters, inputs)
    if template == "records.normalize":
        result, seen = [], set()
        for row in rows:
            item = {k: row[k].strip().lower() if k in parameters["lowercase_fields"] else row[k].strip()
                    for k in parameters["fields"]}
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if not parameters["deduplicate"] or key not in seen:
                result.append(item)
            seen.add(key)
        if parameters["sort_by"] is not None:
            result.sort(key=lambda row: row[parameters["sort_by"]])
        return {"records": result}
    totals = {}
    with localcontext(Context(prec=28)):
        for row in rows:
            group = row[parameters["group_by"]]
            totals[group] = totals.get(group, Decimal(0)) + Decimal(row[parameters["value_field"]])
        return {"totals": [{"group": group, "total": format(total, ".2f")} for group, total in sorted(totals.items())],
                "count": len(rows)}
