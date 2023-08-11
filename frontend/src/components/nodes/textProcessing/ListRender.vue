<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ListField from '@/components/nodes//ListField.vue'

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
      "separator": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "\\n",
        "password": false,
        "name": "separator",
        "display_name": "separator",
        "type": "str",
        "clear_after_run": true,
        "list": true,
        "field_type": "input"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "text",
        "password": false,
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          {
            "value": "list",
            "label": "List"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
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
        "field_type": "textarea"
      }
    }
  }
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
if (!fieldsData.value.output_type) {
  fieldsData.value.output_type = {
    "required": true,
    "placeholder": "",
    "show": false,
    "multiline": false,
    "value": "text",
    "password": false,
    "options": [
      {
        "value": "text",
        "label": "Text"
      },
      {
        "value": "list",
        "label": "List"
      },
    ],
    "name": "output_type",
    "display_name": "output_type",
    "type": "str",
    "clear_after_run": true,
    "list": false,
    "field_type": "select"
  }
}
if (!fieldsData.value.separator) {
  fieldsData.value.separator = {
    "required": false,
    "placeholder": "",
    "show": false,
    "multiline": true,
    "value": "\\n",
    "password": false,
    "name": "separator",
    "display_name": "separator",
    "type": "str",
    "clear_after_run": true,
    "list": true,
    "field_type": "input"
  }
}
fieldsData.value.output_type.options = fieldsData.value.output_type.options.map(item => {
  item.label = t(`components.nodes.textProcessing.ListRender.output_type_${item.value}`)
  return item
})
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.textProcessing.ListRender.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/text-processing#h2-0">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <ListField id="list" :name="t('components.nodes.textProcessing.ListRender.list')" required type="target"
            v-model:value="fieldsData.list.value" v-model:show="fieldsData.list.show">
          </ListField>
        </a-col>

        <a-col :span="24" v-if="fieldsData.output_type.value == 'text'">
          <BaseField id="separator" :name="t('components.nodes.textProcessing.ListRender.separator')" required
            type="target" v-model:show="fieldsData.separator.show">
            <a-input style="width: 100%;" class="field-content" v-model:value="fieldsData.separator.value"
              :placeholder="fieldsData.separator.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.textProcessing.ListRender.output_type')" required
            type="target" v-model:show="fieldsData.output_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.output_type.value"
              :options="fieldsData.output_type.options" />
          </BaseField>
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