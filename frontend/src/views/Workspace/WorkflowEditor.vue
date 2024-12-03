<script setup>
import { ref, reactive, markRaw, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { v4 as uuidv4 } from 'uuid'
import { message } from 'ant-design-vue'
import { Left, Caution, Save, Code, Bug, LayoutFive, MenuFoldOne, MenuUnfoldOne } from '@icon-park/vue-next'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { useRoute, useRouter } from "vue-router"
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserSettingsStore } from "@/stores/userSettings"
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import { useUserRelationalDatabasesStore } from "@/stores/userRelationalDatabase"
import TagInput from '@/components/workspace/TagInput.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import CodeEditorModal from '@/components/CodeEditorModal.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import UIDesign from '@/components/workspace/UIDesign.vue'
import VueFlowStyleSettings from '@/components/workspace/VueFlowStyleSettings.vue'
import TagManage from '@/components/workspace/TagManage.vue'
import WorkflowUse from '@/components/workspace/WorkflowUse.vue'
import { ObjectHasher } from '@/utils/util'
import { nodeCategoryOptions } from "@/utils/common"
import { getUIDesignFromWorkflow, nonFormItemsTypes, checkWorkflowDAG } from '@/utils/workflow'
import { useLayout } from '@/utils/useLayout'
import { workflowAPI, workflowTemplateAPI, workflowRunRecordAPI } from "@/api/workflow"
import { databaseAPI, relationalDatabaseAPI } from "@/api/database"
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'

const { t, te } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const workflowId = ref('')
const activeTab = ref('canvas')
const tabs = reactive([
  {
    label: t('workspace.workflowEditor.workflow_info'),
    value: 'info',
  },
  {
    label: t('workspace.workflowEditor.workflow_canvas'),
    value: 'canvas',
  },
  {
    label: t('workspace.workflowEditor.workflow_ui_design'),
    value: 'ui_design',
  },
])

const collapsed = ref(false)
const sidebarHover = ref(false)
const onCollapse = (switchToCollapsed) => {
  collapsed.value = switchToCollapsed
}

let workflowOrTemplate = 'workflow'
let workflowOrTemplateAPI = null
let queryParam = {}

const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const userRelationalDatabasesStore = useUserRelationalDatabasesStore()
const userWorkflowsStore = useUserWorkflowsStore()
const userSettingsStore = useUserSettingsStore()
const { vueFlowStyleSettings, theme } = storeToRefs(userSettingsStore)
const useNodeMessages = useNodeMessagesStore()
const { nodeMessagesCount, nodeMessages } = storeToRefs(useNodeMessages)

const componentTheme = computed(() => theme.value == 'default' ? 'light' : 'dark')

const savedWorkflowHash = ref('')
const hasher = new ObjectHasher(['data.viewport', 'data.related_workflows'])
const currentWorkflow = ref({})
const elements = ref([])
const diagnosisRecord = ref(userWorkflowsStore.diagnosisRecord)
const diagnosisRecordId = ref(router.currentRoute.value.query.rid)

const onVueFlowStyleSettingsSave = () => {
  edges.value.forEach((edge) => {
    edge.type = vueFlowStyleSettings.value.edge.type
    edge.animated = vueFlowStyleSettings.value.edge.animated
    edge.style = vueFlowStyleSettings.value.edge.style
  })
  userSettingsStore.setVueFlowStyleSettings(vueFlowStyleSettings.value)
}

onUnmounted(() => {
  userWorkflowsStore.setDiagnosisRecord(null)
})

