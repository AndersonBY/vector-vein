<script setup>
import { defineComponent, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'RandomChoice',
})

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  events: {
    required: false,
  },
  templateData: {
    "description": "description",
    "task_name": "control_flows.random_choice",
    "has_inputs": true,
    "template": {
      "input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "input",
        "display_name": "input",
        "type": "list",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      }
    }
  }
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.controlFlows.RandomChoice.title')" :description="props.data.description" documentLink="https://vectorvein.com/help/docs/control-flows#h2-10"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="input" :name="t('components.nodes.controlFlows.RandomChoice.input')" required type="target"
            v-model:show="fieldsData.input.show" nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.controlFlows.RandomChoice.output')" type="source">
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>