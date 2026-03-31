<script setup>
import { onBeforeMount, ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './Claude'
import { hydrateTemplateModelField, mergeTemplateIntoFields } from '@/utils/modelCatalog'

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
onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, createTemplateData())
  await hydrateTemplateModelField(fieldsData, 'Anthropic')
})
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.llms.Claude" documentPath="/help/docs/language-models#node-Claude" />
</template>
