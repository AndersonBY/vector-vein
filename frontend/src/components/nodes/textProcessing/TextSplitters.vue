<script setup>
import { ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './TextSplitters'

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
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.textProcessing.TextSplitters"
    documentLink="https://vectorvein.com/help/docs/text-processing#h2-16" />
</template>