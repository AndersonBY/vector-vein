<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './Conditional'

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
const originalOperatorOptions = JSON.parse(JSON.stringify(templateData.template.operator.options))
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})
originalOperatorOptions.forEach(item => {
  item.label = t(`components.nodes.controlFlows.Conditional.operator_${item.value}`)
})
fieldsData.value.operator.options = originalOperatorOptions.filter(item => item.field_type.includes('string'))

watch(() => fieldsData.value.field_type.value, () => {
  if (fieldsData.value.field_type.value == 'string') {
    fieldsData.value.left_field.field_type = 'input'
    fieldsData.value.right_field.field_type = 'input'
    fieldsData.value.operator.options = originalOperatorOptions.filter(item => item.field_type.includes('string'))
  } else if (fieldsData.value.field_type.value == 'number') {
    fieldsData.value.left_field.field_type = 'number'
    fieldsData.value.right_field.field_type = 'number'
    fieldsData.value.operator.options = originalOperatorOptions.filter(item => item.field_type.includes('number'))
  }
})
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.controlFlows.Conditional"
    documentLink="https://vectorvein.com/help/docs/control-flows#h2-0" />
</template>