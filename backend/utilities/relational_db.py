# @Author: Bi Ying
# @Date:   2024-04-30 02:31:17
import json
import sqlite3
import traceback
from pathlib import Path
from datetime import datetime

import sqlparse
import pandas as pd

from models import UserRelationalDatabase, UserRelationalTable, Status
from utilities.print_utils import mprint_error


def get_table_names(conn: sqlite3.Connection):
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    return tables


def get_row_count_by_table(conn: sqlite3.Connection, table_name: str) -> int:
    cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    count = cursor.fetchone()[0]
    return count


def get_schema_from_table(file_path: str | Path, is_excel: bool):
    if is_excel:
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    # 创建一个空列表用于存储结果
    columns_info = []

    # 定义一个函数，用于将pandas的数据类型转换为SQL数据类型，并计算最大长度
    def pandas_type_to_sql_type_and_length(column_series):
        if pd.api.types.is_integer_dtype(column_series):
            return "INTEGER", None
        elif pd.api.types.is_float_dtype(column_series):
            return "REAL", None
        elif pd.api.types.is_string_dtype(column_series):
            # 先确保所有的数据都被转换为字符串
            str_column = column_series.fillna("").astype(str)
            # 计算转换后的字符串的最大长度
            max_length = int(str_column.str.len().max())
            if max_length > 512:
                return "TEXT", None
            else:
                return "VARCHAR", max_length
        elif pd.api.types.is_bool_dtype(column_series):
            return "BOOLEAN", None
        elif pd.api.types.is_datetime64_any_dtype(column_series):
            return "DATETIME", None
        else:
            # 对于未知类型，将其视为字符串处理
            str_column = column_series.fillna("").astype(str)
            max_length = int(str_column.str.len().max())
            return "VARCHAR", max_length if max_length <= 512 else None

    # 遍历DataFrame的列
    for column in df.columns:
        sql_type, max_length = pandas_type_to_sql_type_and_length(df[column])
        # 将列名、推断的SQL数据类型及最大长度存入字典
        column_info = {"name": column.replace(" ", "_"), "type": sql_type, "max_length": max_length}
        # 将字典添加到列表中
        columns_info.append(column_info)

    return columns_info


def get_schema_from_sql(sql_statement: str):
    # 连接到SQLite内存数据库
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # 执行SQL语句创建表
    cursor.executescript(sql_statement)

    # 获取表格结构信息
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';")
    tables = cursor.fetchall()

    result = []
    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        column_info = []
        for column in columns:
            column_name = column[1]
            column_type = column[2]
            max_length = None
            if "(" in column_type:
                column_type, max_length = column_type.split("(")
                max_length = int(max_length[:-1])

            column_info.append(
                {"name": column_name.replace(" ", "_"), "type": column_type.strip(), "max_length": max_length}
            )

        result.append({"table_name": table_name, "columns": column_info})

    # 关闭数据库连接
    conn.close()

    return result


def generate_create_table_sql(table_name, columns_info):
    column_defs = []
    for column in columns_info:
        column_name = column["name"]
        column_type = column["type"]
        max_length = column["max_length"]

        if max_length is not None:
            column_def = f'"{column_name}" {column_type}({max_length})'
        else:
            column_def = f'"{column_name}" {column_type}'

        column_defs.append(column_def)

    column_defs_str = ", ".join(column_defs)
    create_table_sql = f'CREATE TABLE "{table_name}" ({column_defs_str});'

    return create_table_sql


