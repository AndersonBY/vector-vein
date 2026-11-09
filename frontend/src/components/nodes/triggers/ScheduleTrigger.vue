<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ScheduleEditor from '@/components/scheduling/ScheduleEditor.vue'
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
const { t } = useI18n()
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
})
</script>

<template>
  <BaseNode :nodeId="id" :data="props.data" :fieldsData="fieldsData"
    :title="t('workspace.workflowSpace.schedule_trigger_title')"
    :description="t('workspace.workflowSpace.schedule_trigger_help')"
    :debug="props.data.debug"
    documentPath="/help/docs/triggers#node-ScheduleTrigger">
    <template #main>
      <BaseField :name="t('workspace.workflowSpace.schedule_pattern')" required type="target" v-model:data="fieldsData.schedule">
        <ScheduleEditor v-model="fieldsData.schedule.value" v-model:recurrence="fieldsData.recurrence.value" v-model:timezone="fieldsData.timezone.value" />
      </BaseField>
    </template>
  </BaseNode>
</template>
