<script setup>
import { watch, ref } from 'vue'
import { Delete, Copy, CheckOne, Help } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import QuestionPopover from '@/components/QuestionPopover.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ListField from '@/components/nodes/ListField.vue'

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
  documentLink: {
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
  const outputs = []
  Object.keys(fieldsData.value).forEach((field) => {
    if (fieldsData.value[field].is_output) {
      if (fieldsData.value[field].condition) {
        const condition = fieldsData.value[field].condition
        if (condition(fieldsData.value)) {
          outputs.push(field)
        }
      } else {
        outputs.push(field)
      }
    } else {
      if (fieldsData.value[field].condition) {
        const condition = fieldsData.value[field].condition
        if (condition(fieldsData.value)) {
          inputs.push(field)
        }
      } else {
        inputs.push(field)
      }
    }
  })
  return { inputs, outputs }
}

const inputFields = ref([])
const outputFields = ref([])
const { inputs, outputs } = updateFields()
inputFields.value = inputs
outputFields.value = outputs

watch(() => fieldsData.value, () => {
  const { inputs, outputs } = updateFields()
  inputFields.value = inputs
  outputFields.value = outputs
}, { deep: true })
</script>

<template>
  <div class="node" :style="style">
    <div style="width: 100%;">
      <div v-if="debug" :class="['debug-info', debug.run_time >= 0 ? 'executed-node' : 'not-executed-node']">
        <a-flex justify="space-between">
          <a-typography-text v-if="debug.run_time >= 0">
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
            <QuestionPopover
              :contents="[description, { type: 'link', text: t('components.nodes.baseNode.document_link'), url: props.documentLink }]"
              v-if="props.documentLink.length > 0" class="hint-popover" />
          </a-typography-title>
          <a-tooltip color="blue" :title="t('components.nodes.baseNode.clone_node')">
            <a-button type="text" size="small" @click="pushMessage('clone')">
              <template #icon>
                <Copy fill="#28c5e5" />
              </template>
            </a-button>
          </a-tooltip>
          <a-tooltip color="red" :title="t('components.nodes.baseNode.delete_node')">
            <a-button type="text" size="small" @click="pushMessage('delete')">
              <template #icon>
                <Delete fill="#28c5e5" />
              </template>
            </a-button>
          </a-tooltip>
        </a-flex>
      </div>

      <div class="main-container">
        <slot name="main"></slot>
        <template v-if="!$slots.main">
          <a-flex vertical gap="small">
            <template v-for="field in inputFields">
              <a-tooltip :title="fieldsData[field].has_tooltip ? t(`${translatePrefix}.${field}_tip`) : ''"
                placement="left">
                <ListField v-if="fieldsData[field].field_type == 'list'" :name="t(`${translatePrefix}.${field}`)"
                  :required="fieldsData[field].required" type="target" v-model:data="fieldsData[field]">
                </ListField>
                <BaseField v-else :name="t(`${translatePrefix}.${field}`)" :required="fieldsData[field].required"
                  type="target" v-model:data="fieldsData[field]"
                  :nameOnly="['', 'checkbox'].includes(fieldsData[field].field_type)" />
              </a-tooltip>
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
                nameOnly />
            </a-tooltip>
          </a-flex>
        </template>
      </div>
    </div>
  </div>
</template>

<style>
.node {
  box-shadow: 0 0 0 1px #28c5e5;
  border: 1px solid #28c5e5;
  border-radius: 10px;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  min-width: 300px;
  max-width: 400px;
  transition: box-shadow .3s;
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
</style>