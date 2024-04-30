<script setup>
import { ref, watch } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './StableDiffusion'

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

watch(() => fieldsData.value.size.value, (value) => {
  const [width, height] = value.split(' x ')
  fieldsData.value.width.value = parseInt(width)
  fieldsData.value.height.value = parseInt(height)
})
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.imageGeneration.StableDiffusion"
    documentLink="https://vectorvein.com/help/docs/image-generation#h2-0" />
</template>