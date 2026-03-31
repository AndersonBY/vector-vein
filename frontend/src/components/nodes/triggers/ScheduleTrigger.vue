<script setup>
import { ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import CronInput from '@/components/nodes/CronInput.vue'
import { createTemplateData } from './ScheduleTrigger'

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
})
</script>

<template>
  <BaseNode :nodeId="id" :data="props.data" :fieldsData="fieldsData"
    title="Schedule Trigger"
    description="Run this workflow on a local cron schedule."
    :debug="props.data.debug"
    documentPath="/help/docs/triggers#node-ScheduleTrigger">
    <template #main>
      <BaseField name="Cron" required type="target" v-model:data="fieldsData.schedule">
        <CronInput v-model="fieldsData.schedule.value" />
      </BaseField>
    </template>
  </BaseNode>
</template>
