/**
 * @Author: Bi Ying
 * @Date:   2023-05-08 15:37:42
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-18 02:43:28
 */
'use strict';
import { message } from 'ant-design-vue'
import { workflowAPI } from "@/api/workflow"

export const getWorkflows = async (
  userWorkflowsStore,
  need_fast_access = false,
) => {
  const response = await workflowAPI('list', { need_fast_access: need_fast_access })
  if (response.status == 200) {
    const workflows = response.data.workflows.map(item => {
      item.create_time = new Date(item.create_time).toLocaleString()
      item.update_time = new Date(item.update_time).toLocaleString()
      return item
    })
    userWorkflowsStore.setUserWorkflows(workflows)
    const fastAccessWorkflows = response.data.fast_access_workflows.map(item => {
      item.create_time = new Date(item.create_time).toLocaleString()
      item.update_time = new Date(item.update_time).toLocaleString()
      return item
    })
    userWorkflowsStore.setUserWorkflows(fastAccessWorkflows, true)
    userWorkflowsStore.setUserWorkflowsTotal(response.data.total)
  } else {
    message.error(response.msg)
  }
}