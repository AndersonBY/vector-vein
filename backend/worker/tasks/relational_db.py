# @Author: Bi Ying
# @Date:   2024-03-14 14:52:01
import re
import csv
from io import StringIO

import sqlparse

from models import (
    UserRelationalTable,
    UserRelationalDatabase,
)
from worker.tasks import task, timer
from utilities.workflow import Workflow
from utilities.relational_db import UserDatabaseControl

from utilities.ai_utils.chat_clients import create_chat_client


sql_block_pattern = re.compile(r"```.*?\n(?P<code>.*?)\n```", re.DOTALL)


def generate_create_table_sql(table_name, columns):
    base_sql = f"CREATE TABLE {table_name} ("
    column_definitions = []

    for column in columns:
        column_name = column["name"]
        column_type = column["type"]
        max_length = column.get("max_length")  # 使用get方法，这样如果没有max_length则会返回None
        if max_length:
            column_definitions.append(f"{column_name} {column_type}({max_length})")
        else:
            column_definitions.append(f"{column_name} {column_type}")

    columns_sql = ",\n  ".join(column_definitions)
    create_table_sql = f"{base_sql}\n  {columns_sql}\n);"

    return create_table_sql


def get_sample_data_sql(table_name: str):
    return f"SELECT * FROM {table_name} LIMIT 1;"


def format_cell(cell_content) -> str:
    if cell_content is None:
        return ""
    cell_content = str(cell_content).replace("\n", "<br>")
    cell_content = cell_content.replace("|", "&#124;")
    return cell_content


def format_output(records: list, output_type: str = "markdown"):
    if not isinstance(records, list):
        return ""
    if len(records) == 0:
        return ""
    if output_type == "markdown":
        has_header = isinstance(records[0], dict)
        output = ""
        if has_header:
            headers = [format_cell(column) for column in records[0].keys()]
            output += "|".join(headers) + "\n"
            output += "|".join(["---" for _ in headers]) + "\n"
            rows = [[format_cell(record[key]) for key in headers] for record in records]
        else:
            headers = [f"{i+1}" for i in range(len(records[0]))]
            output += "|".join(headers) + "\n"
            output += "|".join(["---" for _ in headers]) + "\n"
            rows = [[format_cell(value) for value in record] for record in records]
        output += "\n".join(["|".join(row) for row in rows])
        return output
    elif output_type == "csv":
        output = StringIO()
        has_header = isinstance(records[0], dict)
        if has_header:
            writer = csv.DictWriter(output, fieldnames=records[0].keys())

            writer.writeheader()
            for record in records:
                writer.writerow(record)

            return output.getvalue()
        else:
            writer = csv.writer(output)
            writer.writerows(records)
            return output.getvalue()