onMounted(async () => {
  if (diagnosisRecordId.value) {
    if (!diagnosisRecord.value) {
      const res = await workflowRunRecordAPI('get', { rid: diagnosisRecordId.value })
      diagnosisRecord.value = res.data
    }
  }
  if (route.path.startsWith('/workflow/editor/')) {
    workflowOrTemplate = 'workflow'
    workflowOrTemplateAPI = workflowAPI
    workflowId.value = route.params.workflowId
    queryParam = { wid: workflowId.value }
  } else {
    workflowOrTemplate = 'template'
    workflowOrTemplateAPI = workflowTemplateAPI
    workflowId.value = route.params.templateId
    queryParam = { tid: workflowId.value }
  }
  const getWorkflowRequest = workflowOrTemplateAPI('get', queryParam)
  const listVectorDbRequest = databaseAPI('list')
  const listRelationalDbRequest = relationalDatabaseAPI('list')
  const workflowResponse = await getWorkflowRequest
  const listVectorDbResponse = await listVectorDbRequest
  const listRelationalDbResponse = await listRelationalDbRequest

  if (listVectorDbResponse.status == 200) {
    userDatabasesStore.setUserDatabases(listVectorDbResponse.data)
  }
  if (listRelationalDbResponse.status == 200) {
    userRelationalDatabasesStore.setUserRelationalDatabases(listRelationalDbResponse.data)
  }
  if (workflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    await router.push({ name: 'WorkflowSpaceMain' })
    return
  }

  currentWorkflow.value = workflowResponse.data
  if (diagnosisRecord.value) {
    currentWorkflow.value.data = diagnosisRecord.value.data
  }
  currentWorkflow.value.data.nodes.forEach((node) => {
    if (diagnosisRecord.value) {
      node.data.debug = {
        run_time: diagnosisRecord.value.data?.node_run_time?.[node.id] ?? -1
      }
    }
    if (node.category == "vectorDb") {
      node.data.template.database.options = userDatabases.value.filter((database) => {
        return database.status == 'VALID'
      }).map((item) => {
        return {
          value: item.vid,
          label: item.name,
        }
      })
    }

    // 修复节点模板数据中的 condition 字段
    const nodeTemplateData = nodeTemplateCreators[node.type]()
    Object.entries(node.data.template).forEach(([key, value]) => {
      if (nodeTemplateData.template[key]?.condition) {
        value.condition = nodeTemplateData.template[key].condition
      }
    })
    // 创建一个新对象，按照 nodeTemplateData.template 的键的顺序来添加键值对
    const sortedTemplate = {}

    // 首先添加 nodeTemplateData.template 中定义的键
    Object.keys(nodeTemplateData.template).forEach(key => {
      if (node.data.template.hasOwnProperty(key)) {
        sortedTemplate[key] = node.data.template[key]
      }
    })

    // 然后添加那些在 nodeTemplateData.template 中不存在的键
    Object.keys(node.data.template).forEach(key => {
      if (!nodeTemplateData.template.hasOwnProperty(key)) {
        sortedTemplate[key] = node.data.template[key]
      }
    })

    // 更新 node.data.template 为新的排序后的对象
    node.data.template = sortedTemplate
  })
  currentWorkflow.value.tags = currentWorkflow.value.tags.map(tag => tag.tid)
  loading.value = false

  nextTick(() => {
    if (currentWorkflow.value.data.nodes.length == 0) {
      addNodeToCanvas('ButtonTrigger', { x: 100, y: 100 })
    }
    elements.value = [...currentWorkflow.value.data.nodes, ...currentWorkflow.value.data.edges]
    savedWorkflowHash.value = hasher.hash(currentWorkflow.value)
    if (currentWorkflow.value.data.viewport) {
      setViewport(currentWorkflow.value.data.viewport)
    }
  })
})

function getCleanWorkflowData(noShadow = true, noIgnored = false) {
  const { nodes, edges, viewport } = toObject()
  return {
    nodes: nodes.filter((node) => {
      if (noShadow && node.shadow) return false;
      if (noIgnored && node.ignored) return false;
      return true;
    }),
    edges: edges.filter((edge) => {
      if (noShadow && edge.shadow) return false;
      if (noIgnored && edge.ignored) return false;
      return true;
    }),
    viewport,
  }
}

const updateWorkflowData = () => {
  const workflowData = getCleanWorkflowData()
  currentWorkflow.value.data = {
    ...workflowData,
    ui: currentWorkflow.value.data.ui || {},
  }
}

