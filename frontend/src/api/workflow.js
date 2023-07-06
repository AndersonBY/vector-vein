/**
 * @Author: Bi Ying
 * @Date:   2023-02-22 12:26:46
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-06 17:30:37
 */
import baseAPI from './base'

export async function workflowAPI(action, parameter) {
  return await baseAPI(`workflow__${action}`, parameter)
}

export async function workflowScheduleTriggerAPI(action, parameter) {
  return await baseAPI(`workflow_schedule_trigger__${action}`, parameter)
}

export async function workflowTemplateAPI(action, parameter) {
  return await baseAPI(`workflow_template__${action}`, parameter)
}

export async function workflowTagAPI(action, parameter) {
  return await baseAPI(`workflow_tag__${action}`, parameter)
}

export async function workflowRunRecordAPI(action, parameter) {
  return await baseAPI(`workflow_run_record__${action}`, parameter)
}