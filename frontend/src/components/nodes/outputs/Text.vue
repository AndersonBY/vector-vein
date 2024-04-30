<script setup>
import { ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './Text'

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
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.outputs.Text"
    :debug="props.data.debug" documentLink="https://vectorvein.com/help/docs/outputs#h2-14" />
</template>