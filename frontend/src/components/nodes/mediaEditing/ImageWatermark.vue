<script setup>
import { ref, watch } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './ImageWatermark'

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

watch(() => fieldsData.value.image_or_text, () => {
  if (fieldsData.value.image_or_text.value == 'text') {
    fieldsData.value.watermark_image.show = false
    fieldsData.value.watermark_text_font.show = true
  } else {
    fieldsData.value.watermark_text.show = false
    fieldsData.value.watermark_image.show = true
    fieldsData.value.watermark_text_font.show = false
  }
}, { deep: true })
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData" :data="props.data"
    translatePrefix="components.nodes.mediaEditing.ImageWatermark"
    documentPath="/help/docs/media-editing#node-ImageWatermark" />
</template>