<script setup>
import { ref } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'

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
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.fileProcessing.FileLoader"
    documentLink="https://vectorvein.com/help/docs/file-processing#h2-0" />
</template>