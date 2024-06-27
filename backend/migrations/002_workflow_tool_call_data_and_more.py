# @Author: Bi Ying
# @Date:   2024-06-06 14:51:37
"""Peewee migrations -- 002_workflow_tool_call_data_and_more.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    migrator.add_index("agent", "aid", unique=True)

    migrator.add_index("conversation", "cid", unique=True)

    migrator.add_index("message", "mid", unique=True)

    migrator.add_fields("workflow", tool_call_data=pw.TextField(default="{}"))

    migrator.add_fields(
        "workflowrunrecord",
        run_from=pw.CharField(default="WEB", max_length=16),
        source_message=pw.UUIDField(null=True),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_fields("workflowrunrecord", "run_from", "source_message")

    migrator.remove_fields("workflow", "tool_call_data")

    migrator.drop_index("message", "mid")

    migrator.drop_index("conversation", "cid")

    migrator.drop_index("agent", "aid")
