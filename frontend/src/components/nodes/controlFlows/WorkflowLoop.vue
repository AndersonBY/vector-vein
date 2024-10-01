<script setup>
import { ref, reactive, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from "vue-router"
import { Edit } from '@icon-park/vue-next'
import { nonFormItemsTypes } from '@/utils/workflow'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import BaseFieldsCollapse from '@/components/nodes/BaseFieldsCollapse.vue'
import WorkflowSelect from '@/components/workspace/WorkflowSelect.vue'
import SimpleFormItem from '@/components/SimpleFormItem.vue'
import TemplateEditorModal from '@/components/nodes/TemplateEditorModal.vue'
import { deepCopy } from '@/utils/util'
import { getUIDesignFromWorkflow } from '@/utils/workflow'
import { workflowAPI, workflowTemplateAPI } from "@/api/workflow"
import { createTemplateData } from './WorkflowLoop'

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

const internalFields = [
  'workflow_id',
  'loop_count',
  'max_loop_count',
  'initial_values',
  'assignment_in_loop',
  'loop_end_condition',
  'output_field_condition_field',
  'output_field_condition_operator',
  'output_field_condition_value',
  'judgement_model',
  'judgement_prompt',
  'judgement_end_output',
]

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

const inputFieldsOptions = ref([])
const outputFieldsOptions = ref([])
const outputFields = ref({})

onBeforeMount(async () => {
  await setWorkflowData()
})

async function setWorkflowData(data = null) {
  if (data === null && fieldsData.value.workflow_id.value.length == 0) {
    return
  }
  if (data === null) {
    const wid = fieldsData.value.workflow_id.value
    let requestAPI = props.data.is_template ? workflowTemplateAPI : workflowAPI
    const workflowResponse = await requestAPI('get', { wid: wid })
    if (workflowResponse.status != 200) {
      return
    }
    const uiDesign = getUIDesignFromWorkflow(workflowResponse.data)
    const reactiveUIDesign = reactive(uiDesign)
    data = {
      wid: wid,
      isTemplate: props.data.is_template,
      title: workflowResponse.data.title,
      inputFields: reactiveUIDesign.inputFields,
      outputNodes: reactiveUIDesign.outputNodes,
      workflowInvokeOutputNodes: reactiveUIDesign.workflowInvokeOutputNodes,
      update_time: workflowResponse.data.update_time,
    }

    // 从原来的 fieldsData 中恢复 inputFieldsOptions, outputFieldsOptions, outputFields
    inputFieldsOptions.value = []
    outputFieldsOptions.value = []
    outputFields.value = {}

    for (const [key, field] of Object.entries(fieldsData.value)) {
      if (!internalFields.includes(key)) {
        if (!field.is_output) {
          // 恢复 inputFieldsOptions
          inputFieldsOptions.value.push({
            label: key,
            value: key
          })
        } else {
          // 恢复 outputFieldsOptions 和 outputFields
          outputFieldsOptions.value.push({
            label: field.display_name,
            value: key
          })
          outputFields.value[key] = ''
        }
      }
    }

    // 恢复 assignment_in_loop
    fieldsData.value.assignment_in_loop.value = fieldsData.value.assignment_in_loop.value

    return
  }
  props.data.seleted_workflow_title = data.title
  seletedWorkflowTitle.value = data.title
  props.data.is_template = data.isTemplate
  isTemplate.value = data.isTemplate
  fieldsData.value.workflow_id.value = data.wid
  Object.keys(fieldsData.value).forEach((field) => {
    if (!internalFields.includes(field)) {
      delete fieldsData.value[field]
    }
  })
  const fieldNamesIds = new Set()
  const inputFieldNamesIds = new Set()
  inputFieldsOptions.value = []
  data.inputFields.forEach((field) => {
    if (nonFormItemsTypes.includes(field.field_type)) return
    let fieldKey = field.name
    while (fieldNamesIds.has(fieldKey)) {
      fieldKey = `${fieldKey}_${Math.floor(Math.random() * 1000)}`
    }
    fieldsData.value[fieldKey] = deepCopy(field)
    fieldsData.value[fieldKey].node = fieldsData.value[fieldKey].nodeId
    fieldsData.value[fieldKey].name = fieldKey
    fieldNamesIds.add(fieldKey)
    inputFieldNamesIds.add(field.name)
    inputFieldsOptions.value.push({
      label: fieldsData.value[fieldKey].display_name,
      value: fieldKey,
    })
  })

  outputFieldsOptions.value = []
  outputFields.value = {}
  const outputNodes = data.outputNodes.concat(data.workflowInvokeOutputNodes)
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
      fieldsData.value[fieldKey] = deepCopy(node.data.template.text)
      fieldName = `${fieldName}_${node.data.template.output_title.value}`
      fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.data.template.output_title.value || 'text'}`
      outputFieldKey = 'text'
    } else if (node.type == 'Audio') {
      fieldsData.value[fieldKey] = deepCopy(node.data.template.audio_url || {})
      fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
      outputFieldKey = 'audio_url'
    } else if (['Document', 'Table', 'Html'].includes(node.type)) {
      fieldsData.value[fieldKey] = deepCopy(node.data.template.output || {})
      fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
      outputFieldKey = 'output'
    } else if (['Mindmap', 'Mermaid'].includes(node.type)) {
      fieldsData.value[fieldKey] = deepCopy(node.data.template.content)
      fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
      outputFieldKey = 'content'
    } else if (node.type == 'Echarts') {
      fieldsData.value[fieldKey] = deepCopy(node.data.template.option)
      fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.type}`
      outputFieldKey = 'option'
    } else if (node.type == 'WorkflowInvokeOutput') {
      fieldsData.value[fieldKey] = deepCopy(node.data.template.value)
      fieldsData.value[fieldKey].display_name = `${nodeIdSlice}_${node.data.template.display_name.value}`
      outputFieldKey = 'value'
    }
    fieldsData.value[fieldKey].id = fieldKey
    fieldsData.value[fieldKey].name = fieldName
    fieldsData.value[fieldKey].show = false
    fieldsData.value[fieldKey].is_output = true
    fieldsData.value[fieldKey].node = node.id
    fieldsData.value[fieldKey].output_field_key = outputFieldKey

    outputFieldsOptions.value.push({
      label: fieldsData.value[fieldKey].display_name,
      value: fieldKey,
    })
    outputFields.value[fieldKey] = ''
  })

  fieldsData.value.assignment_in_loop.value = {}
  inputFieldNamesIds.forEach((field) => {
    fieldsData.value.assignment_in_loop.value[field] = {
      source: 'constant',
      value: fieldsData.value[field].value,
    }
  })

  fieldsData.value.output_field_condition_field.options = outputFieldsOptions.value
}

