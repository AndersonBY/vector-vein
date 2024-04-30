<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './ButtonTrigger'

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

const { t } = useI18n()

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})
fieldsData.value.button_text.value = fieldsData.value.button_text.value.length > 0 ? fieldsData.value.button_text.value : t('components.nodes.triggers.ButtonTrigger.run')
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.triggers.ButtonTrigger"
    documentLink="https://vectorvein.com/help/docs/triggers#h2-0" />
</template>