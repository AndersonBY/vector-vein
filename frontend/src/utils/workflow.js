/**
 * @Author: Bi Ying
 * @Date:   2023-05-08 15:37:42
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-06-25 01:48:33
 */
'use strict';
import { message } from 'ant-design-vue'
import { workflowAPI } from "@/api/workflow"
import { hasShowFields } from '@/utils/util'

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

export const getUIDesignFromWorkflow = (workflowData) => {
  let inputFields = workflowData.data?.ui?.inputFields || []
  let outputNodes = workflowData.data?.ui?.outputNodes || []
  let triggerNodes = workflowData.data?.ui?.triggerNodes || []

  workflowData.data.nodes.forEach((node) => {
    if (node.category == 'triggers') {
      triggerNodes.push(node)
    } else if (node.category == 'outputs') {
      if (node.type == 'Text') {
        if (!node.data.template.text.show) {
          return
        }
      } else if (node.type == 'Audio') {
        if (!node.data.template.show_player.value) {
          return
        }
      } else if (node.type == 'Mindmap') {
        if (!node.data.template.show_mind_map.value) {
          return
        }
      } else if (node.field_type == 'typography-paragraph') {

      } else {
        return
      }
      const prevNodeIndex = outputNodes.findIndex((n) => n.id == node.id)
      if (prevNodeIndex >= 0) {
        outputNodes.splice(prevNodeIndex, 1, node)
      } else {
        outputNodes.push(node)
      }
    } else {
      if (!node.data.has_inputs && hasShowFields(node)) {
        return
      }
      Object.keys(node.data.template).forEach((field) => {
        if (node.data.template[field].show) {
          const nodeField = JSON.parse(JSON.stringify(node.data.template[field]))
          nodeField.category = node.category
          nodeField.nodeId = node.id
          nodeField.fieldName = field
          // 让 nodeField.value和node.data.template[field].value双向绑定
          Object.defineProperty(nodeField, 'value', {
            get() {
              return node.data.template[field].value
            },
            set(newValue) {
              node.data.template[field].value = newValue
            }
          })
          const prevFieldIndex = inputFields.findIndex((n) => n.nodeId == node.id && n.fieldName == field)
          if (prevFieldIndex >= 0) {
            inputFields.splice(prevFieldIndex, 1, nodeField)
          } else {
            inputFields.push(nodeField)
          }
        }
      })
    }
  })

  return {
    inputFields,
    outputNodes,
    triggerNodes,
  }
}