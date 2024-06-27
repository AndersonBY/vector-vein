<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './FileLoader'

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
    translatePrefix="components.nodes.fileProcessing.FileLoader" documentPath="/help/docs/file-processing#h2-0">
    <template #main>
      <BaseField :name="fieldsData.files.display_name" required editable @edit="showEditField = true" type="target"
        v-model:data="fieldsData.files">
        <a-modal v-model:open="showEditField" :title="t('components.nodes.textProcessing.TextInOut.edit_name')"
          :footer="null">
          <a-input v-model:value="fieldsData.files.display_name" />
        </a-modal>
      </BaseField>

      <BaseField :name="t('components.nodes.fileProcessing.FileLoader.remove_image')"
        :required="fieldsData.remove_image.required" type="target" v-model:data="fieldsData.remove_image" nameOnly />

      <BaseField :name="t('components.nodes.fileProcessing.FileLoader.remove_url_and_email')"
        :required="fieldsData.remove_url_and_email.required" type="target"
        v-model:data="fieldsData.remove_url_and_email" nameOnly />
    </template>
  </BaseNode>
</template>