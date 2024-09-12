<script setup>
import { watch, ref } from 'vue'
import { Delete, Copy, CheckOne, CloseOne, Help, BookOpen } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { useVueFlow } from '@vue-flow/core'
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import QuestionPopover from '@/components/QuestionPopover.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import BaseFieldsCollapse from '@/components/nodes/BaseFieldsCollapse.vue'
import ListField from '@/components/nodes/ListField.vue'
import DocumentModal from '@/components/help/DocumentModal.vue'
import { websiteBase } from '@/utils/common'

const props = defineProps({
  nodeId: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: false,
    default: '',
  },
  description: {
    type: String,
    required: false,
    default: '',
  },
  documentPath: {
    type: String,
    required: false,
    default: '',
  },
  width: {
    type: [Number, String, null],
    required: false,
    default: null,
  },
  translatePrefix: {
    type: String,
    required: false,
    default: '',
  },
  fieldsData: {
    type: Object,
    required: false,
    default: () => ({}),
  },
  debug: {
    type: [Object, null],
    required: false,
    default: null,
  },
})

const fieldsData = ref(props.fieldsData)
watch(() => props.fieldsData, (newValue) => {
  fieldsData.value = newValue
}, { deep: true })

if (props.debug) {
  Object.keys(fieldsData.value).forEach((field) => {
    fieldsData.value[field].debug = true;
  });
}

const documentSlug = ref('')
const documentNodeType = ref('')
const documentModalOpen = ref(false)

if (props.documentPath) {
  const parts = props.documentPath.split('#')
  if (parts.length === 2) {
    documentSlug.value = parts[0].split('/').pop()
    documentNodeType.value = parts[1].replace('node-', '')
  }
}

const { findNode } = useVueFlow()
const node = findNode(props.nodeId)

const useNodeMessages = useNodeMessagesStore()

const pushMessage = (action, data) => {
  useNodeMessages.push({
    action,
    data,
    nodeId: props.nodeId,
  })
}

const { t } = useI18n()
const title = props.title.length == 0 ? t(`${props.translatePrefix}.title`) : props.title
const description = props.description.length == 0 ? t(`${props.translatePrefix}.description`) : props.description

let style = {}
if (props.width) {
  if (typeof props.width === 'number') {
    style = { width: `${props.width}px` }
  } else if (typeof props.width === 'string') {
    style = { width: props.width }
  }
}

const updateFields = () => {
  const inputs = []
  const inputGroups = {}
  const outputs = []
  Object.keys(fieldsData.value).forEach((field) => {
    if (fieldsData.value[field].is_output) {
      if (fieldsData.value[field].condition) {
        const condition = fieldsData.value[field].condition
        if (!condition(fieldsData.value)) {
          fieldsData.value[field].hide = true
        } else {
          fieldsData.value[field].hide = false
        }
      }
      outputs.push(field)
    } else {
      if (fieldsData.value[field].condition) {
        const condition = fieldsData.value[field].condition
        if (!condition(fieldsData.value)) {
          fieldsData.value[field].hide = true
        } else {
          fieldsData.value[field].hide = false
        }
      }
      if (fieldsData.value[field].group) {
        if (!inputGroups[fieldsData.value[field].group]) {
          inputGroups[fieldsData.value[field].group] = []
        }
        inputGroups[fieldsData.value[field].group].push(field)
      } else {
        inputs.push(field)
      }
    }
  })
  return { inputs, inputGroups, outputs }
}

const inputFields = ref([])
const inputGroupFields = ref({})
const outputFields = ref([])
const { inputs, inputGroups, outputs } = updateFields()
inputFields.value = inputs
inputGroupFields.value = inputGroups
outputFields.value = outputs

watch(() => fieldsData.value, () => {
  const { inputs, inputGroups, outputs } = updateFields()
  inputFields.value = inputs
  inputGroupFields.value = inputGroups
  outputFields.value = outputs
}, { deep: true })

const collapseChanged = (data) => {
  for (const key in fieldsData.value) {
    if (fieldsData.value[key].group === data.id) {
      fieldsData.value[key].group_collpased = data.collpased
    }
  }
}
</script>

