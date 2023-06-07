<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'Text',
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
    "task_name": "output.text",
    "has_inputs": false,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": true,
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
      "render_markdown": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": true,
        "password": false,
        "name": "render_markdown",
        "display_name": "render_markdown",
        "type": "bool",
        "clear_after_run": true,
        "list": false,
        "field_type": "checkbox"
      },
      "output_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "output_title",
        "display_name": "output_title",
        "type": "str",
        "clear_after_run": true,
        "list": false,
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
        "type": "str|dict",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
    }
  },
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
  <BaseNode :title="t('components.nodes.outputs.Text.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/outputs#h2-14" @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="text" :name="t('components.nodes.outputs.Text.text')" required type="target"
            v-model:show="fieldsData.text.show">
            <a-textarea v-model:value="fieldsData.text.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.text.placeholder" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_title" :name="t('components.nodes.outputs.Text.output_title')" required type="target"
            v-model:show="fieldsData.output_title.show">
            <a-input class="field-content" v-model:value="fieldsData.output_title.value"
              :placeholder="fieldsData.output_title.placeholder" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="render_markdown" :name="t('components.nodes.outputs.Text.render_markdown')" required
            type="target" v-model:show="fieldsData.render_markdown.show">
            <a-checkbox v-model:checked="fieldsData.render_markdown.value">
              {{ t('components.nodes.outputs.Text.render_markdown') }}
            </a-checkbox>
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.outputs.Text.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>