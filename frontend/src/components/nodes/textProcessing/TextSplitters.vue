<script setup>
import { defineComponent, ref } from 'vue'
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
          {
            "value": "delimiter",
            "label": "delimiter"
          },
          {
            "value": "markdown",
            "label": "markdown"
          }
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
      "chunk_overlap": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 30,
        "password": false,
        "name": "chunk_overlap",
        "display_name": "chunk_overlap",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "delimiter": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "\\n",
        "password": false,
        "name": "delimiter",
        "display_name": "delimiter",
        "type": "str",
        "clear_after_run": true,
        "list": true,
        "field_type": "input"
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
if (!fieldsData.value.delimiter) {
  fieldsData.value.delimiter = {
    "required": false,
    "placeholder": "",
    "show": false,
    "multiline": true,
    "value": "\\n",
    "password": false,
    "name": "delimiter",
    "display_name": "delimiter",
    "type": "str",
    "clear_after_run": true,
    "list": true,
    "field_type": "input"
  }
}
if (!fieldsData.value.chunk_overlap) {
  fieldsData.value.chunk_overlap = {
    "required": true,
    "placeholder": "",
    "show": false,
    "multiline": true,
    "value": 30,
    "password": false,
    "name": "chunk_overlap",
    "display_name": "chunk_overlap",
    "type": "str",
    "clear_after_run": true,
    "list": false,
    "field_type": "number"
  }
}

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.textProcessing.TextSplitters.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/text-processing#h2-16" @delete="deleteNode">
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

        <a-col :span="24" v-if="['general', 'markdown'].includes(fieldsData.split_method.value)">
          <BaseField id="chunk_length" :name="t('components.nodes.textProcessing.TextSplitters.chunk_length')" required
            type="target" v-model:show="fieldsData.chunk_length.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.chunk_length.value"
              :placeholder="fieldsData.chunk_length.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24" v-if="['general', 'markdown'].includes(fieldsData.split_method.value)">
          <BaseField id="chunk_overlap" :name="t('components.nodes.textProcessing.TextSplitters.chunk_overlap')" required
            type="target" v-model:show="fieldsData.chunk_overlap.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.chunk_overlap.value"
              :placeholder="fieldsData.chunk_overlap.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24" v-if="fieldsData.split_method.value == 'delimiter'">
          <BaseField id="delimiter" :name="t('components.nodes.textProcessing.TextSplitters.delimiter')" required
            type="target" v-model:show="fieldsData.delimiter.show">
            <a-input style="width: 100%;" class="field-content" v-model:value="fieldsData.delimiter.value"
              :placeholder="fieldsData.delimiter.placeholder" />
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