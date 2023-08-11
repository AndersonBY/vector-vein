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
    "task_name": "output.document",
    "has_inputs": true,
    "template": {
      "file_name": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "file_name",
        "display_name": "file_name",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "content": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "content",
        "display_name": "content",
        "type": "str|list",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "export_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": ".docx",
        "password": false,
        "options": [
          {
            "value": ".docx",
            "label": ".docx"
          },
          {
            "value": ".xlsx",
            "label": ".xlsx"
          },
          {
            "value": ".txt",
            "label": ".txt"
          },
          {
            "value": ".md",
            "label": ".md"
          },
          {
            "value": ".json",
            "label": ".json"
          },
          {
            "value": ".csv",
            "label": ".csv"
          },
          {
            "value": ".html",
            "label": ".html"
          },
        ],
        "name": "export_type",
        "display_name": "export_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "show_local_file": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": true,
        "password": false,
        "name": "show_local_file",
        "display_name": "show_local_file",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
      },
      "output": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "local_file"
      },
    }
  },
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.outputs.Document.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/outputs#h2-4">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="file_name" :name="t('components.nodes.outputs.Document.file_name')" required type="target"
            v-model:show="fieldsData.file_name.show">
            <a-input class="field-content" v-model:value="fieldsData.file_name.value"
              :placeholder="fieldsData.file_name.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="export_type" :name="t('components.nodes.outputs.Document.export_type')" required type="target"
            v-model:show="fieldsData.export_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.export_type.value"
              :options="fieldsData.export_type.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="content" :name="t('components.nodes.outputs.Document.content')" required type="target"
            v-model:show="fieldsData.content.show">
            <a-textarea v-model:value="fieldsData.content.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.content.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="show_local_file" :name="t('components.nodes.outputs.Document.show_local_file')" required
            type="target" v-model:show="fieldsData.show_local_file.show">
            <a-checkbox v-model:checked="fieldsData.show_local_file.value">
              {{ t('components.nodes.outputs.Document.show_local_file') }}
            </a-checkbox>
          </BaseField>
        </a-col>

      </a-row>
    </template>

    <template #output>
      <BaseField id="output" :name="t('components.nodes.outputs.Document.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>