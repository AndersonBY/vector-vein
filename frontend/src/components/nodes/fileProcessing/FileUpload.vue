<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './FileUpload'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

const showEditField = ref(false)
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.fileProcessing.FileUpload"
    documentPath="/help/docs/file-processing#node-FileUpload">
    <template #main>
      <BaseField :name="fieldsData.files.display_name" required editable @edit="showEditField = true" type="target"
        v-model:data="fieldsData.files">
        <a-modal v-model:open="showEditField" :title="t('components.nodes.textProcessing.TextInOut.edit_name')"
          :footer="null">
          <a-input v-model:value="fieldsData.files.display_name" />
        </a-modal>
      </BaseField>
    </template>
  </BaseNode>
</template>