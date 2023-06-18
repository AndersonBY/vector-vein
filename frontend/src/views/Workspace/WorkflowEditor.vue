<script setup>
import { h, ref, reactive, defineComponent, markRaw, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { v4 as uuidv4 } from 'uuid'
import { Modal, message } from 'ant-design-vue'
import { LeftOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Background, BackgroundVariant } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { useRoute, useRouter } from "vue-router"
import { storeToRefs } from 'pinia'
import { useUserAccountStore } from '@/stores/userAccount'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import TagInput from '@/components/workspace/TagInput.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import { workflowAPI } from "@/api/workflow"
import { hashObject } from "@/utils/util"
import { databaseAPI } from "@/api/database"
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'

defineComponent({
  name: 'WorkflowEditor',
})
console.log("in workflow editor")
const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const workflowId = route.params.workflowId
const activeTab = ref(t('workspace.workflowEditor.workflow_canvas'))
const tabs = reactive([
  t('workspace.workflowEditor.workflow_info'),
  t('workspace.workflowEditor.workflow_canvas'),
])

const userAccountStore = useUserAccountStore()
const { userAccount } = storeToRefs(userAccountStore)
const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const userWorkflowsStore = useUserWorkflowsStore()

const savedWorkflowHash = ref('')
const currentWorkflow = ref({})
const elements = ref([])

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
  elements.value.forEach((element) => {
    element.events = {
      change: (event) => onNodeChange(event),
      delete: (event) => onNodeDelete(event),
    }
  })
  savedWorkflowHash.value = hashObject(currentWorkflow.value)
  loading.value = false
})

const saving = ref(false)
const saveWorkflow = async () => {
  saving.value = true
  currentWorkflow.value.data = toObject()
  const response = await workflowAPI('update', {
    wid: workflowId,
    ...currentWorkflow.value,
  })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.save_success'))
    savedWorkflowHash.value = hashObject(currentWorkflow.value)
  } else {
    message.error(t('workspace.workflowSpace.save_failed'))
  }
  userWorkflowsStore.updateUserWorkflow(currentWorkflow.value)
  saving.value = false
}

const exitConfirm = () => {
  currentWorkflow.value.data = toObject()
  if (savedWorkflowHash.value != hashObject(currentWorkflow.value)) {
    Modal.confirm({
      title: t('common.back'),
      icon: h(ExclamationCircleOutlined),
      content: t('workspace.workflowEditor.exit_not_saved_confirm'),
      okText: t('workspace.workflowEditor.save_and_exit'),
      cancelText: t('workspace.workflowEditor.exit_without_save'),
      onOk() {
        saveWorkflow().then(() => {
          router.push({ name: 'WorkflowUse', params: { workflowId: workflowId } })
        })
      },
      onCancel() {
        router.push({ name: 'WorkflowUse', params: { workflowId: workflowId } })
      },
    })
  } else {
    router.push({ name: 'WorkflowUse', params: { workflowId: workflowId } })
  }
}

const { addEdges, updateEdge, onConnect, toObject } = useVueFlow()
onConnect((params) => {
  params.animated = true
  params.style = { strokeWidth: 3, stroke: '#565656' }
  addEdges([params])
})
const onEdgeUpdate = ({ edge, connection }) => {
  updateEdge(edge, connection)
}

const onNodeChange = (event) => {
  // console.log('change', event)
}
const onNodeDelete = (event) => {
  elements.value = elements.value.filter((element) => element.id !== event.id)
  elements.value = elements.value.filter((element) => {
    if (element.source && element.source === event.id) {
      return false
    }
    if (element.target && element.target === event.id) {
      return false
    }
    return true
  })
}

const onEdgeDoubleClick = (event) => {
  elements.value = elements.value.filter((element) => {
    if (element.source === event.edge.source && element.target === event.edge.target && element.sourceHandle === event.edge.sourceHandle && element.targetHandle === event.edge.targetHandle) {
      return false
    }
    return true
  })
}

let vueflowInstance = null
const onPaneReady = (pane) => {
  vueflowInstance = pane
}

let dropZone = null

