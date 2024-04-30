# @Author: Bi Ying
# @Date:   2024-04-29 23:34:39
import sqlite3
import traceback
from pathlib import Path
from datetime import datetime

from models import (
    Status,
    DatabaseStatus,
    model_serializer,
    UserRelationalTable,
    UserRelationalDatabase,
)
from api.utils import get_user_object_general
from utilities.relational_db import (
    UserDatabaseControl,
    get_schema_from_sql,
    get_schema_from_table,
    create_relational_database_table,
)
from utilities.print_utils import mprint_error


class RelationalDatabaseAPI:
    name = "relational_database"

    def get(self, payload):
        status, msg, database = get_user_object_general(
            UserRelationalDatabase,
            rid=payload.get("rid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        database = model_serializer(database)
        response = {"status": 200, "msg": "success", "data": database}
        return response

    def update(self, payload):
        status, msg, database = get_user_object_general(
            UserRelationalDatabase,
            rid=payload.get("rid", None),
        )
        if status != 200:
            return {"status": status, "msg": msg, "data": {}}
        database.name = payload.get("name", database.name)
        database.save()
        return {"status": 200, "msg": msg}

    def list(self, payload):
        databases = UserRelationalDatabase.select().order_by("create_time")
        databases_list = model_serializer(databases, many=True)
        response = {"status": 200, "msg": "success", "data": databases_list}
        return response

    def create(self, payload):
        database: UserRelationalDatabase = UserRelationalDatabase.create(
            name=payload.get("name", ""),
        )

        database_path = Path(self.data_path) / "relational_db" / f"{database.rid.hex}.db"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(database_path.as_posix())
        conn.close()

        database.database_path = database_path.as_posix()
        database.database_file_last_modified = datetime.now()
        database.status = DatabaseStatus.VALID
        database.save()
        database = model_serializer(database)
        response = {"status": 200, "msg": "success", "data": database}
        return response

    def delete(self, payload):
        status, msg, database = get_user_object_general(
            UserRelationalDatabase,
            rid=payload.get("rid", None),
        )
        if status != 200:
            return {"status": status, "msg": msg, "data": {}}

        database_path = Path(database.database_path)
        if database_path.exists():
            database_path.unlink()

        database.delete_instance()
        return {"status": 200, "msg": "success", "data": {}}

    def run_sql(self, payload):
        status, msg, database = get_user_object_general(
            UserRelationalDatabase,
            rid=payload.get("rid"),
        )
        if status != 200:
            return {"status": status, "msg": msg, "data": {}}

        user_db_ctl = UserDatabaseControl(database)
        run_result = user_db_ctl.run_sql(payload.get("sql"))
        return dict(
            status=run_result["status"],
            msg=run_result.get("msg", ""),
            data=run_result.get("data", {}),
        )


class RelationalDatabaseTableAPI:
    name = "relational_database_table"

    def get(self, payload):
        status, msg, user_object = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid", None),
        )
        if status != 200:
            return {"status": status, "msg": msg, "data": {}}
        user_object = model_serializer(user_object)
        return {"status": 200, "msg": "success", "data": user_object}

    def create(self, payload):
        rid = payload.get("rid")
        add_method = payload.get("add_method")
        sql_statement = payload.get("sql_statement")
        table_schema = payload.get("table_schema")

        status, msg, relational_database = get_user_object_general(
            UserRelationalDatabase,
            rid=rid,
        )
        if status != 200:
            return dict(status=status, msg=msg)

        all_table_names = [table["table_name"] for table in table_schema]
        if (
            UserRelationalTable.select()
            .where(UserRelationalTable.database == relational_database, UserRelationalTable.name.in_(all_table_names))
            .exists()
        ):
            return dict(status=400, msg="table name already exists")

        for schema in table_schema:
            table = UserRelationalTable.create(
                database=relational_database,
                name=schema["table_name"],
                status=Status.PROCESSING,
                schema={"columns": schema["columns"]},
            )
            if add_method == "table_file":
                create_relational_database_table(
                    table=table,
                    add_method=add_method,
                    file=schema["source"],
                    sql_statement=sql_statement,
                )
            elif add_method == "manual" or add_method == "sql":
                create_relational_database_table(
                    table=table,
                    add_method=add_method,
                    sql_statement=sql_statement,
                )

        return dict(status=200, data={"tid": table.tid.hex})

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "create_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = f"-{sort_field}" if sort_order == "descend" else sort_field
        user_tables = (
            UserRelationalTable.select()
            .join(UserRelationalDatabase)
            .where(UserRelationalDatabase.rid == payload.get("rid", None))
        )
        status = payload.get("status")
        if status:
            status = [status] if isinstance(status, str) else status
            user_tables = user_tables.where(UserRelationalTable.status.in_(status))
        tids = payload.get("tids")
        if tids:
            user_tables = user_tables.where(UserRelationalTable.tid.in_(tids))
        user_tables_count = user_tables.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        user_tables = user_tables.order_by(sort_field).offset(offset).limit(limit)
        user_tables_list = model_serializer(user_tables, many=True)
        response = {
            "status": 200,
            "msg": "success",
            "data": {
                "tables": user_tables_list,
                "total": user_tables_count,
                "page_size": page_size,
                "page": page_num,
            },
        }
        return response

    def update(self, payload):
        status, msg, user_object = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid"),
        )
        if status != 200:
            return {"status": status, "msg": msg, "data": {}}
        user_object.title = payload.get("title", "")
        user_object.info = payload.get("info", {})
        user_object.save()
        return {"status": 200, "msg": "success", "data": {}}

    def delete(self, payload):
        status, msg, table = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid", None),
        )
        if status != 200:
            return {"status": status, "msg": msg, "data": {}}
        user_db_ctl = UserDatabaseControl(table.database)
        user_db_ctl.delete_table(table.name)
        table.delete_instance()
        return {"status": 200, "msg": "success", "data": {}}

    def get_table_schema(self, payload):
        if payload.get("files"):
            try:
                result = []
                for file_path in payload.get("files"):
                    file = Path(file_path)
                    if file.suffix == ".sql":
                        sql_statement = file.read_text()
                        result.extend(get_schema_from_sql(sql_statement))
                    else:
                        table_name = file.stem
                        is_excel = file.suffix.endswith((".xlsx", ".xls"))
                        result.append(
                            {
                                "table_name": table_name,
                                "columns": get_schema_from_table(file, is_excel),
                                "source": file.as_posix(),
                            }
                        )
                table_schema = result
                return dict(status=200, data=table_schema)
            except Exception:
                mprint_error(traceback.format_exc())
                return dict(status=500, msg="Failed to get table schema")
        elif payload.get("sql_statement"):
            try:
                table_schema = get_schema_from_sql(payload.get("sql_statement"))
                return dict(status=200, data=table_schema)
            except Exception:
                mprint_error(traceback.format_exc())
                return dict(status=500, msg="Failed to get table schema")