@task
@timer
def get_table_info(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    database = workflow.get_node_field_value(node_id, "database")
    tables = workflow.get_node_field_value(node_id, "tables")

    user_tables_qs = (
        UserRelationalTable.select().join(UserRelationalDatabase).where(UserRelationalDatabase.rid == database)
    )
    if tables:
        user_tables_qs = user_tables_qs.where(UserRelationalTable.tid.in_(tables))
    output_sql = "\n\n".join(
        [generate_create_table_sql(table.name, table.schema["columns"]) for table in user_tables_qs]
    )
    output_json = [
        {
            "name": table.name,
            "columns": table.schema["columns"],
        }
        for table in user_tables_qs
    ]

    workflow.update_node_field_value(node_id, "output_sql", output_sql)
    workflow.update_node_field_value(node_id, "output_json", output_json)
    return workflow.data


@task
@timer
def run_sql(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    database = workflow.get_node_field_value(node_id, "database")
    original_sqls = workflow.get_node_field_value(node_id, "sql")
    read_only = workflow.get_node_field_value(node_id, "read_only")
    include_column_names = workflow.get_node_field_value(node_id, "include_column_names")
    max_count = workflow.get_node_field_value(node_id, "max_count")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if isinstance(original_sqls, str):
        sqls = [original_sqls]
    else:
        sqls = original_sqls

    sql_statements = [sqlparse.format(sql, strip_comments=True, keyword_case="upper") for sql in sqls]
    split_statements = []
    for sql in sql_statements:
        split_statements.extend(sqlparse.split(sql))

    database = UserRelationalDatabase.get(UserRelationalDatabase.rid == database)

    user_db_ctl = UserDatabaseControl(database)
    results = user_db_ctl.run_sql(split_statements, read_only, include_column_names, max_count)

    if output_type == "list":
        output = results[0] if isinstance(original_sqls, str) else results
        workflow.update_node_field_value(node_id, "output", output)
    elif output_type in ("markdown", "csv"):
        outputs = [format_output(result, output_type) for result in results]
        output = outputs[0] if isinstance(original_sqls, str) else outputs
        workflow.update_node_field_value(node_id, "output", output)

    return workflow.data


@task
@timer
def smart_query(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    original_query = workflow.get_node_field_value(node_id, "query")
    model = workflow.get_node_field_value(node_id, "model")
    database = workflow.get_node_field_value(node_id, "database")
    tables = workflow.get_node_field_value(node_id, "tables")
    use_sample_data = workflow.get_node_field_value(node_id, "use_sample_data")
    include_column_names = workflow.get_node_field_value(node_id, "include_column_names")
    max_count = workflow.get_node_field_value(node_id, "max_count")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if isinstance(original_query, str):
        queries = [original_query]
    else:
        queries = original_query

    backend, model = model.split("/")

    user_tables_qs = (
        UserRelationalTable.select().join(UserRelationalDatabase).where(UserRelationalDatabase.rid == database)
    )
    if tables:
        user_tables_qs = user_tables_qs.where(UserRelationalTable.tid.in_(tables))
    create_table_sql = "\n\n".join(
        [generate_create_table_sql(table.name, table.schema["columns"]) for table in user_tables_qs]
    )

    database = UserRelationalDatabase.get(UserRelationalDatabase.rid == database)
    user_db_ctl = UserDatabaseControl(database)

    sample_datas = []
    if use_sample_data:
        sample_data_sqls = [get_sample_data_sql(table.name) for table in user_tables_qs]
        results = [
            user_db_ctl.run_sql(
                sql_script=sample_data_sql,
                read_only=True,
                include_column_names=False,
                max_count=10,
            )
            for sample_data_sql in sample_data_sqls
        ]
        sample_datas = [
            f"{user_tables_qs[index].name} sample data:\n{result['data'][0]['records'][0]}"
            for index, result in enumerate(results)
        ]

    client = create_chat_client(backend=backend.lower(), model=model.lower(), stream=False)
    system_message = {
        "role": "system",
        "content": "As an expert in SQLite, you are expected to utilize your knowledge to craft SQL queries that are in strict adherence with SQLite syntax standards when responding to inquiries.",
    }

    llm_generated_sqls = []
    sql_statements = []
    for query in queries:
        if use_sample_data:
            sample_datas_str = "\n\n".join(sample_datas)
            user_message = (
                f"The table structure is as follows:\n```sql\n{create_table_sql}\n```\n\n"
                f"{sample_datas_str}\n"
                f"Please write the SQL in strict adherence with SQLite syntax standards to answer the question: `{query}`\n Do not explain."
            )
        else:
            user_message = (
                f"The table structure is as follows:\n```sql\n{create_table_sql}\n```\n\n"
                f"Please write the SQL in strict adherence with SQLite syntax standards to answer the question: `{query}`\n Do not explain."
            )

        messages = [system_message, {"role": "user", "content": user_message}]
        response = client.create_completion(messages=messages, temperature=0.2)
        content = response["content"]
        sql_block_search = sql_block_pattern.search(content)
        if sql_block_search:
            content = sql_block_search.group("code")

        sql_statements.append(content.strip())
        llm_generated_sqls.append(content.strip())

    sql_statements = [sqlparse.format(sql, strip_comments=True, keyword_case="upper") for sql in sql_statements]
    split_statements = []
    for sql in sql_statements:
        split_statements.extend(sqlparse.split(sql))

    results = [
        user_db_ctl.run_sql(
            sql_script=split_statement,
            read_only=True,
            include_column_names=include_column_names,
            max_count=max_count,
        )["data"][0]["records"]
        for split_statement in split_statements
    ]

    if output_type == "list":
        output = results[0] if isinstance(original_query, str) else results
        workflow.update_node_field_value(node_id, "output", output)
    elif output_type in ("markdown", "csv"):
        outputs = [format_output(result, output_type) for result in results]
        output = outputs[0] if isinstance(original_query, str) else outputs
        workflow.update_node_field_value(node_id, "output", output)

    output_query_sql = llm_generated_sqls[0] if isinstance(original_query, str) else llm_generated_sqls
    workflow.update_node_field_value(node_id, "output_query_sql", output_query_sql)

    return workflow.data
