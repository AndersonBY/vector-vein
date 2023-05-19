/**
 * @Author: Bi Ying
 * @Date:   2023-02-22 12:26:46
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-15 23:00:37
 */
export async function workflowAPI(action, parameter) {
  return await window.pywebview.api[`workflow__${action}`](parameter)
}

export async function workflowScheduleTriggerAPI(action, parameter) {
  return await window.pywebview.api[`workflow_schedule_trigger__${action}`](parameter)
}

export async function workflowTemplateAPI(action, parameter) {
  return await window.pywebview.api[`workflow_template__${action}`](parameter)
}

export async function workflowTagAPI(action, parameter) {
  return await window.pywebview.api[`workflow_tag__${action}`](parameter)
}

export async function workflowRunRecordAPI(action, parameter) {
  return await window.pywebview.api[`workflow_run_record__${action}`](parameter)
}