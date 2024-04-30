/**
 * @Author: Bi Ying
 * @Date:   2023-05-08 15:37:42
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-29 11:33:10
 */
'use strict';
import { message } from 'ant-design-vue'

export function hasShowFields(node) {
  let hasShow = false
  Object.keys(node.data.template).forEach(key => {
    if (node.data.template[key].show) {
      hasShow = true
    }
  })
  return hasShow
}

export class DAG {
  constructor() {
    this.nodes = new Set();
    this.edges = {};
  }

  add_node(node) {
    this.nodes.add(node);
    if (!(node in this.edges)) {
      this.edges[node] = new Set();
    }
  }

  add_edge(start, end) {
    if (!this.nodes.has(start)) {
      this.add_node(start);
    }
    if (!this.nodes.has(end)) {
      this.add_node(end);
    }
    this.edges[start].add(end);
  }

  get_parents(node) {
    let parents = [];
    for (const [start, ends] of Object.entries(this.edges)) {
      if (ends.has(node)) {
        parents.push(start);
      }
    }
    return parents;
  }

  get_children(node) {
    return Array.from(this.edges[node]);
  }

  get_all_nodes() {
    return Array.from(this.nodes);
  }

  topological_sort() {
    let in_degree = {};
    for (const node of this.nodes) {
      in_degree[node] = 0;
    }
    for (const [start, ends] of Object.entries(this.edges)) {
      for (const end of ends) {
        in_degree[end] += 1;
      }
    }

    let queue = Object.keys(in_degree).filter(node => in_degree[node] == 0);

    let result = [];
    while (queue.length > 0) {
      let node = queue.shift();
      result.push(node);
      for (const child of this.edges[node]) {
        in_degree[child] -= 1;
        if (in_degree[child] == 0) {
          queue.push(child);
        }
      }
    }

    if (result.length != this.nodes.size) {
      throw new Error("The graph contains cycles");
    }

    return result;
  }
}

export const checkWorkflowDAG = (workflowData) => {
  const result = {
    noCycle: true,
    noIsolatedNodes: true,
  }
  let dag = new DAG()
  workflowData.data.nodes.forEach((node) => {
    if (node.category != 'triggers' && node.category != 'assistedNodes') {
      dag.add_node(node.id)
    }
  })
  workflowData.data.edges.forEach((edge) => {
    dag.add_edge(edge.source, edge.target)
  })
  try {
    dag.topological_sort()
    result.noCycle = true
  } catch (e) {
    result.noCycle = false
  }

  const nodes = workflowData.data.nodes.filter((node) => node.category != 'triggers' && node.category != 'assistedNodes').map((node) => node.id)
  const edges = workflowData.data.edges
  const adjacencyList = {}

  // 构建邻接表
  nodes.forEach(node => adjacencyList[node] = [])
  edges.forEach(edge => {
    adjacencyList[edge.source].push(edge.target)
    adjacencyList[edge.target].push(edge.source)
  })

  const visited = new Set()

  // 深度优先搜索
  const dfs = (node) => {
    visited.add(node)
    adjacencyList[node].forEach(neighbor => {
      if (!visited.has(neighbor)) {
        dfs(neighbor)
      }
    })
  }

  let numberOfConnectedComponents = 0
  nodes.forEach(node => {
    if (!visited.has(node)) {
      numberOfConnectedComponents += 1
      dfs(node)
    }
  })

  // 存在一个以上的连通分量，则认为有孤岛节点
  if (numberOfConnectedComponents > 1) {
    result.noIsolatedNodes = false
  } else {
    result.noIsolatedNodes = true
  }
  return result
}

export const nonFormItemsTypes = ["typography-paragraph"]

export const getUIDesignFromWorkflow = (workflowData) => {
  let inputFields = workflowData.data?.ui?.inputFields || []
  let unusedInputFields = JSON.parse(JSON.stringify(inputFields))
  let outputNodes = workflowData.data?.ui?.outputNodes || []
  let unusedOutputNodes = JSON.parse(JSON.stringify(outputNodes))
  let triggerNodes = workflowData.data?.ui?.triggerNodes || []
  let unusedTriggerNodes = JSON.parse(JSON.stringify(triggerNodes))
  let workflowInvokeOutputNodes = []

  workflowData.data.nodes.forEach((node) => {
    if (node.category == 'triggers') {
      triggerNodes.push(node)
      const nodeIndex = unusedTriggerNodes.findIndex((n) => n.id == node.id)
      unusedTriggerNodes.splice(nodeIndex, 1)
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
      } else if (node.type == 'Mermaid') {
        if (!node.data.template.show_mermaid.value) {
          return
        }
      } else if (node.type == 'Echarts') {
        if (!node.data.template.show_echarts.value) {
          return
        }
      } else if (node.field_type == 'typography-paragraph') {

      } else if (node.type == 'WorkflowInvokeOutput') {
        workflowInvokeOutputNodes.push(node)
        return
      } else if (node.type == 'Html') {

      } else {
        return
      }
      const prevNodeIndex = outputNodes.findIndex((n) => n.id == node.id)
      if (prevNodeIndex >= 0) {
        outputNodes.splice(prevNodeIndex, 1, node)
        const unusedNodeIndex = unusedOutputNodes.findIndex((n) => n.id == node.id)
        unusedOutputNodes.splice(unusedNodeIndex, 1)
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
            const unusedFieldIndex = unusedInputFields.findIndex((n) => n.nodeId == node.id && n.fieldName == field)
            unusedInputFields.splice(unusedFieldIndex, 1)
          } else {
            inputFields.push(nodeField)
          }
        }
      })
    }
  })

  // 删除没有用到的inputFields
  unusedInputFields.filter(field => !nonFormItemsTypes.includes(field.field_type)).forEach((field) => {
    const fieldIndex = inputFields.findIndex((n) => n.nodeId == field.nodeId && n.fieldName == field.fieldName)
    inputFields.splice(fieldIndex, 1)
  })
  // 删除没有用到的outputNodes
  unusedOutputNodes.filter(field => !nonFormItemsTypes.includes(field.field_type)).forEach((node) => {
    const nodeIndex = outputNodes.findIndex((n) => n.id == node.id)
    outputNodes.splice(nodeIndex, 1)
  })
  // 删除没有用到的triggerNodes
  unusedTriggerNodes.forEach((node) => {
    const nodeIndex = triggerNodes.findIndex((n) => n.id == node.id)
    triggerNodes.splice(nodeIndex, 1)
  })

  return {
    inputFields,
    outputNodes,
    triggerNodes,
    workflowInvokeOutputNodes,
  }
}

export function checkFieldsValid(inputFields) {
  let checkFieldsValid = true
  try {
    inputFields.forEach((field) => {
      let currentFieldValid = true
      if (field.field_type == 'checkbox') {
        return
      }
      if (!field.show) {
        return
      }
      if (!field.required) {
        return
      }

      if (field.field_type == 'number' && typeof field.value != 'number') {
        currentFieldValid = false
      } else if (field.field_type == 'select' && field.value.length === 0) {
        currentFieldValid = false
      } else if (!field.value && !field.value === 0) {
        currentFieldValid = false
      }
      if (!currentFieldValid) {
        message.error(t('workspace.workflowSpace.field_is_empty', { field: field.display_name }))
        checkFieldsValid = false
      }
    })
  } catch (errorInfo) {
    checkFieldsValid = false
  }
  return checkFieldsValid
}