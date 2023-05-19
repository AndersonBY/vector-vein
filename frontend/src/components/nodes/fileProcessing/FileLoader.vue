<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'FileLoader',
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
    "task_name": "file_processing.file_loader",
    "has_inputs": true,
    "template": {
      "files": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "files",
        "display_name": "files",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "file"
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
      },
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
  <BaseNode :title="t('components.nodes.fileProcessing.FileLoader.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="files" :name="t('components.nodes.fileProcessing.FileLoader.files')" required type="target"
            v-model:show="fieldsData.files.show">
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.fileProcessing.FileLoader.output')" type="source">
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>