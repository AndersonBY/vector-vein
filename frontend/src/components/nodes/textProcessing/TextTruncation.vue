<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'TextTruncation',
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
    "task_name": "text_processing.text_truncation",
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
      "truncate_method": {
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
          {
            "value": "markdown",
            "label": "markdown"
          }
        ],
        "name": "truncate_method",
        "display_name": "truncate_method",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "truncate_length": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 2000,
        "password": false,
        "name": "truncate_length",
        "display_name": "truncate_length",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "floating_range": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 100,
        "password": false,
        "name": "floating_range",
        "display_name": "floating_range",
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
fieldsData.value.truncate_method.options = fieldsData.value.truncate_method.options.map(item => {
  item.label = t(`components.nodes.textProcessing.TextTruncation.truncate_method_${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.textProcessing.TextTruncation.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/text-processing#h2-20" @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="text" :name="t('components.nodes.textProcessing.TextTruncation.text')" required type="target"
            v-model:show="fieldsData.text.show">
            <a-textarea class="field-content" v-model:value="fieldsData.text.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.text.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="truncate_length" :name="t('components.nodes.textProcessing.TextTruncation.truncate_length')"
            required type="target" v-model:show="fieldsData.truncate_length.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.truncate_length.value"
              :placeholder="fieldsData.truncate_length.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="floating_range" :name="t('components.nodes.textProcessing.TextTruncation.floating_range')"
            required type="target" v-model:show="fieldsData.floating_range.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.floating_range.value"
              :placeholder="fieldsData.floating_range.placeholder" />
          </BaseField>
        </a-col>

      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.textProcessing.TextTruncation.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>