const workflowSelectModal = reactive({
  open: false,
  data: {},
  onWorkflowSelect: () => {
    setWorkflowData(workflowSelectModal.data)
    workflowSelectModal.open = false
  },
})

const collapseChanged = (data) => {
  for (const key in fieldsData.value) {
    if (fieldsData.value[key].group === data.id) {
      fieldsData.value[key].group_collpased = data.collpased
    }
  }
}

const assignmentInLoopSourceOptions = [
  {
    label: t('components.nodes.controlFlows.WorkflowLoop.constant'),
    value: 'constant',
  },
  {
    label: t('components.nodes.controlFlows.WorkflowLoop.input_field'),
    value: 'input_field',
  },
  {
    label: t('components.nodes.controlFlows.WorkflowLoop.output_field'),
    value: 'output_field',
  },
  {
    label: t('components.nodes.controlFlows.WorkflowLoop.output_field_cumulative'),
    value: 'output_field_cumulative',
  },
  {
    label: t('components.nodes.controlFlows.WorkflowLoop.loop_count'),
    value: 'loop_count',
  },
]

const openTemplateEditor = ref(false)
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.controlFlows.WorkflowLoop"
    :debug="props.data.debug" documentPath="/help/docs/control-flows#node-WorkflowLoop">
    <template #main>
      <a-flex vertical gap="small">
        <div style="padding: 5px 10px;">
          <template v-if="seletedWorkflowTitle">
            <a-typography-text type="secondary">
              {{ t('components.nodes.controlFlows.WorkflowLoop.selected_workflow') }}:
            </a-typography-text>
            <a-typography-text>
              {{ seletedWorkflowTitle }}
            </a-typography-text>
          </template>
          <a-button type="dashed" block @click="workflowSelectModal.open = true">
            {{ t('components.nodes.controlFlows.WorkflowLoop.select_workflow') }}
          </a-button>
          <a-modal :open="workflowSelectModal.open"
            :title="t('components.nodes.controlFlows.WorkflowLoop.select_workflow')" width="80vw"
            @cancel="workflowSelectModal.open = false" :footer="null">
            <WorkflowSelect :showUser="showUser" :selectType="selectType" v-model="workflowSelectModal.data"
              @selected="workflowSelectModal.onWorkflowSelect" />
          </a-modal>
        </div>

        <BaseField :name="t('components.nodes.controlFlows.WorkflowLoop.workflow_id')" required type="target"
          v-model:data="fieldsData.workflow_id">
          <a-input disabled v-model:value="fieldsData.workflow_id.value"
            :placeholder="fieldsData.workflow_id.placeholder" class="nodrag" />
        </BaseField>

        <BaseField :name="t('components.nodes.controlFlows.WorkflowLoop.max_loop_count')" required type="target"
          v-model:data="fieldsData.max_loop_count" />

        <BaseFieldsCollapse v-if="fieldsData.workflow_id.value.length > 0" id="initial_values"
          :collapse="fieldsData.initial_values.group_collpased"
          :name="t('components.nodes.controlFlows.WorkflowLoop.workflow_fields_initial_values')"
          @collapseChanged="collapseChanged">
          <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
            <BaseField v-if="!internalFields.includes(field) && !fieldsData[field].is_output"
              :name="`${fieldsData[field].display_name}: ${fieldsData[field].type}`" required type="target"
              @delete="removeField(field)" v-model:data="fieldsData[field]">
              <a-select v-if="fieldsData[field].field_type == 'select'" style="width: 100%;"
                v-model:value="fieldsData[field].value" :options="fieldsData[field].options" class="nodrag" />
              <a-textarea v-else-if="fieldsData[field].field_type == 'textarea'" v-model:value="fieldsData[field].value"
                :autoSize="{ minRows: 1, maxRows: 10 }" :showCount="true" :placeholder="fieldsData[field].placeholder"
                class="nodrag" />
              <a-input v-else-if="fieldsData[field].field_type == 'input'" v-model:value="fieldsData[field].value"
                :placeholder="fieldsData[field].placeholder" class="nodrag" />
              <a-input-number v-else-if="fieldsData[field].field_type == 'number'"
                v-model:value="fieldsData[field].value" :controls="false" style="width: 100%;" class="nodrag" />

              <template #inline>
                <a-checkbox v-if="fieldsData[field].field_type == 'checkbox'" v-model:checked="fieldsData[field].value"
                  class="nodrag">
                </a-checkbox>
              </template>
            </BaseField>
          </template>
        </BaseFieldsCollapse>

        <BaseFieldsCollapse v-if="fieldsData.workflow_id.value.length > 0" id="assignment_in_loop"
          :collapse="fieldsData.assignment_in_loop.group_collpased"
          :name="t('components.nodes.controlFlows.WorkflowLoop.workflow_fields_assignment_in_loop')"
          @collapseChanged="collapseChanged">
          <a-flex vertical gap="small" style="padding: 5px 10px;">
            <template v-for="(field, fieldIndex) in Object.keys(fieldsData.assignment_in_loop.value)" :key="fieldIndex">
              <SimpleFormItem
                :title="`${fieldsData[field].display_name}: ${t('components.nodes.controlFlows.WorkflowLoop.source')}`"
                type="select" layout="vertical" :options="assignmentInLoopSourceOptions"
                v-model="fieldsData.assignment_in_loop.value[field].source" />
              <SimpleFormItem v-if="fieldsData.assignment_in_loop.value[field].source === 'constant'"
                :title="`${fieldsData[field].display_name}: ${t('components.nodes.controlFlows.WorkflowLoop.value')}`"
                type="input" layout="vertical" v-model="fieldsData.assignment_in_loop.value[field].value" />
              <SimpleFormItem v-else-if="fieldsData.assignment_in_loop.value[field].source === 'input_field'"
                :title="`${fieldsData[field].display_name}: ${t('components.nodes.controlFlows.WorkflowLoop.source_input_field')}`"
                type="select" layout="vertical" :options="inputFieldsOptions"
                v-model="fieldsData.assignment_in_loop.value[field].value" />
              <SimpleFormItem v-else-if="fieldsData.assignment_in_loop.value[field].source === 'output_field'"
                :title="`${fieldsData[field].display_name}: ${t('components.nodes.controlFlows.WorkflowLoop.source_output_field')}`"
                type="select" layout="vertical" :options="outputFieldsOptions"
                v-model="fieldsData.assignment_in_loop.value[field].value" />
              <a-tooltip v-else-if="fieldsData.assignment_in_loop.value[field].source === 'output_field_cumulative'"
                :title="t('components.nodes.controlFlows.WorkflowLoop.output_field_cumulative_tip')" placement="left">
                <SimpleFormItem
                  :title="`${fieldsData[field].display_name}: ${t('components.nodes.controlFlows.WorkflowLoop.source_output_field')}`"
                  type="select" layout="vertical" :options="outputFieldsOptions"
                  v-model="fieldsData.assignment_in_loop.value[field].value" />
              </a-tooltip>
            </template>
          </a-flex>
        </BaseFieldsCollapse>

        <BaseFieldsCollapse v-if="fieldsData.workflow_id.value.length > 0" id="loop_end_condition"
          :collapse="fieldsData.loop_end_condition.group_collpased"
          :name="t('components.nodes.controlFlows.WorkflowLoop.loop_end_condition')" @collapseChanged="collapseChanged">
          <BaseField :name="t('components.nodes.controlFlows.WorkflowLoop.loop_end_condition')" required type="target"
            v-model:data="fieldsData.loop_end_condition" />
          <template v-if="fieldsData.loop_end_condition.value == 'output_field_condition'">
            <BaseField
              v-for="(field, fieldIndex) in ['output_field_condition_field', 'output_field_condition_operator', 'output_field_condition_value']"
              :key="fieldIndex" :name="t(`components.nodes.controlFlows.WorkflowLoop.${field}`)"
              :required="fieldsData[field]?.required" type="target" v-model:data="fieldsData[field]" />
          </template>
          <template v-if="fieldsData.loop_end_condition.value == 'ai_model_judgement'">
            <BaseField :name="t('components.nodes.controlFlows.WorkflowLoop.judgement_model')"
              :required="fieldsData.judgement_model?.required" type="target"
              v-model:data="fieldsData.judgement_model" />

            <BaseField :name="t('components.nodes.controlFlows.WorkflowLoop.judgement_prompt')" required type="target"
              v-model:data="fieldsData.judgement_prompt">
              <a-typography-paragraph :ellipsis="{ row: 1, expandable: false }"
                :content="fieldsData.judgement_prompt.value"></a-typography-paragraph>
              <a-button block type="dashed" @click="openTemplateEditor = true">
                <template #icon>
                  <Edit />
                </template>
                {{ t('components.nodes.textProcessing.TemplateCompose.open_template_editor') }}
              </a-button>
              <TemplateEditorModal v-model:open="openTemplateEditor"
                v-model:template="fieldsData.judgement_prompt.value" :fields="outputFields" />
            </BaseField>

            <a-tooltip :title="t('components.nodes.controlFlows.WorkflowLoop.judgement_end_output_tip')"
              placement="left">
              <BaseField :name="t('components.nodes.controlFlows.WorkflowLoop.judgement_end_output')"
                :required="fieldsData.judgement_end_output?.required" type="target"
                v-model:data="fieldsData.judgement_end_output" />
            </a-tooltip>
          </template>
        </BaseFieldsCollapse>
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