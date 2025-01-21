<script setup>
import { ref } from 'vue'
import BaseLLMComponent from './_BaseLLM.vue'
import { createTemplateData } from './Gemini.js'
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
  <BaseLLMComponent :id="id" :createTemplateData="createTemplateData" :debug="props.data.debug"
    v-model:templateData="fieldsData" llmName="Gemini" :responseFormatAvailable="true" :functionCallAvailable="true" />
</template>