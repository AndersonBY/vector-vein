<script setup>
import { ref, reactive, markRaw, onBeforeMount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { v4 as uuidv4 } from 'uuid'
import { message } from 'ant-design-vue'
import { LeftOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Background, BackgroundVariant } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { useRoute, useRouter } from "vue-router"
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserSettingsStore } from "@/stores/userSettings"
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import TagInput from '@/components/workspace/TagInput.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import CodeEditorModal from '@/components/CodeEditorModal.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import UIDesign from '@/components/workspace/UIDesign.vue'
import VueFlowStyleSettings from '@/components/workspace/VueFlowStyleSettings.vue'
import { workflowAPI } from "@/api/workflow"
import { hashObject } from "@/utils/util"
import { getUIDesignFromWorkflow, nonFormItemsTypes, checkWorkflowDAG } from '@/utils/workflow'
import { databaseAPI } from "@/api/database"
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const workflowId = route.params.workflowId
const activeTab = ref(t('workspace.workflowEditor.workflow_canvas'))
const tabs = reactive([
  t('workspace.workflowEditor.workflow_info'),
  t('workspace.workflowEditor.workflow_canvas'),
  t('workspace.workflowEditor.workflow_ui_design'),
])

const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const userWorkflowsStore = useUserWorkflowsStore()
const userSettingsStore = useUserSettingsStore()
const { vueFlowStyleSettings } = storeToRefs(userSettingsStore)
const useNodeMessages = useNodeMessagesStore()
const { nodeMessagesCount, nodeMessages } = storeToRefs(useNodeMessages)

const nodeEvents = {
  change: (data, nodeId) => {
    // console.log('change', event)
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
    const node = elements.value.find((element) => element.id === nodeId)
    node.selected = false
    const newNode = JSON.parse(JSON.stringify(node))
    newNode.id = uuidv4()
    newNode.selected = true
    newNode.position.x += 50
    newNode.position.y += 50
    elements.value.push(newNode)
  },
}
watch(() => nodeMessagesCount.value, () => {
  while (nodeMessages.value.length > 0) {
    const { action, data, nodeId } = useNodeMessages.pop()
    nodeEvents[action](data, nodeId)
  }
})

const savedWorkflowHash = ref('')
const currentWorkflow = ref({})
const elements = ref([])

const onVueFlowStyleSettingsSave = () => {
  edges.value.forEach((edge) => {
    edge.type = vueFlowStyleSettings.value.edge.type
    edge.animated = vueFlowStyleSettings.value.edge.animated
    edge.style = vueFlowStyleSettings.value.edge.style
  })
  userSettingsStore.setVueFlowStyleSettings(vueFlowStyleSettings.value)
}

onBeforeMount(async () => {
  const getWorkflowRequest = workflowAPI('get', { wid: workflowId })
  const listDatabasesRequest = databaseAPI('list', {})
  const workflowResponse = await getWorkflowRequest
  const listDatabasesResponse = await listDatabasesRequest

  if (listDatabasesResponse.status == 200) {
    userDatabasesStore.setUserDatabases(listDatabasesResponse.data)
  }
  if (workflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    router.push({ name: 'WorkflowSpaceMain' })
    return
  }
  currentWorkflow.value = workflowResponse.data
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
  currentWorkflow.value.tags = currentWorkflow.value.tags.map(tag => tag.tid)
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
  workflowCheckList.value.hasOutput = reactiveUIDesign.outputNodes.filter((node) => node.category == 'outputs').length > 0
  workflowCheckList.value.hasTrigger = reactiveUIDesign.triggerNodes.filter((node) => node.category == 'triggers').length > 0
  if (Object.values(workflowCheckList.value).some(val => val === false)) {
    saveCheckModalOpen.value = true;
  }
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
  saveWorkflowCheck()
  const response = await workflowAPI('update', {
    wid: workflowId,
    ...currentWorkflow.value,
  })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.save_success'))
    savedWorkflowHash.value = hashObject(currentWorkflow.value)
  } else if (response.data.status == 400) {
    message.error(t('workspace.workflowSpace.workflow_cant_invoke_itself'))
  } else {
    message.error(t('workspace.workflowSpace.save_failed'))
  }
  userWorkflowsStore.updateUserWorkflow(currentWorkflow.value)
  saving.value = false
}