def create_from_table(
    file_path: str | Path,
    table_name: str,
    db_path: str,
    columns_info: list,
    is_excel: bool = True,
):
    if is_excel:
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    df.columns = df.columns.str.replace(" ", "_")

    conn = sqlite3.connect(db_path)

    create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ('
    for column_info in columns_info:
        column_name = column_info["name"]
        column_type = column_info["type"]
        max_length = column_info["max_length"]
        if max_length:
            create_table_sql += f'"{column_name}" {column_type}({max_length}), '
        else:
            create_table_sql += f'"{column_name}" {column_type}, '
    create_table_sql = create_table_sql.rstrip(", ") + ")"

    conn.execute(create_table_sql)

    df.to_sql(table_name, conn, if_exists="append", index=False)

    conn.commit()
    conn.close()


def create_from_sql(
    db_path: str,
    sql_statement: str,
):
    # 建立与SQLite数据库的连接
    conn = sqlite3.connect(db_path)

    # 执行CREATE TABLE语句
    conn.executescript(sql_statement)

    # 提交更改并关闭连接
    conn.commit()
    conn.close()


def create_relational_database_table(
    table: UserRelationalTable,
    add_method: str,
    file: str | None = None,
    sql_statement: str | None = None,
):
    print(table, add_method, file, sql_statement)
    database = table.database

    table_name = None
    columns_info = None

    if add_method == "table_file" and file is not None:
        table_name = table.name
        columns_info = table.schema["columns"]
    elif add_method == "manual":
        sql_statement = generate_create_table_sql(
            table_name=table.name,
            columns_info=table.schema["columns"],
        )
    elif add_method == "sql" and sql_statement is not None:
        pass
    else:
        raise ValueError("Invalid add method")

    created = False
    try:
        if file is not None:
            if not file.endswith(".sql"):
                is_excel = file.endswith((".xlsx", ".xls"))
                create_from_table(file, table_name, database.database_path, columns_info, is_excel)
                created = True
            else:
                sql_statement = Path(file).read_text()
                create_from_sql(database.database_path, sql_statement)
                created = True
        elif sql_statement is not None:
            create_from_sql(database.database_path, sql_statement)
            created = True

        if created:
            database.database_file_last_modified = datetime.now()
            database.save()

            conn = sqlite3.connect(database.database_path)
            table_names = get_table_names(conn)
            for table_name in table_names:
                table_qs = UserRelationalTable.select().where(
                    UserRelationalTable.name == table_name, UserRelationalTable.database == database
                )
                if not table_qs.exists():
                    continue

                table = table_qs.first()
                if table.status == Status.PROCESSING:
                    table.current_rows = get_row_count_by_table(conn, table_name)
                    table.status = Status.VALID
                    table.save()

            return True
        else:
            table.status = Status.INVALID
            table.save()
            return False
    except Exception as e:
        mprint_error(f"Failed to create table {table.tid.hex}: {e}")
        mprint_error(traceback.format_exc())
        table.status = Status.INVALID
        table.save()
        return False


class UserDatabaseControl:
    def __init__(self, db: UserRelationalDatabase | str):
        if isinstance(db, str):
            self.db = UserRelationalDatabase.get(UserRelationalDatabase.rid == db)
        else:
            self.db = db

    def get(
        self,
        table_name: str,
        page_num: int,
        page_size: int,
        sort_field: str,
        sort_order: str,
    ):
        if sort_field:
            sort_field = f"ORDER BY \"{sort_field}\" {'DESC' if sort_order == 'descend' else 'ASC'}"
        else:
            sort_field = ""

        connection = sqlite3.connect(self.db.database_path)
        connection.row_factory = sqlite3.Row  # 设置行工厂以访问列信息
        cursor = connection.cursor()
        cursor.execute(
            f'SELECT *, rowid FROM "{table_name}" {sort_field} LIMIT {page_size} OFFSET {(page_num - 1) * page_size}'
        )
        records = [dict(row) for row in cursor.fetchall()]  # 将每条记录转换为字典形式
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        total = cursor.fetchone()[0]
        connection.close()
        return {
            "records": records,
            "total": total,
        }

    def get_table_max_rows(self, table_name: str) -> int:
        if not Path(self.db.database_path).exists():
            return 0
        try:
            connection = sqlite3.connect(self.db.database_path)
            cursor = connection.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            result = cursor.fetchone()
            connection.close()
            return result[0]
        except Exception as e:
            mprint_error(f"database {self.db.rid.hex} failed to get table max rows: {e}")
            return 0

    def set_table_max_rows(self, table_name: str, max_rows: int):
        table = UserRelationalTable.get(
            UserRelationalTable.database == self.db, UserRelationalTable.name == table_name
        )
        table.current_rows = max_rows
        table.save()

    def delete_table(self, table_name: str):
        if not Path(self.db.database_path).exists():
            return -1

        try:
            connection = sqlite3.connect(self.db.database_path)
            cursor = connection.cursor()
            cursor.execute(f'DROP TABLE "{table_name}"')
            connection.commit()
            connection.close()
            return 0
        except Exception as e:
            mprint_error(f"database {self.db.rid.hex} failed to delete table: {e}")
            return -1

    def update(self, table_name: str, records: list):
        if not Path(self.db.database_path).exists():
            return -1

        try:
            connection = sqlite3.connect(self.db.database_path)
            cursor = connection.cursor()
            for record in records:
                rowid = record.pop("rowid")
                update_query = 'UPDATE "{}" SET {} WHERE rowid = ?'.format(
                    table_name, ", ".join('"{}"=?'.format(k) for k in record)
                )
                cursor.execute(update_query, list(record.values()) + [rowid])
            connection.commit()
            connection.close()
            table_max_rows = self.get_table_max_rows(table_name)
            self.set_table_max_rows(table_name, table_max_rows)
            return table_max_rows
        except Exception as e:
            mprint_error(f"database {self.db.rid.hex} failed to update: {e}")
            return -1

    def delete(self, table_name: str, records: list):
        if not Path(self.db.database_path).exists():
            return -1

        try:
            connection = sqlite3.connect(self.db.database_path)
            cursor = connection.cursor()
            for rowid in records:
                delete_query = 'DELETE FROM "{}" WHERE rowid = ?'.format(table_name)
                cursor.execute(delete_query, [rowid])
            connection.commit()
            connection.close()
            table_max_rows = self.get_table_max_rows(table_name)
            self.set_table_max_rows(table_name, table_max_rows)
            return table_max_rows
        except Exception as e:
            mprint_error(f"database {self.db.rid.hex} failed to delete: {e}")
            return -1

    def add(self, table_name: str, records: list):
        if not Path(self.db.database_path).exists():
            return -1

        table_max_rows = self.get_table_max_rows(table_name)

        if table_max_rows + len(records) > self.max_row_quota:
            mprint_error(f"database {self.db.rid.hex} is too large")
            return -1

        try:
            connection = sqlite3.connect(self.db.database_path)
            cursor = connection.cursor()
            for record in records:
                insert_query = 'INSERT INTO "{}" ({}) VALUES ({})'.format(
                    table_name,
                    ", ".join(f'"{k}"' for k in record),
                    ", ".join("?" for _ in record),
                )
                cursor.execute(insert_query, list(record.values()))
            connection.commit()
            connection.close()
            table_max_rows = self.get_table_max_rows(table_name)
            self.set_table_max_rows(table_name, table_max_rows)
            return table_max_rows
        except Exception as e:
            mprint_error(f"database {self.db.rid.hex} failed to add: {e}")
            return -1

    def add_from_file(self, table_name: str, file: str):
        if not Path(self.db.database_path).exists():
            return -1

        try:
            if Path(file).suffix == ".csv":
                records = pd.read_csv(file).to_dict(orient="records")
            elif Path(file).suffix == ".xlsx":
                records = pd.read_excel(file).to_dict(orient="records")
            elif Path(file).suffix == ".json":
                with open(file, "r", encoding="utf8") as f:
                    records = json.load(f)

            return self.add(table_name, records)
        except Exception as e:
            mprint_error(f"database {self.db.rid.hex} failed to add from file: {e}")
            return -1

    def run_sql(
        self,
        sql_script: str,
        read_only: bool = False,
        include_column_names: bool = True,
        max_count: int | None = None,
    ):
        if not Path(self.db.database_path).exists():
            return {
                "status": 500,
                "msg": "Database not found",
            }

        sql_script = sqlparse.format(sql_script, strip_comments=True)
        sql_statements = sqlparse.split(sql_script)
        results = []

        connection = sqlite3.connect(self.db.database_path)
        if include_column_names:
            connection.row_factory = sqlite3.Row

        cursor = connection.cursor()
        cursor.execute("BEGIN TRANSACTION;")

        try:
            for sql_statement in sql_statements:
                try:
                    sql_type = sqlparse.parse(sql_statement)[0].get_type()

                    cursor.execute(sql_statement)
                    if sql_type == "SELECT":
                        if max_count:
                            data = cursor.fetchmany(size=max_count)
                        else:
                            data = cursor.fetchall()
                        columns = [description[0] for description in cursor.description]
                        if include_column_names:
                            records = [dict(row) for row in data]
                        else:
                            records = data
                        results.append(
                            {
                                "success": True,
                                "type": sql_type,
                                "columns": columns,
                                "records": records,
                            }
                        )
                    else:
                        results.append({"success": True, "type": sql_type, "rows": cursor.rowcount})
                except Exception as e:
                    results.append(
                        {
                            "success": False,
                            "msg": f"Failed to run {sql_statement}: {e}",
                        }
                    )

            if read_only:
                connection.rollback()
            else:
                connection.commit()

        except Exception as e:
            connection.rollback()
            mprint_error(f"Failed to run sql: {e}")
            results = []
        finally:
            connection.close()

        return {
            "status": 200,
            "data": results,
        }