<template>
  <div class="node-wrapper">
    <a-flex justify="space-between" align="center" class="hover-buttons">
      <a-flex gap="small" align="center">
        <QuestionPopover :size="18"
          :contents="[description, { type: 'link', text: t('components.nodes.baseNode.document_link'), url: `${websiteBase}${props.documentPath}` }]"
          v-if="props.documentPath.length > 0" class="hint-popover" />
        <a-tooltip :title="t('components.nodes.baseNode.view_node_help_document')">
          <a-button type="text" size="large" @click="documentModalOpen = true">
            <template #icon>
              <BookOpen fill="#28c5e5" />
            </template>
          </a-button>
          <DocumentModal v-model:open="documentModalOpen" :slug="documentSlug" :nodeType="documentNodeType"
            :title="title" />
        </a-tooltip>
      </a-flex>
      <a-flex gap="small" align="center">
        <a-tooltip color="blue" :title="t('components.nodes.baseNode.clone_node')">
          <a-button type="text" size="large" @click="pushMessage('clone')">
            <template #icon>
              <Copy fill="#28c5e5" />
            </template>
          </a-button>
        </a-tooltip>
        <a-tooltip color="red" :title="t('components.nodes.baseNode.delete_node')">
          <a-button type="text" size="large" @click="pushMessage('delete')">
            <template #icon>
              <Delete fill="#28c5e5" />
            </template>
          </a-button>
        </a-tooltip>
      </a-flex>
    </a-flex>
    <div class="node" :style="style" :class="{ 'shadow-node': node.shadow }">
      <a-flex v-if="node.shadow" align="center" justify="center" vertical class="shadow-node-overlay">
        <div class="confirm-shadow-node-container shadow-node-action-area" @click="pushMessage('confirmShadowNode')">
          <CheckOne theme="filled" size="48" fill="#52c41a" class="check-icon" />
        </div>
        <div class="reject-shadow-node-container shadow-node-action-area" @click="pushMessage('rejectShadowNode')">
          <CloseOne theme="filled" size="48" fill="#f5222d" class="close-icon" />
        </div>
      </a-flex>
      <div style="width: 100%;">
        <div v-if="debug" :class="['debug-info', debug.run_time > 0 ? 'executed-node' : 'not-executed-node']">
          <a-flex justify="space-between">
            <a-typography-text v-if="debug.run_time > 0">
              <CheckOne theme="filled" fill="#52c41a" />
              {{ t('components.nodes.baseNode.run_time', { time: debug.run_time.toFixed(2) }) }}
            </a-typography-text>
            <a-typography-text v-else>
              <Help theme="filled" fill="#faad14" />
              {{ t('components.nodes.baseNode.no_run_record') }}
            </a-typography-text>
          </a-flex>
        </div>
        <div class="title-container">
          <a-flex justify="space-between" align="center" gap="10">
            <a-typography-title class="title" :level="3" style="flex-grow: 1;">
              {{ title }}
            </a-typography-title>
          </a-flex>
        </div>

        <div class="main-container">
          <slot name="main"></slot>
          <template v-if="!$slots.main">
            <a-flex vertical gap="small">
              <template v-for="field in inputFields">
                <a-tooltip :title="fieldsData[field].has_tooltip ? t(`${translatePrefix}.${field}_tip`) : ''"
                  placement="left" :class="{ 'hide-field': fieldsData[field].hide }">
                  <ListField v-if="fieldsData[field].field_type == 'list'" :name="t(`${translatePrefix}.${field}`)"
                    :required="fieldsData[field].required" type="target" v-model:data="fieldsData[field]">
                  </ListField>
                  <BaseField v-else :name="t(`${translatePrefix}.${field}`)" :required="fieldsData[field].required"
                    type="target" v-model:data="fieldsData[field]"
                    :nameOnly="['', 'checkbox'].includes(fieldsData[field].field_type)" />
                </a-tooltip>
              </template>
              <template v-for="(fields, group) in inputGroupFields">
                <BaseFieldsCollapse :id="group" :collapse="fieldsData[fields[0]].group_collpased"
                  :name="group === 'default' ? t('common.more_settings') : t(`${translatePrefix}.group_${group}`)"
                  @collapseChanged="collapseChanged">
                  <template v-for="field in fields">
                    <a-tooltip :title="fieldsData[field].has_tooltip ? t(`${translatePrefix}.${field}_tip`) : ''"
                      placement="left" :class="{ 'hide-field': fieldsData[field].hide }">
                      <ListField v-if="fieldsData[field].field_type == 'list'" :name="t(`${translatePrefix}.${field}`)"
                        :required="fieldsData[field].required" type="target" v-model:data="fieldsData[field]">
                      </ListField>
                      <BaseField v-else :name="t(`${translatePrefix}.${field}`)" :required="fieldsData[field].required"
                        type="target" v-model:data="fieldsData[field]"
                        :nameOnly="['', 'checkbox'].includes(fieldsData[field].field_type)" />
                    </a-tooltip>
                  </template>
                </BaseFieldsCollapse>
              </template>
            </a-flex>
          </template>
        </div>

        <div v-if="outputFields.length > 0" class="output-container">
          <slot name="output"></slot>
          <template v-if="!$slots.output">
            <a-flex vertical style="width: 100%;">
              <a-tooltip v-for="field in outputFields"
                :title="fieldsData[field].has_tooltip ? t(`${translatePrefix}.${field}_tip`) : ''" placement="right">
                <BaseField :name="t(`${translatePrefix}.${field}`)" v-model:data="fieldsData[field]" type="source"
                  :class="{ 'hide-field': fieldsData[field].hide }" nameOnly />
              </a-tooltip>
            </a-flex>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.node-wrapper {
  position: relative;
}