const routerBack = async () => {
  await router.push({ name: 'WorkflowUse', params: { workflowId: workflowId } })
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

const { addEdges, updateEdge, onConnect, toObject, viewport, vueFlowRef, edges } = useVueFlow()
onConnect((params) => {
  params.type = vueFlowStyleSettings.value.edge.type
  params.animated = vueFlowStyleSettings.value.edge.animated
  params.style = vueFlowStyleSettings.value.edge.style
  addEdges([params])
})
const onEdgeUpdate = ({ edge, connection }) => {
  updateEdge(edge, connection)
}

const onEdgeDoubleClick = (event) => {
  elements.value = elements.value.filter((element) => {
    if (element.source === event.edge.source && element.target === event.edge.target && element.sourceHandle === event.edge.sourceHandle && element.targetHandle === event.edge.targetHandle) {
      return false
    }
    return true
  })
}

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
  const nodeCategory = nodeCategoriesReverse[nodeType]
  const nodeId = uuidv4()
  const templateData = JSON.parse(JSON.stringify(nodeTypes[nodeType].props.templateData))
  templateData.description = t(`components.nodes.${nodeCategory}.${nodeType}.description`)
  Object.keys(templateData.template).forEach((key) => {
    templateData.template[key].display_name = t(`components.nodes.${nodeCategory}.${nodeType}.${key}`)
  })

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

  const newNode = {
    id: nodeId,
    type: nodeType,
    category: nodeCategory,
    position: {
      x: (dropZoneX - x) / zoom,
      y: (dropZoneY - y) / zoom,
    },
    data: templateData,
  }

  elements.value.push(newNode)
}

const nodeFiles = import.meta.globEager('@/components/nodes/*/*.vue')
const nodeTypes = {}
const nodesCategories = {}
const nodeCategoriesReverse = {}
Object.entries(nodeFiles).forEach(([path, component]) => {
  const name = path.match(/\/([^/]+)\.vue$/)[1]
  nodeTypes[name] = markRaw(component.default)
  const categoryName = path.match(/\/([^/]+)\/[^/]+\.vue$/)[1]
  if (!nodesCategories[categoryName]) {
    nodesCategories[categoryName] = []
  }
  nodesCategories[categoryName].push(name)
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
      <a-row type="flex" align="middle" justify="space-between" :gutter="[16, 16]" style="width: 100%;">
        <a-col flex="0 0">
          <a-typography-link @click="exitConfirm" style="text-wrap: nowrap;">
            <LeftOutlined />
            {{ t('common.back') }}

            <a-modal v-model:open="exitModalOpen">
              <template #title>
                <a-typography-text type="warning">
                  <ExclamationCircleOutlined />
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
        </a-col>

        <a-col flex="0 0">
          <a-typography-text class="title" :editable="{ triggerType: ['text', 'icon'] }"
            v-model:content="currentWorkflow.title">
          </a-typography-text>
        </a-col>

        <a-col flex="1 0" style="display: flex; justify-content: center;">
          <a-segmented v-model:value="activeTab" :options="tabs" @change="updateWorkflowData" />
        </a-col>

        <a-col flex="0 0" style="display: flex; justify-content: end;">
          <a-space>
            <a-button @click="codeEditorModal.openEditor">
              {{ t('workspace.workflowEditor.edit_code') }}
              <CodeEditorModal language="json" v-model:open="codeEditorModal.open" v-model:code="codeEditorModal.code"
                @save="codeEditorModal.updateCode" />
            </a-button>
            <a-button type="primary" @click="saveWorkflow" :loading="saving">
              {{ t('common.save') }}
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
            <UploaderFieldUse v-model="currentWorkflow.images" :multiple="true" />
          </div>
        </a-col>
      </a-row>
    </div>

    <a-layout has-sider style="height: 100%;" v-show="activeTab == t('workspace.workflowEditor.workflow_canvas')">
      <a-layout-sider :style="{ overflow: 'auto', backgroundColor: '#fff' }" class="custom-scrollbar">
        <a-menu theme="light" mode="inline">
          <a-sub-menu v-for="(category, categoryIndex) in Object.keys(nodesCategories)"
            :key="`category-${categoryIndex}`">
            <template #title>{{ t(`components.nodes.${category}.title`) }}</template>
            <a-menu-item :data-node-type="node" :id="node" draggable="true" @touchstart="onTouchStart"
              @touchmove="onTouchMove" @dragend="onNewNodeDragEnd" @touchend="onNewNodeDragEnd"
              v-for="(node, nodeIndex) in nodesCategories[category]" :key="`node-${nodeIndex}`">
              <span :data-node-type="node">{{ t(`components.nodes.${category}.${node}.title`) }}</span>
            </a-menu-item>
          </a-sub-menu>
        </a-menu>
      </a-layout-sider>
      <a-layout>
        <a-layout-content :style="{ margin: '24px 16px 0', overflow: 'initial' }">
          <VueFlow v-model="elements" :node-types="nodeTypes" :edgesUpdatable="true" @edge-update="onEdgeUpdate"
            @edge-double-click="onEdgeDoubleClick" :snap-to-grid="true" :snap-grid="[20, 20]">
            <MiniMap />
            <Controls />
            <Background :variant="BackgroundVariant.Dots" />
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
  margin-bottom: 20px;
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