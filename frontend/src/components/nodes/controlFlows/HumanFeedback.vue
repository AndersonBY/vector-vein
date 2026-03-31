<script setup>
import { ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './HumanFeedback'

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
    title="Human Feedback"
    description="Expose a human review field in the run panel and forward the confirmed content."
    :debug="props.data.debug"
    documentPath="/help/docs/control-flows#node-HumanFeedback" />
</template>