const saveCheckModalOpen = ref(false)
const workflowCheckList = ref({
  hasInput: false,
  hasOutput: false,
  hasTrigger: false,
})
const saveWorkflowCheck = () => {
  workflowCheckList.value = {
    hasInput: false,
    hasOutput: false,
    hasTrigger: false,
    noCycle: false,
    noIsolatedNodes: false,
  }
  const workflowDAGStatus = checkWorkflowDAG({ data: getCleanWorkflowData(true, true) })
  workflowCheckList.value.noCycle = workflowDAGStatus.noCycle
  workflowCheckList.value.noIsolatedNodes = workflowDAGStatus.noIsolatedNodes
  const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
  const reactiveUIDesign = reactive(uiDesign)
  workflowCheckList.value.hasInput = reactiveUIDesign.inputFields.filter((inputField) => !nonFormItemsTypes.includes(inputField.field_type)).length > 0
  workflowCheckList.value.hasOutput = currentWorkflow.value.data.nodes.filter((node) => node.category == 'outputs').length > 0
  workflowCheckList.value.hasTrigger = reactiveUIDesign.triggerNodes.filter((node) => node.category == 'triggers').length > 0
  if (Object.values(workflowCheckList.value).some(val => val === false)) {
    saveCheckModalOpen.value = true
    return false
  }
  return true
}

const saving = ref(false)
const saveWorkflow = async () => {
  saving.value = true
  const uiDesign = currentWorkflow.value.data.ui || {}
  const workflowData = getCleanWorkflowData()
  currentWorkflow.value.data = {
    ...workflowData,
    ui: uiDesign,
  }
  const checkResult = saveWorkflowCheck()
  try {
    const response = await workflowOrTemplateAPI('update', {
      ...queryParam,
      ...currentWorkflow.value,
    })
    if (response.status == 200) {
      message.success({
        content: () => t('workspace.workflowSpace.save_success'),
        style: {
          marginTop: '60px',
        },
      })
      savedWorkflowHash.value = hasher.hash(currentWorkflow.value)
    } else if (response.status == 400) {
      message.error(t('workspace.workflowSpace.workflow_cant_invoke_itself'))
    } else {
      message.error(t('workspace.workflowSpace.save_failed'))
    }
    if (workflowOrTemplate == 'workflow') {
      userWorkflowsStore.updateUserWorkflow(currentWorkflow.value)
    }
  } catch (error) {
    console.error(error)
    message.error(t('workspace.workflowSpace.save_failed'))
  }
  saving.value = false
  return checkResult
}

const routerBack = async () => {
  if (workflowOrTemplate == 'workflow') {
    await router.push({ name: 'WorkflowUse', params: { workflowId: workflowId.value } })
  } else {
    await router.push({ name: 'WorkflowTemplate', params: { workflowTemplateId: workflowId.value } })
  }
}

const exitModalOpen = ref(false)
const saveAndExit = async () => {
  await saveWorkflow()
  await routerBack()
}
const exitNoSave = async () => {
  await routerBack()
}
const exitConfirm = () => {
  if (!!diagnosisRecordId.value) {
    routerBack()
  }
  const uiDesign = currentWorkflow.value.data.ui || {}
  const workflowData = getCleanWorkflowData()
  currentWorkflow.value.data = {
    ...workflowData,
    ui: uiDesign,
  }
  if (savedWorkflowHash.value != hasher.hash(currentWorkflow.value)) {
    exitModalOpen.value = true
  } else {
    routerBack()
  }
}

const {
  removeNodes,
  addNodes,
  addEdges,
  removeEdges,
  updateEdge,
  onConnect,
  toObject,
  findNode,
  fitView,
  setViewport,
  vueFlowRef,
  viewport,
  edges,
  nodes,
} = useVueFlow()
onConnect((params) => {
  const hasConnectedEdge = edges.value.some((edge) => {
    return !edge.ignored && edge.target === params.target && edge.targetHandle === params.targetHandle
  })
  if (hasConnectedEdge) {
    message.error(t('workspace.workflowEditor.edge_already_connected_message'))
    return
  }

  params.type = vueFlowStyleSettings.value.edge?.type || 'default'
  params.animated = vueFlowStyleSettings.value.edge?.animated || true
  params.style = vueFlowStyleSettings.value.edge?.style || { strokeWidth: 3, stroke: '#28c5e5' }

  // 如果连线任意一端是 ignored 的节点，则节点也要设置为 ignored
  const sourceNode = findNode(params.source)
  const targetNode = findNode(params.target)
  if (sourceNode.ignored || targetNode.ignored) {
    params.ignored = true
    params.class = 'ignored-edge'
  }

  addEdges([params])
})
const onEdgeUpdate = ({ edge, connection }) => {
  updateEdge(edge, connection)
}

