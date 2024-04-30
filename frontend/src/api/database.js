/**
 * @Author: Bi Ying
 * @Date:   2023-02-22 12:26:46
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-30 12:05:49
 */
import baseAPI from './base'

export async function databaseAPI(action, parameter) {
  return await baseAPI(`database__${action}`, parameter)
}

export async function databaseObjectAPI(action, parameter) {
  return await baseAPI(`database_object__${action}`, parameter)
}

export async function relationalDatabaseAPI(action, parameter) {
  return await baseAPI(`relational_database__${action}`, parameter)
}

export async function relationalDatabaseTableAPI(action, parameter) {
  return await baseAPI(`relational_database_table__${action}`, parameter)
}

export async function relationalDatabaseTableRecordAPI(action, parameter) {
  return await baseAPI(`relational_database_table_record__${action}`, parameter)
}