"""Local JSON Schema validation. References never fetch network resources."""
from __future__ import annotations

import json

from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for
from referencing import Registry
from referencing.exceptions import NoSuchResource


def _deny_remote_reference(uri: str):
    raise NoSuchResource(ref=uri)


def make_validator(schema):
    if schema is None or schema == "":
        return None
    if isinstance(schema, str):
        schema = json.loads(schema)
    if not isinstance(schema, (dict, bool)):
        raise ValueError("Output schema must be a JSON Schema object or boolean")
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)
    return validator_type(schema, format_checker=FormatChecker(), registry=Registry(retrieve=_deny_remote_reference))


def _invalid_constant(value: str):
    raise ValueError(f"Invalid JSON constant: {value}")


def validate_output(content: str, validator):
    try:
        value = json.loads(content, parse_constant=_invalid_constant)
    except (ValueError, TypeError) as exc:
        raise ValueError("Output must be valid JSON without Markdown fences") from exc
    try:
        validator.validate(value)
    except ValidationError as exc:
        raise ValueError(f"Schema validation failed at {exc.json_path}: {exc.validator}") from exc
    return value
