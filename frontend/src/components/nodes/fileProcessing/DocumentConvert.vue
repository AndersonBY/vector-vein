<script setup>
import { ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './DocumentConvert'

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

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})
</script>

<template>
  <BaseNode :nodeId="id" :data="props.data" :fieldsData="fieldsData"
    title="Document Convert"
    description="Extract document content locally and export it into a chosen file format."
    :debug="props.data.debug"
    documentPath="/help/docs/file-processing#node-DocumentConvert">
    <template #main>
      <BaseField name="Files" required type="target" v-model:data="fieldsData.files" />
      <BaseField name="Output Format" required type="target" v-model:data="fieldsData.output_format" />
    </template>
  </BaseNode>
</template>
