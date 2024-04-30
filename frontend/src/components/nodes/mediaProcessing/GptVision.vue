<script setup>
import { ref, watch } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './GptVision'

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

watch(() => fieldsData.value.images_or_urls, () => {
  if (fieldsData.value.images_or_urls.value == 'images') {
    fieldsData.value.urls.show = false
  } else {
    fieldsData.value.images.show = false
  }
}, { deep: true })
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.mediaProcessing.GptVision"
    documentLink="https://vectorvein.com/help/docs/media-processing#h2-4" />
</template>