class RelationalDatabaseTableRecordAPI:
    name = "relational_database_table_record"

    def list(self, payload):
        status, msg, user_table = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid"),
        )
        if status != 200:
            return dict(status=status, msg=msg)

        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field")
        sort_order = payload.get("sort_order", "descend")

        database = user_table.database
        user_db_ctl = UserDatabaseControl(database)
        result = user_db_ctl.get(
            table_name=user_table.name,
            page_num=page_num,
            page_size=page_size,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        return dict(
            status=200,
            msg="",
            data={
                "records": result["records"],
                "schema": user_table.schema,
                "total": result["total"],
                "page_size": page_size,
                "page": page_num,
            },
        )

    def update(self, payload):
        status, msg, user_table = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid"),
        )
        if status != 200:
            return dict(status=status, msg=msg)

        database = user_table.database
        user_db_ctl = UserDatabaseControl(database)
        update_result = user_db_ctl.update(user_table.name, payload.get("records", []))
        if update_result >= 0:
            return dict(status=200, data={"current_rows": update_result})
        else:
            return dict(status=500, msg="Failed to update records")

    def delete(self, payload):
        status, msg, user_table = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid"),
        )
        if status != 200:
            return dict(status=status, msg=msg)

        database = user_table.database
        user_db_ctl = UserDatabaseControl(database)
        delete_result = user_db_ctl.delete(user_table.name, payload.get("records", []))
        if delete_result >= 0:
            return dict(status=200, data={"current_rows": delete_result})
        else:
            return dict(status=500, msg="Failed to delete records")

    def add(self, payload):
        status, msg, user_table = get_user_object_general(
            UserRelationalTable,
            tid=payload.get("tid"),
        )
        if status != 200:
            return dict(status=status, msg=msg)

        add_method = payload.get("add_method")
        database = user_table.database
        user_db_ctl = UserDatabaseControl(database)
        if add_method == "manual":
            record = payload.get("record")
            add_result = user_db_ctl.add(user_table.name, [record])
        elif add_method == "file":
            file = payload.get("file")
            add_result = user_db_ctl.add_from_file(user_table.name, file)
        else:
            return dict(status=400, msg="invalid add method")

        if add_result >= 0:
            return dict(status=200, data={"current_rows": add_result})
        else:
            return dict(status=500, msg="Failed to add record")