const onNewNodeDragStart = (event) => {
  event.dataTransfer.setData('nodeType', event.target.id)
}
const onNewNodeDragEnd = (event) => {
  const nodeType = event.srcElement.id
  const nodeCategory = nodeCategoriesReverse[nodeType]
  const nodeId = uuidv4()
  const templateData = JSON.parse(JSON.stringify(nodeTypes[nodeType].props.templateData))
  templateData.description = t(`components.nodes.${nodeCategory}.${nodeType}.description`)
  Object.keys(templateData.template).forEach((key) => {
    templateData.template[key].display_name = t(`components.nodes.${nodeCategory}.${nodeType}.${key}`)
  })

  const dropZoneRect = dropZone.getBoundingClientRect()
  const { x, y, zoom } = vueflowInstance.viewport.value
  const dropZoneX = event.clientX - dropZoneRect.left
  const dropZoneY = event.clientY - dropZoneRect.top

  const newNode = {
    id: nodeId,
    type: nodeType,
    category: nodeCategory,
    position: {
      x: (dropZoneX - x) / zoom,
      y: (dropZoneY - y) / zoom,
    },
    data: templateData,
    events: {
      change: (event) => onNodeChange(event),
      delete: (event) => onNodeDelete(event),
    },
  }

  elements.value.push(newNode)
}

const onNewNodeDragOver = (event) => {
  event.preventDefault();
  dropZone = event.target
}

const nodeFiles = import.meta.globEager('@/components/nodes/*/*.vue')
const nodeTypes = {}
const nodesCategories = {}
const nodeCategoriesReverse = {}
Object.entries(nodeFiles).forEach(([path, component]) => {
  const name = path.match(/\/([^/]+)\.vue$/)[1]
  nodeTypes[name] = markRaw(component.default)
  const categoryName = path.match(/\/([^/]+)\/[^/]+\.vue$/)[1]
  // 工作人员提前测试用
  // if (!userAccount.value.is_staff && categoryName === 'mediaProcessing') {
  //   return
  // }
  // if (!userAccount.value.is_staff && name === 'MpWeixinTemplateMsg') {
  //   return
  // }
  if (!nodesCategories[categoryName]) {
    nodesCategories[categoryName] = []
  }
  nodesCategories[categoryName].push(name)
  nodeCategoriesReverse[name] = categoryName
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
          </a-typography-link>
        </a-col>

        <a-col flex="0 0">
          <a-typography-text class="title" :editable="{ triggerType: ['text', 'icon'] }"
            v-model:content="currentWorkflow.title">
          </a-typography-text>
        </a-col>

        <a-col flex="1 0" style="display: flex; justify-content: center;">
          <a-segmented v-model:value="activeTab" :options="tabs" />
        </a-col>

        <a-col flex="0 0" style="display: flex; justify-content: end;">
          <a-button type="primary" @click="saveWorkflow" :confirm-loading="saving">
            {{ t('common.save') }}
          </a-button>
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
          <MarkdownEditor v-model:markdown="currentWorkflow.brief" />
          <a-divider>
            {{ t('workspace.workflowEditor.brief_images') }}
          </a-divider>
          <UploaderFieldUse v-model="currentWorkflow.images" :multiple="true" />
        </a-col>
      </a-row>
    </div>

    <a-layout has-sider style="height: 100%;" v-show="activeTab == t('workspace.workflowEditor.workflow_canvas')">
      <a-layout-sider :style="{ overflow: 'auto', backgroundColor: '#fff' }" class="custom-scrollbar">
        <a-menu theme="light" mode="inline">
          <a-sub-menu v-for="(category, categoryIndex) in Object.keys(nodesCategories)"
            :key="`category-${categoryIndex}`">
            <template #title>{{ t(`components.nodes.${category}.title`) }}</template>
            <a-menu-item :id="node" draggable="true" @dragstart="onNewNodeDragStart" @dragend="onNewNodeDragEnd"
              v-for="(node, nodeIndex) in nodesCategories[category]" :key="`node-${nodeIndex}`">
              <span>{{ t(`components.nodes.${category}.${node}.title`) }}</span>
            </a-menu-item>
          </a-sub-menu>
        </a-menu>
      </a-layout-sider>
      <a-layout>
        <a-layout-content :style="{ margin: '24px 16px 0', overflow: 'initial' }">
          <VueFlow v-model="elements" :default-edge-options="{ type: 'smoothstep' }" :node-types="nodeTypes"
            :edgesUpdatable="true" @edge-update="onEdgeUpdate" @pane-ready="onPaneReady" @dragover="onNewNodeDragOver"
            @edge-double-click="onEdgeDoubleClick" :snap-to-grid="true" :snap-grid="[20, 20]">
            <MiniMap />
            <Controls />
            <Background :variant="BackgroundVariant.Dots" />
          </VueFlow>
        </a-layout-content>
      </a-layout>
    </a-layout>
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
  text-wrap: nowrap;
  font-size: 18px;
  margin-bottom: 0;
  min-width: 200px;
}

.editor-container .ant-layout-sider {
  height: calc(100vh - 40px - 40px);
}
</style>