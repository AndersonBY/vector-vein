<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from "vue-router"
import { nonFormItemsTypes } from '@/utils/workflow'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import WorkflowSelect from '@/components/workspace/WorkflowSelect.vue'
import { createTemplateData } from './WorkflowInvoke'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
})

const route = useRoute()
const selectType = route.path.startsWith('/workspace/workflow/editor/') ? 'workflow' : 'officialTemplate'
const showUser = selectType == 'template'

const { t } = useI18n()

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

const seletedWorkflowTitle = ref(props.data.seleted_workflow_title)
const isTemplate = ref(props.data.is_template)

const workflowSelectModal = reactive({
  open: false,
  data: {},
  onWorkflowSelect: () => {
    props.data.seleted_workflow_title = workflowSelectModal.data.title
    seletedWorkflowTitle.value = workflowSelectModal.data.title
    props.data.is_template = workflowSelectModal.data.isTemplate
    isTemplate.value = workflowSelectModal.data.isTemplate
    fieldsData.value.workflow_id.value = workflowSelectModal.data.wid
    Object.keys(fieldsData.value).forEach((field) => {
      if (!['workflow_id'].includes(field)) {
        delete fieldsData.value[field]
      }
    })
    workflowSelectModal.data.inputFields.forEach((field) => {
      if (nonFormItemsTypes.includes(field.field_type)) return
      fieldsData.value[field.name] = JSON.parse(JSON.stringify(field))
      fieldsData.value[field.name].node = fieldsData.value[field.name].nodeId
    })
    const fieldNamesIds = new Set()
    const outputNodes = workflowSelectModal.data.outputNodes.concat(workflowSelectModal.data.workflowInvokeOutputNodes)
    outputNodes.forEach((node) => {
      if (node.field_type == 'typography-paragraph') return
      const nodeIdSlice = node.id.slice(0, 8)
      let fieldKey = `${nodeIdSlice}_${node.type}`
      while (fieldNamesIds.has(fieldKey)) {
        fieldKey = `${fieldKey}_${Math.floor(Math.random() * 1000)}`
      }
      fieldNamesIds.add(fieldKey)
      let fieldName = fieldKey
      let outputFieldKey = ''

      if (node.type == 'Text') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.text))
        fieldName = `${fieldName}_${node.data.template.output_title.value}`
        fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.data.template.output_title.value || 'text'}`
        outputFieldKey = 'text'
      } else if (node.type == 'Audio') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.audio_url || {}))
        fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
        outputFieldKey = 'audio_url'
      } else if (node.type == 'Mindmap') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.content))
        fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
        outputFieldKey = 'content'
      } else if (node.type == 'Mermaid') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.content))
        fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
        outputFieldKey = 'content'
      } else if (node.type == 'Echarts') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.option))
        fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
        outputFieldKey = 'option'
      } else if (node.type == 'WorkflowInvokeOutput') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.value))
        fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.data.template.display_name.value}`
        outputFieldKey = 'value'
      }
      fieldsData.value[fieldKey].id = fieldKey
      fieldsData.value[fieldKey].name = fieldName
      fieldsData.value[fieldKey].show = false
      fieldsData.value[fieldKey].is_output = true
      fieldsData.value[fieldKey].node = node.id
      fieldsData.value[fieldKey].output_field_key = outputFieldKey
    })
    workflowSelectModal.open = false
  },
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.tools.WorkflowInvoke"
    :debug="props.data.debug" documentLink="https://vectorvein.com/help/docs/tools#h2-12">
    <template #main>
      <a-flex vertical gap="small">
        <div style="padding: 5px 10px;">
          <template v-if="seletedWorkflowTitle">
            <a-typography-text type="secondary">
              {{ t('components.nodes.tools.WorkflowInvoke.selected_workflow') }}:
            </a-typography-text>
            <a-typography-text>
              {{ seletedWorkflowTitle }}
            </a-typography-text>
          </template>
          <a-button type="dashed" block @click="workflowSelectModal.open = true">
            {{ t('components.nodes.tools.WorkflowInvoke.select_workflow') }}
          </a-button>
          <a-modal :open="workflowSelectModal.open" :title="t('components.nodes.tools.WorkflowInvoke.select_workflow')"
            width="80vw" @cancel="workflowSelectModal.open = false" :footer="null">
            <WorkflowSelect :showUser="showUser" :selectType="selectType" v-model="workflowSelectModal.data"
              @selected="workflowSelectModal.onWorkflowSelect" />
          </a-modal>
        </div>

        <BaseField :name="t('components.nodes.tools.WorkflowInvoke.workflow_id')" required type="target"
          v-model:data="fieldsData.workflow_id">
          <a-input disabled v-model:value="fieldsData.workflow_id.value"
            :placeholder="fieldsData.workflow_id.placeholder" />
        </BaseField>

        <a-divider v-if="fieldsData.workflow_id.value.length > 0">
          {{ t('components.nodes.tools.WorkflowInvoke.workflow_fields') }}
        </a-divider>

        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
          <BaseField v-if="!['workflow_id'].includes(field) && !fieldsData[field].is_output"
            :name="`${fieldsData[field].display_name}: ${fieldsData[field].type}`" required type="target"
            @delete="removeField(field)" v-model:data="fieldsData[field]">
            <a-select style="width: 100%;" v-model:value="fieldsData[field].value" :options="fieldsData[field].options"
              v-if="fieldsData[field].field_type == 'select'" />
            <a-textarea v-model:value="fieldsData[field].value" :autoSize="{ minRows: 1, maxRows: 10 }"
              :showCount="true" :placeholder="fieldsData[field].placeholder"
              v-else-if="fieldsData[field].field_type == 'textarea'" />
            <a-input v-model:value="fieldsData[field].value" :placeholder="fieldsData[field].placeholder"
              v-else-if="fieldsData[field].field_type == 'input'" />
            <a-input-number v-model:value="fieldsData[field].value" :controls="false" style="width: 100%;"
              v-else-if="fieldsData[field].field_type == 'number'" />

            <template #inline>
              <a-checkbox v-model:checked="fieldsData[field].value" v-if="fieldsData[field].field_type == 'checkbox'">
              </a-checkbox>
            </template>
          </BaseField>
        </template>
      </a-flex>
    </template>
    <template #output>
      <a-flex vertical style="width: 100%;">
        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
          <BaseField v-if="fieldsData[field].is_output" :name="fieldsData[field].display_name" type="source" nameOnly
            v-model:data="fieldsData[field]">
          </BaseField>
        </template>
      </a-flex>
    </template>
  </BaseNode>
</template>