.node {
  box-shadow: 0 0 0 1px #28c5e5;
  border: 1px solid #28c5e5;
  border-radius: 10px;
  background: var(--component-background);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  min-width: 300px;
  max-width: 400px;
  transition: box-shadow .3s;
  position: relative;
  z-index: 1;
}

.node:hover {
  box-shadow: 0 0 0 4px #28c5e5;
}

.node .debug-info {
  padding: 10px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
}

.node .debug-info.executed-node {
  background-color: #f6ffed;
}

.node .debug-info.not-executed-node {
  background-color: #fffbe6;
}

.node .debug-info span {
  color: rgba(29, 29, 31, 0.88);
}

.node .title-container {
  padding: 10px;
  padding-top: 20px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
}

.node .title-container .hint-popover {
  font-size: 14px;
  color: #a0a0a0;
}

.node .main-container {
  margin-bottom: 10px;
}

.node .output-container {
  padding: 10px 0;
  display: flex;
  border-top: 1px solid #28c5e5;
}

.node .output-container:empty {
  padding: 0;
}

.node .output-container span {
  float: right;
  margin-right: 10px;
  font-size: 18px;
}

.vue-flow .vue-flow__node.selected .node {
  box-shadow: 0 0 0 3px #28c5e5;
  border: 1px solid #28c5e5;
}

.vue-flow .vue-flow__node .node .title {
  color: #179ebf !important;
  transition: color .3s;
}

.vue-flow .vue-flow__node:hover .node .title {
  color: #28c5e5 !important;
}

.vue-flow .vue-flow__node:hover .node .template-item-field-text .field-name {
  color: #28c5e5 !important;
}

.vue-flow .vue-flow__node .node .handle.source-handle {
  background-color: #28c5e5;
}

.vue-flow .vue-flow__node .node .handle.target-handle {
  background-color: #28c5e5;
}

.vue-flow .vue-flow__node .node .handle {
  border-color: #fff;
  border-width: 3px;
  width: 12px;
  height: 12px;
  transition: width .3s, height .3s;
}

.vue-flow .vue-flow__node .node .handle:hover {
  width: 20px;
  height: 20px;
}

.hide-field {
  display: none !important;
}

.node.shadow-node {
  opacity: 0.5;
}

.shadow-node-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.164);
  z-index: 1;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.shadow-node-overlay .shadow-node-action-area {
  display: flex;
  align-items: center;
  justify-content: center;
}

.shadow-node-overlay .confirm-shadow-node-container {
  width: 100%;
  flex-grow: 1;
  cursor: pointer;
}

.shadow-node-overlay .confirm-shadow-node-container:hover {
  background-color: rgba(82, 196, 26, 0.2);
  transition: background-color 0.3s ease;
}

.shadow-node-overlay .reject-shadow-node-container {
  width: 100%;
  flex-grow: 1;
  cursor: pointer;
}

.shadow-node-overlay .reject-shadow-node-container:hover {
  background-color: rgba(245, 34, 45, 0.2);
  transition: background-color 0.3s ease;
}

.node.shadow-node {
  position: relative;
  opacity: 0.5;
}

.hover-buttons {
  width: 100%;
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%) translateY(-100%);
  display: flex;
  gap: 10px;
  opacity: 0;
  transition: opacity 0.3s ease, transform 0.3s ease;
  z-index: 0;
}

.node-wrapper:hover .hover-buttons {
  opacity: 1;
  transform: translateX(-50%) translateY(-120%);
  z-index: 2;
}

.hover-button {
  transition: transform 0.3s ease;
}
</style>