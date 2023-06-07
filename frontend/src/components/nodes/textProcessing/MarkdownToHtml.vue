<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'MarkdownToHtml',
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
    "task_name": "text_processing.markdown_to_html",
    "has_inputs": true,
    "template": {
      "markdown": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "markdown",
        "display_name": "markdown",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "html": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "html",
        "display_name": "html",
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
  <BaseNode :title="t('components.nodes.textProcessing.MarkdownToHtml.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/text-processing#h2-4" @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="markdown" :name="t('components.nodes.textProcessing.MarkdownToHtml.markdown')" required
            type="target" v-model:show="fieldsData.markdown.show">
            <a-textarea class="field-content" v-model:value="fieldsData.markdown.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.markdown.placeholder" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="html" :name="t('components.nodes.textProcessing.MarkdownToHtml.html')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>