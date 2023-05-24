<script setup>
import { ref, defineComponent, markRaw, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { v4 as uuidv4 } from 'uuid'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Background, BackgroundVariant } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import TagInput from '@/components/workspace/TagInput.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'

defineComponent({
  name: 'WorkflowEditor',
})

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  brief: {
    type: String,
    required: true,
    default: '',
  },
  images: {
    type: Array,
    required: true,
    default: () => [],
  },
  tags: {
    type: Array,
    required: true,
  },
  nodes: {
    type: Array,
    required: true,
  },
  edges: {
    type: Array,
    required: true,
  },
})

const title = ref(props.title)
const brief = ref(props.brief)
const images = ref(props.images)
const tags = ref(props.tags.map(tag => tag.tid))
const open = ref(false)
const showModal = () => {
  open.value = true
}
const handleOk = e => {
  emit('ok', {
    title: title.value,
    brief: brief.value,
    images: images.value,
    tags: tags.value,
    workflow: toObject()
  })
  open.value = false
}
defineExpose({
  showModal,
})

const briefEditorModalOpen = ref(false)

const emit = defineEmits(['ok'])

const { t } = useI18n()

const { addEdges, updateEdge, onConnect, toObject } = useVueFlow()
onConnect((params) => {
  params.animated = true
  params.style = { strokeWidth: 3, stroke: '#565656' }
  addEdges([params])
})
const onEdgeUpdate = ({ edge, connection }) => {
  updateEdge(edge, connection)
}
const elements = ref([...props.nodes, ...props.edges])

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

onMounted(() => {
  elements.value.forEach((element) => {
    element.events = {
      change: (event) => onNodeChange(event),
      delete: (event) => onNodeDelete(event),
    }
  })
})

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
  if (!nodesCategories[categoryName]) {
    nodesCategories[categoryName] = []
  }
  nodesCategories[categoryName].push(name)
  nodeCategoriesReverse[name] = categoryName
})

</script>

<template>
  <a-modal v-model:open="open" width="100%" wrap-class-name="full-modal" @ok="handleOk" :ok-text="t('common.save')">
    <template #title>
      <a-space>
        <a-typography-text style="font-size: 18px;" :editable="{ triggerType: ['text', 'icon'] }" v-model:content="title">
        </a-typography-text>
        <a-divider type="vertical" />
        <TagInput v-model="tags" />
        <a-divider type="vertical" />
        <a-button type="primary" @click="briefEditorModalOpen = true">
          {{ t('components.workspace.workflowEditor.brief_editor') }}
          <a-modal :title="t('components.workspace.workflowEditor.brief_editor')" :open="briefEditorModalOpen"
            @cancel="briefEditorModalOpen = false" @ok="briefEditorModalOpen = false" :ok-text="t('common.save')">
            <MarkdownEditor v-model:markdown="brief" />
            <a-divider>
              {{ t('components.workspace.workflowEditor.brief_images') }}
            </a-divider>
            <UploaderFieldUse v-model="images" :multiple="true" />
          </a-modal>
        </a-button>
      </a-space>
    </template>
    <a-layout has-sider style="height: 100%;">
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
  </a-modal>
</template>

<style>
.full-modal .ant-modal {
  max-width: 100%;
  top: 0;
  padding-bottom: 0;
  margin: 0;
}

.full-modal .ant-modal-content {
  display: flex;
  flex-direction: column;
  height: calc(100vh);
}

.full-modal .ant-modal-body {
  flex: 1;
}

.full-modal .ant-layout-sider {
  height: calc(100vh - 40px - 36px - 44px);
}
</style>