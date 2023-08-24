<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { nonFormItemsTypes } from '@/utils/workflow'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import WorkflowSelect from '@/components/workspace/WorkflowSelect.vue'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  templateData: {
    "description": "description",
    "task_name": "tools.workflow_invoke",
    "has_inputs": true,
    "template": {
      "workflow_id": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "workflow_id",
        "display_name": "workflow_id",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "fail_all": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": false,
        "password": false,
        "name": "fail_all",
        "display_name": "fail_all",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "checkbox"
      },
      "list_input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": false,
        "password": false,
        "name": "list_input",
        "display_name": "list_input",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "checkbox"
      },
    }
  }
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
const seletedWorkflowTitle = ref(props.data.seleted_workflow_title)

const workflowSelectModal = reactive({
  open: false,
  data: {},
  onWorkflowSelect: () => {
    props.data.seleted_workflow_title = workflowSelectModal.data.title
    seletedWorkflowTitle.value = workflowSelectModal.data.title
    fieldsData.value.workflow_id.value = workflowSelectModal.data.wid
    Object.keys(fieldsData.value).forEach((field) => {
      if (!['workflow_id', 'fail_all', 'list_input'].includes(field)) {
        delete fieldsData.value[field]
      }
    })
    workflowSelectModal.data.input_fields.forEach((field) => {
      if (nonFormItemsTypes.includes(field.field_type)) return
      fieldsData.value[field.name] = JSON.parse(JSON.stringify(field))
      fieldsData.value[field.name].node = fieldsData.value[field.name].nodeId
    })
    const fieldNamesIds = new Set()
    workflowSelectModal.data.output_nodes.forEach((node) => {
      let fieldKey = `${node.id.slice(0, 8)}_${node.type}`
      while (fieldNamesIds.has(fieldKey)) {
        fieldKey = `${fieldKey}_${Math.floor(Math.random() * 1000)}`
      }
      fieldNamesIds.add(fieldKey)
      let fieldName = fieldKey
      let outputFieldKey = ''
      if (node.type == 'Text') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.text))
        fieldName = `${fieldName}_${node.data.template.output_title.value}`
        outputFieldKey = 'text'
      } else if (node.type == 'Audio') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.audio_url || {}))
        outputFieldKey = 'audio_url'
      } else if (node.type == 'Mindmap') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.content))
        outputFieldKey = 'content'
      } else if (node.type == 'Mermaid') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.content))
        outputFieldKey = 'content'
      } else if (node.type == 'Echarts') {
        fieldsData.value[fieldKey] = JSON.parse(JSON.stringify(node.data.template.option))
        outputFieldKey = 'option'
      }
      fieldsData.value[fieldKey].name = fieldName
      fieldsData.value[fieldKey].display_name = fieldName
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
  <BaseNode :nodeId="id" :title="t('components.nodes.tools.WorkflowInvoke.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/tools#h2-12">
    <template #main>
      <a-row type="flex">

        <a-col :span="24" style="padding: 5px 10px;">
          <template v-if="seletedWorkflowTitle">
            <a-typography-text type="secondary">
              {{ t('components.nodes.tools.WorkflowInvoke.selected_workflow') }}:
            </a-typography-text>
            <a-typography-text>
              {{ seletedWorkflowTitle }}
            </a-typography-text>
          </template>
          <a-button type="primary" block @click="workflowSelectModal.open = true">
            {{ t('components.nodes.tools.WorkflowInvoke.select_workflow') }}
          </a-button>
          <a-modal :open="workflowSelectModal.open" :title="t('components.nodes.tools.WorkflowInvoke.select_workflow')"
            width="80vw" @cancel="workflowSelectModal.open = false" :footer="null">
            <WorkflowSelect v-model="workflowSelectModal.data" @selected="workflowSelectModal.onWorkflowSelect" />
          </a-modal>
        </a-col>

        <a-col :span="24">
          <BaseField id="workflow_id" :name="t('components.nodes.tools.WorkflowInvoke.workflow_id')" required
            type="target" v-model:show="fieldsData.workflow_id.show">
            <a-input disabled v-model:value="fieldsData.workflow_id.value"
              :placeholder="fieldsData.workflow_id.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="fail_all" :name="t('components.nodes.tools.WorkflowInvoke.fail_all')" required type="target"
            v-model:show="fieldsData.fail_all.show">
            <a-checkbox v-model:checked="fieldsData.fail_all.value">
            </a-checkbox>
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="list_input" :name="t('components.nodes.tools.WorkflowInvoke.list_input')" required type="target"
            v-model:show="fieldsData.list_input.show">
            <a-checkbox v-model:checked="fieldsData.list_input.value">
            </a-checkbox>
          </BaseField>
        </a-col>

        <a-divider>
          {{ t('components.nodes.tools.WorkflowInvoke.workflow_fields') }}
        </a-divider>

        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
          <a-col :span="24"
            v-if="!['workflow_id', 'fail_all', 'list_input'].includes(field) && !fieldsData[field].is_output">
            <BaseField :id="field" :name="`${fieldsData[field].display_name}: ${fieldsData[field].type}`" required
              type="target" deletable @delete="removeField(field)" v-model:show="fieldsData[field].show">
              <a-select style="width: 100%;" v-model:value="fieldsData[field].value" :options="fieldsData[field].options"
                v-if="fieldsData[field].field_type == 'select'" />
              <a-textarea v-model:value="fieldsData[field].value" :autoSize="true" :showCount="true"
                :placeholder="fieldsData[field].placeholder" v-else-if="fieldsData[field].field_type == 'textarea'" />
              <a-input v-model:value="fieldsData[field].value" :placeholder="fieldsData[field].placeholder"
                v-else-if="fieldsData[field].field_type == 'input'" />
              <a-checkbox v-model:checked="fieldsData[field].value"
                v-else-if="fieldsData[field].field_type == 'checkbox'">
              </a-checkbox>
            </BaseField>
          </a-col>
        </template>

      </a-row>

    </template>
    <template #output>
      <a-row type="flex" style="width: 100%;">
        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="field">
          <a-col :span="24" v-if="fieldsData[field].is_output">
            <BaseField :id="field" :name="fieldsData[field].name" type="source" nameOnly>
            </BaseField>
          </a-col>
        </template>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>