<script setup>
import { ref, reactive, markRaw, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { v4 as uuidv4 } from 'uuid'
import { message } from 'ant-design-vue'
import { Left, Caution, Save, Code } from '@icon-park/vue-next'
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
import { hashObject } from "@/utils/util"
import { nodeCategoryOptions } from "@/utils/common"
import { getUIDesignFromWorkflow, nonFormItemsTypes, checkWorkflowDAG } from '@/utils/workflow'
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
const activeTab = ref(t('workspace.workflowEditor.workflow_canvas'))
const tabs = reactive([
  t('workspace.workflowEditor.workflow_info'),
  t('workspace.workflowEditor.workflow_canvas'),
  t('workspace.workflowEditor.workflow_ui_design'),
])
let workflowOrTemplate = 'workflow'
let workflowOrTemplateAPI = null
let queryParam = {}

const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const userRelationalDatabasesStore = useUserRelationalDatabasesStore()
const { userRelationalDatabases } = storeToRefs(userRelationalDatabasesStore)
const userWorkflowsStore = useUserWorkflowsStore()
const userSettingsStore = useUserSettingsStore()
const { vueFlowStyleSettings } = storeToRefs(userSettingsStore)
const useNodeMessages = useNodeMessagesStore()
const { nodeMessagesCount, nodeMessages } = storeToRefs(useNodeMessages)

const savedWorkflowHash = ref('')
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
        run_time: diagnosisRecord.value.data?.node_run_time?.[node.id] ?? -1,
        credits: node.data.credits || 0
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
  fromObject(currentWorkflow.value.data)
  elements.value = [...currentWorkflow.value.data.nodes, ...currentWorkflow.value.data.edges]
  savedWorkflowHash.value = hashObject(currentWorkflow.value)
  loading.value = false
})

const updateWorkflowData = () => {
  const workflowData = toObject()
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
  const workflowDAGStatus = checkWorkflowDAG(currentWorkflow.value)
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
  const workflowData = toObject()
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
      message.success(t('workspace.workflowSpace.save_success'))
      savedWorkflowHash.value = hashObject(currentWorkflow.value)
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
  const workflowData = toObject()
  currentWorkflow.value.data = {
    ...workflowData,
    ui: uiDesign,
  }
  if (savedWorkflowHash.value != hashObject(currentWorkflow.value)) {
    exitModalOpen.value = true
  } else {
    routerBack()
  }
}

const {
  addEdges,
  removeEdges,
  updateEdge,
  onConnect,
  toObject,
  fromObject,
  findNode,
  viewport,
  vueFlowRef,
  edges
} = useVueFlow()
onConnect((params) => {
  const hasConnectedEdge = edges.value.some((edge) => {
    return edge.target === params.target && edge.targetHandle === params.targetHandle
  })
  if (hasConnectedEdge) {
    message.error(t('workspace.workflowEditor.edge_already_connected_message'))
    return
  }

  params.type = vueFlowStyleSettings.value.edge?.type || 'bezier'
  params.animated = vueFlowStyleSettings.value.edge?.animated || true
  params.style = vueFlowStyleSettings.value.edge?.style || { strokeWidth: 3, stroke: '#28c5e5' }
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
    elements.value = elements.value.filter((element) => element.id !== nodeId)
    elements.value = elements.value.filter((element) => {
      if (element.source && element.source === nodeId) {
        return false
      }
      if (element.target && element.target === nodeId) {
        return false
      }
      return true
    })
  },
  clone: (data, nodeId) => {
    const node = findNode(nodeId)
    node.selected = false
    const newNode = JSON.parse(JSON.stringify(node))
    newNode.id = uuidv4()
    newNode.selected = true
    newNode.position.x += 50
    newNode.position.y -= 50
    elements.value.push(newNode)
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

  const nodeTemplateData = nodeTemplateCreators[nodeType]()

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
    position: {
      x: (dropZoneX - x) / zoom,
      y: (dropZoneY - y) / zoom,
    },
    data: nodeTemplateData,
  }

  elements.value.push(newNode)
}

const nodeFiles = import.meta.glob('@/components/nodes/*/*.vue', { eager: true })
const nodeTemplateFiles = import.meta.glob('@/components/nodes/*/*.js', { eager: true })
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
    let editorData = toObject()
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
    savedWorkflowHash.value = hashObject(currentWorkflow.value)
  },
})
</script>

<template>
  <div class="loading-container" v-if="loading">
    <a-spin size="large" />
  </div>
  <div class="editor-container" v-else>
    <div class="title-container">
      <a-row style="width: 100%;">
        <a-col :span="8">
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
            v-model:content="currentWorkflow.title">
          </a-typography-text>
        </a-col>

        <a-col :span="8" style="display: flex; justify-content: center;">
          <a-segmented v-model:value="activeTab" :options="tabs" @change="updateWorkflowData" />
        </a-col>

        <a-col :span="8" style="display: flex; justify-content: end;">
          <a-space>
            <a-button @click="codeEditorModal.openEditor">
              <template #icon>
                <Code />
              </template>
              {{ t('workspace.workflowEditor.edit_code') }}
              <CodeEditorModal language="json" v-model:open="codeEditorModal.open" v-model:code="codeEditorModal.code"
                @save="codeEditorModal.updateCode" />
            </a-button>
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

    <div v-show="activeTab == t('workspace.workflowEditor.workflow_info')">
      <a-row justify="center">
        <a-col :lg="10" :md="12" :sm="18" :xs="24">
          <a-divider>
            {{ t('workspace.workflowEditor.tags') }}
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

    <a-layout has-sider style="height: 100%;" v-show="activeTab == t('workspace.workflowEditor.workflow_canvas')">
      <a-layout-sider :style="{ overflow: 'auto', backgroundColor: '#fff' }" class="custom-scrollbar">
        <a-menu theme="light" mode="inline">
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
        </a-menu>
      </a-layout-sider>
      <a-layout style="background-color: #fff;">
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
        <a-layout-content :style="{ margin: '24px 16px 0', overflow: 'initial', backgroundColor: '#fff' }">
          <VueFlow v-model="elements" :node-types="nodeTypes" :edges-updatable="true" @edge-update="onEdgeUpdate"
            @edge-click="onEdgeClick" @edge-double-click="onEdgeDoubleClick" @pane-click="onPaneClick"
            :snap-to-grid="true" :snap-grid="[20, 20]">
            <MiniMap />
            <Controls />
            <Background variant="dots" />
            <VueFlowStyleSettings v-model="vueFlowStyleSettings" @save=onVueFlowStyleSettingsSave />
          </VueFlow>
        </a-layout-content>
      </a-layout>
    </a-layout>

    <UIDesign v-model="currentWorkflow" v-if="activeTab == t('workspace.workflowEditor.workflow_ui_design')">
    </UIDesign>
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
}

.editor-container .title-container {
  display: flex;
  align-items: center;
  height: 40px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f0f0;
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
</style>

<style>
.vue-flow .vue-flow__edge.selected path {
  stroke: #28c5e5 !important;
  stroke-width: 6 !important;
}
</style>