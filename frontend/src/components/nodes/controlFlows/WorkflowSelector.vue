<script setup>
import { onBeforeMount, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import WorkflowSelect from '@/components/workspace/WorkflowSelect.vue'
import { createTemplateData } from './WorkflowSelector'
import { hydrateFlattenedModelField, mergeTemplateIntoFields } from '@/utils/modelCatalog'

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

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()

onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, templateData)
  await hydrateFlattenedModelField(fieldsData, 'llm_model')
})

const workflowSelectModal = reactive({
  open: false,
  data: {},
})

const addWorkflowCandidate = () => {
  const selected = workflowSelectModal.data
  if (!selected?.wid) {
    message.warning('Please choose a workflow first')
    return
  }
  const exists = (fieldsData.value.workflow_ids.value || []).some((item) => item.id === selected.wid)
  if (!exists) {
    fieldsData.value.workflow_ids.value = [
      ...(fieldsData.value.workflow_ids.value || []),
      { id: selected.wid, title: selected.title },
    ]
  }
  workflowSelectModal.open = false
  workflowSelectModal.data = {}
}

const removeWorkflowCandidate = (workflowId) => {
  fieldsData.value.workflow_ids.value = (fieldsData.value.workflow_ids.value || []).filter((item) => item.id !== workflowId)
}
</script>

<template>
  <BaseNode :nodeId="id" :data="props.data" :fieldsData="fieldsData"
    title="Workflow Selector"
    description="Select one workflow from multiple candidates, then invoke it."
    :debug="props.data.debug"
    documentPath="/help/docs/control-flows#node-WorkflowSelector">
    <template #main>
      <a-flex vertical gap="small">
        <BaseField name="Request" type="target" v-model:data="fieldsData.input">
          <a-textarea v-model:value="fieldsData.input.value" class="nodrag" :auto-size="{ minRows: 2, maxRows: 10 }" />
        </BaseField>

        <BaseField name="Selection Prompt" required type="target" v-model:data="fieldsData.template">
          <a-textarea v-model:value="fieldsData.template.value" class="nodrag" :auto-size="{ minRows: 3, maxRows: 12 }" />
        </BaseField>

        <BaseField name="Selection Model" type="target" v-model:data="fieldsData.llm_model">
          <a-select v-model:value="fieldsData.llm_model.value" :options="fieldsData.llm_model.options" />
        </BaseField>

        <a-card size="small" title="Workflow Candidates">
          <a-flex vertical gap="small">
            <a-empty v-if="(fieldsData.workflow_ids.value || []).length === 0" description="No candidates selected" />
            <a-flex v-for="workflow in fieldsData.workflow_ids.value || []" :key="workflow.id" justify="space-between" align="center" gap="small">
              <a-typography-text ellipsis style="max-width: 180px;">
                {{ workflow.title }}
              </a-typography-text>
              <a-button danger type="text" size="small" @click="removeWorkflowCandidate(workflow.id)">
                Remove
              </a-button>
            </a-flex>
            <a-button type="dashed" block @click="workflowSelectModal.open = true">
              Add Workflow
            </a-button>
          </a-flex>
        </a-card>

        <a-modal v-model:open="workflowSelectModal.open" :footer="null" title="Select Workflow" width="80vw">
          <WorkflowSelect v-model="workflowSelectModal.data" @selected="addWorkflowCandidate" />
        </a-modal>
      </a-flex>
    </template>
  </BaseNode>
</template>
