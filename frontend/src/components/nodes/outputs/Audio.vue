<script setup>
import { ref, computed, watch } from 'vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { agentVoiceOptions } from '@/utils/common'
import { createTemplateData } from './Audio'

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

fieldsData.value.tts_voice.options = computed(() => agentVoiceOptions.value.find((provider) => provider.value == fieldsData.value.tts_provider.value)?.children)

watch(() => fieldsData.value.tts_provider.value, (value) => {
  fieldsData.value.tts_voice.value = fieldsData.value.tts_voice.options[0].value
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" :data="props.data" translatePrefix="components.nodes.outputs.Audio"
    :debug="props.data.debug" documentPath="/help/docs/outputs#node-Audio" />
</template>