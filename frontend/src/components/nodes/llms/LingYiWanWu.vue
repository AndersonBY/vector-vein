<script setup>
import { onBeforeMount, ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './LingYiWanWu'
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
  await hydrateTemplateModelField(fieldsData, 'Yi')
})
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.llms.LingYiWanWu" documentPath="/help/docs/language-models#node-LingYiWanWu" />
</template>
