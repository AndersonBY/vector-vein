<script setup>
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './LocalLlm'

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

const userSettings = useUserSettingsStore()
const { setting } = storeToRefs(userSettings)

fieldsData.value.model_family.options = setting.value.data.local_llms.map((llm) => ({
  value: llm.model_family,
  text: llm.model_family,
}))

fieldsData.value.llm_model.options = computed(() => {
  const modelFamily = fieldsData.value.model_family.value
  const llm = setting.value.data.local_llms.find((llm) => llm.model_family === modelFamily)
  return llm ? llm.models.map((model) => ({
    value: model.model_id,
    text: model.model_label,
  })) : []
})
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.llms.LocalLlm" />
</template>