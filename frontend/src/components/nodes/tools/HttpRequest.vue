<script setup>
import { ref, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './HttpRequest'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, required: true },
})
const { t } = useI18n()
const fieldsData = ref(props.data.template)
Object.entries(createTemplateData().template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) fieldsData.value[key].is_output = true
})
watchEffect(() => {
  fieldsData.value.body_type.options = ['none', 'json', 'text', 'form'].map(value => ({
    value, label: t(`components.nodes.tools.HttpRequest.body_type_${value}`),
  }))
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" :data="props.data" :debug="props.data.debug"
    translatePrefix="components.nodes.tools.HttpRequest" documentPath="/help/docs/tools#node-HttpRequest" />
</template>