const onEdgeClick = ({ edge, event }) => {
  if (edge.selected) {
    message.info(t('workspace.workflowEditor.edge_delete_message'))
  }
}
const onPaneClick = (event) => {
}

const onEdgeDoubleClick = (event) => {
  elements.value = elements.value.filter((element) => {
    if (element.source === event.edge.source && element.target === event.edge.target && element.sourceHandle === event.edge.sourceHandle && element.targetHandle === event.edge.targetHandle) {
      return false
    }
    return true
  })
}

const nodeEvents = {
  change: (data, nodeId) => {
    if (data.event == 'removeField') {
      const edgesToRemove = edges.value.filter((edge) => {
        if (edge.source === nodeId && edge.sourceHandle === data.fieldName) {
          return true
        }
        if (edge.target === nodeId && edge.targetHandle === data.fieldName) {
          return true
        }
        return false
      })
      removeEdges(edgesToRemove)
    } else if (data.event == 'editField') {
      const { oldFieldName, newFieldName } = data
      const node = findNode(nodeId)
      // handleBounds 得手动修改一下才行
      node.handleBounds.source.forEach((handle) => {
        if (handle.id === oldFieldName) {
          handle.id = newFieldName
        }
      })
      node.handleBounds.target.forEach((handle) => {
        if (handle.id === oldFieldName) {
          handle.id = newFieldName
        }
      })
      edges.value.forEach((edge) => {
        if (edge.source === nodeId && edge.sourceHandle === oldFieldName) {
          edge.sourceHandle = newFieldName
        }
        if (edge.target === nodeId && edge.targetHandle === oldFieldName) {
          edge.targetHandle = newFieldName
        }
      })
    }
  },
  delete: (data, nodeId) => {
    removeNodes([nodeId])
  },
  clone: (data, nodeId) => {
    const node = findNode(nodeId)
    node.selected = false
    const newNode = JSON.parse(JSON.stringify(node))
    newNode.id = uuidv4()
    newNode.selected = true
    newNode.position.x += 50
    newNode.position.y -= 50
    addNodes([newNode])
  },
  ignore: (ignored, nodeId) => {
    const node = findNode(nodeId)

    // 检查是否可以忽略该节点，主要判断 target 类端口在该节点恢复后不能有多个连线
    const resumable = { pass: true, errors: new Set() }
    if (!ignored) {
      edges.value.forEach(edge => {
        if (edge.source === nodeId || edge.target === nodeId) {
          // 首先检查该 edge 的 target 端口是否存在除了该 edge 之外的连线
          // 检查该 edge 的 target 端口是否存在除了该 edge 之外的连线
          const hasOtherConnections = edges.value.some(e => {
            return !e.ignored && e.target === edge.target && e.targetHandle === edge.targetHandle
          });

          if (hasOtherConnections) {
            resumable.pass = false
            resumable.errors.add('has_other_connections')
            const originalStyle = edge.originalStyle || edge.style
            edge.originalStyle = originalStyle
            edge.style = {
              stroke: '#f5222d',
              strokeWidth: 8,
            }
            setTimeout(() => {
              edge.style = originalStyle
              delete edge.originalStyle
            }, 3000)
            return
          }
        }
      })
    }

    if (!resumable.pass) {
      resumable.errors.forEach(error => {
        if (error == 'has_other_connections') {
          message.error(t('workspace.workflowEditor.resume_node_but_edge_already_connected_message'))
        }
      })
      return
    }

    // 需要把所有连线都调整 ignore 状态
    edges.value.forEach(edge => {
      if (edge.source === nodeId || edge.target === nodeId) {
        if (ignored) {
          edge.ignored = true
          edge.class = 'ignored-edge'
        } else {
          const otherNodeId = edge.source === nodeId ? edge.target : edge.source
          const otherNode = findNode(otherNodeId)
          if (otherNode.ignored) return
          delete edge.ignored
          if (edge.class) {
            edge.class = edge.class.replace('ignored-edge', '').trim()
          }
        }
      }
    })
    node.ignored = ignored
  },
}
watch(() => nodeMessagesCount.value, () => {
  while (nodeMessages.value.length > 0) {
    const { action, data, nodeId } = useNodeMessages.pop()
    nodeEvents[action](data, nodeId)
  }
})

