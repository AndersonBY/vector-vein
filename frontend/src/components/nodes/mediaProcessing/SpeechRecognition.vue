<script setup>
import { ref, watch } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './SpeechRecognition'

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

watch(() => fieldsData.value.files_or_urls, () => {
  if (fieldsData.value.files_or_urls.value == 'files') {
    fieldsData.value.urls.show = false
  } else {
    fieldsData.value.files.show = false
  }
}, { deep: true })
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.mediaProcessing.SpeechRecognition"
    documentPath="/help/docs/media-processing#node-SpeechRecognition" />
</template>