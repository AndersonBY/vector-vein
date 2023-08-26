<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

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
    "task_name": "output.workflow_invoke_output",
    "has_inputs": false,
    "template": {
      "value": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "value",
        "display_name": "value",
        "type": "any",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "display_name": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "display_name",
        "display_name": "display_name",
        "type": "any",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
    }
  },
})


const { t } = useI18n()

const fieldsData = ref(props.data.template)
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.outputs.WorkflowInvokeOutput.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/outputs#h2-30">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="value" :name="t('components.nodes.outputs.WorkflowInvokeOutput.value')" required type="target"
            v-model:show="fieldsData.value.show">
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="display_name" :name="t('components.nodes.outputs.WorkflowInvokeOutput.display_name')" required
            type="target" v-model:show="fieldsData.display_name.show">
            <a-input class="field-content" v-model:value="fieldsData.display_name.value"
              :placeholder="fieldsData.display_name.placeholder" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>