let ghostMenuItem
const onTouchStart = (event) => {
  if (ghostMenuItem) {
    document.body.removeChild(ghostMenuItem)
  }
  let rect = event.target.getBoundingClientRect()
  ghostMenuItem = event.target.cloneNode(true)
  ghostMenuItem.style.position = "absolute"
  ghostMenuItem.style.top = rect.top + "px"
  ghostMenuItem.style.left = rect.left + "px"
  ghostMenuItem.style.width = rect.width + "px"
  ghostMenuItem.style.height = rect.height + "px"
  ghostMenuItem.style.opacity = "0.5"
  ghostMenuItem.style.zIndex = "1000"
  document.body.appendChild(ghostMenuItem)
}
const onTouchMove = (event) => {
  if (ghostMenuItem) {
    ghostMenuItem.style.left = event.touches[0].clientX + "px"
    ghostMenuItem.style.top = event.touches[0].clientY + "px"
  }
}

const addNodeToCanvas = (nodeType, position, updateTemplateData = {}, extraData = {}) => {
  const nodeTemplateData = nodeTemplateCreators[nodeType]()
  nodeTemplateData.template = {
    ...nodeTemplateData.template,
    ...updateTemplateData,
  }

  // 翻译节点模板数据中的 display_name
  Object.entries(nodeTemplateData.template).forEach(([key, value]) => {
    const translationKey = `components.nodes.${nodeCategoriesReverse[nodeType]}.${nodeType}.${key}`
    if (te(translationKey) && value.display_name) {
      value.display_name = t(translationKey)
    }
    if (!value.options) return

    value.options = value.options.map(item => {
      const translationKey = `components.nodes.${nodeCategoriesReverse[nodeType]}.${nodeType}.${key}_${item.value}`
      if (te(translationKey)) {
        item.label = t(translationKey)
      }
      return item
    })
  })

  const newNode = {
    id: uuidv4(),
    type: nodeType,
    category: nodeCategoriesReverse[nodeType],
    position,
    data: nodeTemplateData,
    ...extraData,
  }

  addNodes([newNode])
}

const onNewNodeDragEnd = (event) => {
  if (ghostMenuItem) {
    document.body.removeChild(ghostMenuItem)
    ghostMenuItem = null
  }

  let nodeType = event.srcElement.dataset.nodeType
  if (!nodeType) {
    nodeType = event.srcElement.children[0].dataset.nodeType
  }

  const dropZoneRect = vueFlowRef.value.getBoundingClientRect()
  const { x, y, zoom } = viewport.value
  let dropZoneX = 0
  let dropZoneY = 0
  if (event.type == 'touchend') {
    dropZoneX = event.changedTouches[0].clientX - dropZoneRect.left
    dropZoneY = event.changedTouches[0].clientY - dropZoneRect.top
  } else {
    dropZoneX = event.clientX - dropZoneRect.left
    dropZoneY = event.clientY - dropZoneRect.top
  }

  const position = {
    x: (dropZoneX - x) / zoom,
    y: (dropZoneY - y) / zoom,
  }

  addNodeToCanvas(nodeType, position)
}

const nodeFiles = import.meta.glob([
  '@/components/nodes/*/*.vue',
  '!@/components/nodes/*/_*.vue'
], { eager: true })

