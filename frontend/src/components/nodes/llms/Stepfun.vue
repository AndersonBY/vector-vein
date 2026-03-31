<script setup>
import { ref } from 'vue'
import BaseLLMComponent from './_BaseLLM.vue'
import { createTemplateData } from './Stepfun.js'

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
  <BaseLLMComponent :id="id" :data="props.data" :createTemplateData="createTemplateData" :debug="props.data.debug"
    v-model:templateData="fieldsData" llmName="Stepfun" :responseFormatAvailable="true"
    :functionCallAvailable="true" />
</template>
