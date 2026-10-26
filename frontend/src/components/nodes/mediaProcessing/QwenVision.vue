<script setup>
import { onBeforeMount, ref, watch } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { hydrateTemplateModelField } from '@/utils/modelCatalog'
import { createTemplateData } from './QwenVision'

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

onBeforeMount(async () => {
  await hydrateTemplateModelField(fieldsData, 'Qwen', 'llm_model', true)
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
  <BaseNode :nodeId="id" :debug="props.data.debug" :data="props.data" :fieldsData="fieldsData"
    translatePrefix="components.nodes.mediaProcessing.QwenVision"
    documentPath="/help/docs/media-processing#node-QwenVision" />
</template>