/**
 * @Author: Bi Ying
 * @Date:   2023-02-22 12:26:46
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-16 19:50:03
 */
export async function databaseAPI(action, parameter) {
  return await window.pywebview.api[`database__${action}`](parameter)
}

export async function databaseObjectAPI(action, parameter) {
  return await window.pywebview.api[`database_object__${action}`](parameter)
}