const nodeTemplateFiles = import.meta.glob([
  '@/components/nodes/*/*.js',
  '!@/components/nodes/*/_*.js'
], { eager: true })
const nodeTypes = {}
const nodeCategories = {}
const nodeTemplateCreators = {}
const nodeCategoriesReverse = {}
Object.entries(nodeFiles).forEach(([path, component]) => {
  const name = path.match(/\/([^/]+)\.vue$/)[1]
  const categoryName = path.match(/\/([^/]+)\/[^/]+\.vue$/)[1]

  nodeTypes[name] = markRaw(component.default)

  const nodeTemplate = nodeTemplateFiles[path.replace(/\.vue$/, '.js')]
  nodeTemplateCreators[name] = nodeTemplate?.createTemplateData
  if (nodeTemplateCreators[name]().deprecated) return
  if (!nodeCategories[categoryName]) {
    nodeCategories[categoryName] = []
  }
  nodeCategories[categoryName].push(name)
  nodeCategoriesReverse[name] = categoryName
})

const codeEditorModal = reactive({
  open: false,
  code: '',
  openEditor: async () => {
    let editorData = getCleanWorkflowData()
    editorData.ui = currentWorkflow.value.data.ui || {}
    codeEditorModal.code = JSON.stringify(editorData, null, 2)
    codeEditorModal.open = true
  },
  updateCode: (code) => {
    const workflowData = JSON.parse(code)
    currentWorkflow.value.data.ui = workflowData.ui || {}
    elements.value = [...workflowData.nodes, ...workflowData.edges]

    currentWorkflow.value.data.nodes = workflowData.nodes
    currentWorkflow.value.data.edges = workflowData.edges
    currentWorkflow.value.data.nodes.forEach((node) => {
      if (node.category == "vectorDb") {
        node.data.template.database.options = userDatabases.value.filter((database) => {
          return database.status == 'VALID'
        }).map((item) => {
          return {
            value: item.vid,
            label: item.name,
          }
        })
      }
    })
    savedWorkflowHash.value = hasher.hash(currentWorkflow.value)
  },
})

const testRunModal = reactive({
  open: false,
  openTestModal: () => {
    updateWorkflowData()
    testRunModal.open = true
  },
})

const { layout } = useLayout()
async function layoutGraph(direction) {
  const result = layout(nodes.value, edges.value, direction)
  elements.value.forEach((element) => {
    if (Object.keys(element).includes('handleBounds')) {
      element.position = result.find(node => node.id === element.id).position
    }
  })

  nextTick(() => {
    fitView()
  })
}
</script>

