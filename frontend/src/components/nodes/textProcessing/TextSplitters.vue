<script setup>
import { defineComponent, ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'TextSplitters',
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
    "task_name": "text_processing.text_splitters",
    "has_inputs": true,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "text",
        "display_name": "text",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "split_method": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "general",
        "password": false,
        "options": [
          {
            "value": "general",
            "label": "general"
          },
        ],
        "name": "split_method",
        "display_name": "split_method",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "chunk_length": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 500,
        "password": false,
        "name": "chunk_length",
        "display_name": "chunk_length",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
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
        "type": "list",
        "clear_after_run": true,
        "list": true,
        "field_type": "textarea"
      },
    }
  }
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.split_method.options = fieldsData.value.split_method.options.map(item => {
  item.label = t(`components.nodes.textProcessing.TextSplitters.split_method_${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.textProcessing.TextSplitters.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="text" :name="t('components.nodes.textProcessing.TextSplitters.text')" required type="target"
            v-model:show="fieldsData.text.show">
            <a-textarea class="field-content" v-model:value="fieldsData.text.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.text.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="split_method" :name="t('components.nodes.textProcessing.TextSplitters.split_method')" required
            type="target" v-model:show="fieldsData.split_method.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.split_method.value"
              :options="fieldsData.split_method.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="chunk_length" :name="t('components.nodes.textProcessing.TextSplitters.chunk_length')" required
            type="target" v-model:show="fieldsData.chunk_length.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.chunk_length.value"
              :placeholder="fieldsData.chunk_length.placeholder" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.textProcessing.TextSplitters.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>