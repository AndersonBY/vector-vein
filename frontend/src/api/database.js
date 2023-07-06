/**
 * @Author: Bi Ying
 * @Date:   2023-02-22 12:26:46
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-06 17:23:32
 */
import baseAPI from './base'

export async function databaseAPI(action, parameter) {
  return await baseAPI(`database__${action}`, parameter)
}

export async function databaseObjectAPI(action, parameter) {
  return await baseAPI(`database_object__${action}`, parameter)
}
