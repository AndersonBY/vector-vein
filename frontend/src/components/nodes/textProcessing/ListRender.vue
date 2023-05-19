<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ListField from '@/components/nodes//ListField.vue'

defineComponent({
  name: 'ListRender',
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
    "task_name": "text_processing.list_render",
    "has_inputs": true,
    "template": {
      "list": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "list",
        "display_name": "list",
        "type": "str",
        "clear_after_run": true,
        "list": true,
        "field_type": "list"
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
        "field_type": "textarea"
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
  <BaseNode :title="t('components.nodes.textProcessing.ListRender.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <ListField id="list" :name="t('components.nodes.textProcessing.ListRender.list')" required type="target"
            v-model:value="fieldsData.list.value" v-model:show="fieldsData.list.show">
          </ListField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.textProcessing.ListRender.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>