<template>
  <div class="loading-container" v-if="loading">
    <a-spin size="large" />
  </div>
  <div class="editor-container" v-else>
    <div class="title-container">
      <a-row style="width: 100%;">
        <a-col :span="8">
          <a-flex gap="middle" align="center">
            <a-typography-link @click="exitConfirm" style="text-wrap: nowrap;">
              <Left />
              {{ t('common.back') }}

              <a-modal v-model:open="exitModalOpen">
                <template #title>
                  <a-typography-text type="warning">
                    <Caution />
                    {{ t('common.back') }}
                  </a-typography-text>
                </template>

                {{ t('workspace.workflowEditor.exit_not_saved_confirm') }}

                <template #footer>
                  <a-button @click="exitNoSave">
                    {{ t('workspace.workflowEditor.exit_without_save') }}
                  </a-button>
                  <a-button type="primary" @click="saveAndExit">
                    {{ t('workspace.workflowEditor.save_and_exit') }}
                  </a-button>
                </template>
              </a-modal>
            </a-typography-link>

            <a-typography-text class="title" :ellipsis="true" :editable="{ triggerType: ['text', 'icon'] }"
              v-model:content="currentWorkflow.title" />
          </a-flex>
        </a-col>

        <a-col :span="8" style="display: flex; justify-content: center;">
          <a-segmented v-model:value="activeTab" :options="tabs" @change="updateWorkflowData" />
        </a-col>

        <a-col :span="8" style="display: flex; justify-content: end;">
          <a-space>
            <a-tooltip :title="t('workspace.workflowEditor.edit_code')">
              <a-button type="text" size="small" @click="codeEditorModal.openEditor">
                <template #icon>
                  <Code />
                </template>
                <CodeEditorModal language="json" v-model:open="codeEditorModal.open" v-model:code="codeEditorModal.code"
                  @save="codeEditorModal.updateCode" />
              </a-button>
            </a-tooltip>
            <a-tooltip :title="t('workspace.workflowEditor.test_run')">
              <a-button type="text" size="small" @click="testRunModal.openTestModal">
                <template #icon>
                  <Bug />
                </template>
                <a-modal v-model:open="testRunModal.open"
                  :title="`${t('workspace.workflowEditor.test_run')}: ${currentWorkflow.title}`" :footer="null"
                  width="90vw" :bodyStyle="{ minHeight: '70vh' }">
                  <WorkflowUse v-if="testRunModal.open" :workflow="currentWorkflow" :isTemplate="false" />
                </a-modal>
              </a-button>
            </a-tooltip>
            <a-button type="primary" @click="saveWorkflow" :loading="saving" :disabled="!!diagnosisRecordId">
              <template #icon>
                <Save />
              </template>
              <a-tooltip :title="diagnosisRecordId ? t('workspace.workflowEditor.cannot_save_when_diagnosing') : ''">
                {{ t('common.save') }}
              </a-tooltip>
            </a-button>
            <a-modal v-model:open="saveCheckModalOpen" :footer="null">
              <template #title>
                <a-typography-text type="warning">
                  <Caution />
                  {{ t('workspace.workflowEditor.workflow_check_warning') }}
                </a-typography-text>
              </template>

              <a-typography-paragraph type="danger" v-if="!workflowCheckList.hasInput">
                {{ t('workspace.workflowEditor.workflow_has_no_inputs') }}
              </a-typography-paragraph>
              <a-typography-paragraph type="danger" v-if="!workflowCheckList.hasOutput">
                {{ t('workspace.workflowEditor.workflow_has_no_outputs') }}
              </a-typography-paragraph>
              <a-typography-paragraph type="danger" v-if="!workflowCheckList.hasTrigger">
                {{ t('workspace.workflowEditor.workflow_has_no_triggers') }}
              </a-typography-paragraph>
              <a-typography-paragraph type="danger" v-if="!workflowCheckList.noCycle">
                {{ t('workspace.workflowEditor.workflow_has_cycles') }}
              </a-typography-paragraph>
              <a-typography-paragraph type="danger" v-if="!workflowCheckList.noIsolatedNodes">
                {{ t('workspace.workflowEditor.workflow_has_isolated_nodes') }}
              </a-typography-paragraph>

            </a-modal>
          </a-space>
        </a-col>
      </a-row>
    </div>

    <div v-show="activeTab == 'info'" class="workflow-info-editor">
      <a-row justify="center">
        <a-col :lg="10" :md="12" :sm="18" :xs="24">
          <a-divider>
            {{ t('workspace.workflowEditor.tags') }}
            <TagManage />
          </a-divider>
          <TagInput v-model="currentWorkflow.tags" />
          <a-divider>
            {{ t('workspace.workflowEditor.brief_info') }}
          </a-divider>
          <MarkdownEditor v-model="currentWorkflow.brief" />
          <a-divider>
            {{ t('workspace.workflowEditor.brief_images') }}
          </a-divider>
          <div>
            <UploaderFieldUse v-model="currentWorkflow.images" :multiple="true" :supportFileTypes="'image/*'" />
          </div>
        </a-col>
      </a-row>
    </div>

    <a-layout v-show="activeTab == 'canvas'" has-sider style="height: 100%;">
      <a-layout-sider class="custom-scrollbar" :defaultCollapsed="collapsed" v-model:collapsed="collapsed"
        :trigger="null" :width="220" collapsible :collapsedWidth="48" @collapse="onCollapse" breakpoint="lg"
        :theme="componentTheme" :style="{ overflowY: sidebarHover ? 'auto' : 'hidden' }"
        @mouseover="sidebarHover = true" @mouseleave="sidebarHover = false">
        <a-menu :theme="componentTheme" mode="inline">
          <a-sub-menu v-for="category in nodeCategoryOptions" :key="`category-${category.name}`" :icon="category.icon">
            <template #title>
              {{ t(`components.nodes.${category.name}.title`) }}
            </template>
            <a-menu-item :data-node-type="node" :id="node" draggable="true" @touchstart="onTouchStart"
              @touchmove="onTouchMove" @dragend="onNewNodeDragEnd" @touchend="onNewNodeDragEnd"
              v-for="(node, nodeIndex) in nodeCategories[category.name]" :key="`node-${nodeIndex}`">
              <span :data-node-type="node">{{ t(`components.nodes.${category.name}.${node}.title`) }}</span>
            </a-menu-item>
          </a-sub-menu>
          <div class="collapse-button">
            <a-button type="text" @click="onCollapse(!collapsed)">
              <MenuFoldOne v-if="collapsed" class="trigger" />
              <MenuUnfoldOne v-else class="trigger" />
            </a-button>
          </div>
        </a-menu>
      </a-layout-sider>
      <a-layout style="background-color: var(--component-background);">
        <a-alert v-if="diagnosisRecord" banner>
          <template #message>
            <a-flex align="center" justify="space-between">
              <a-typography-text>
                {{ t('workspace.workflowEditor.diagnosing_record', {
                  record: `${diagnosisRecord.title}
                ${diagnosisRecord.data.rid}`
                }) }}
              </a-typography-text>
            </a-flex>
          </template>
        </a-alert>
        <a-layout-content class="editor-canvas">
          <VueFlow v-model="elements" :node-types="nodeTypes" :edges-updatable="true" @edge-update="onEdgeUpdate"
            @edge-click="onEdgeClick" @edge-double-click="onEdgeDoubleClick" @pane-click="onPaneClick"
            :snap-to-grid="true" :snap-grid="[20, 20]">
            <MiniMap pannable :style="{ backgroundColor: 'var(--component-background)' }"
              :maskColor="theme == 'default' ? 'rgb(240, 242, 243, 0.7)' : 'rgb(60, 60, 60, 0.7)'" />
            <Controls />
            <Background variant="dots" />
            <a-flex align="center" justify="center" class="vue-flow-toolbar">
              <VueFlowStyleSettings v-model="vueFlowStyleSettings" @save=onVueFlowStyleSettingsSave />
              <a-tooltip :title="t('workspace.workflowEditor.layout_graph')">
                <a-button type="text" @click="layoutGraph('LR')">
                  <template #icon>
                    <LayoutFive />
                  </template>
                </a-button>
              </a-tooltip>
            </a-flex>
          </VueFlow>
        </a-layout-content>
      </a-layout>
    </a-layout>

    <UIDesign v-if="activeTab == 'ui_design'" v-model="currentWorkflow" />
  </div>
</template>

<style scoped>
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
}

.editor-container {
  padding: 20px;
  padding-bottom: 0;
  background-color: var(--component-background);
}

.editor-container .title-container {
  display: flex;
  align-items: center;
  height: 40px;
  padding-bottom: 20px;
  border-bottom: var(--light-border);
}

.editor-container .title-container .title {
  white-space: nowrap;
  font-size: 18px;
  margin-bottom: 0;
  min-width: 200px;
}

.editor-container .ant-layout-sider {
  height: calc(100vh - 40px - 40px);
}

.editor-canvas {
  margin: 24px 16px 0;
  overflow: initial;
  background-color: var(--component-background);
}

.workflow-info-editor {
  height: calc(100vh - 60px);
}

.vue-flow-toolbar {
  position: absolute;
  top: 5px;
  right: 5px;
  z-index: 10;
}
</style>

<style>
.vue-flow .vue-flow__edge.selected path {
  stroke: #28c5e5 !important;
  stroke-width: 6 !important;
}

.vue-flow .shadow-edge,
.vue-flow .ignored-edge {
  opacity: 0.5;
}
</style>