<script setup>
import EmbeddingBackendSettings from "@/components/settings/EmbeddingBackendSettings.vue"

const props = defineProps({
  endpoints: {
    type: Array,
    required: true
  },
})

const backends = defineModel()

const EMBEDDING_BACKEND_TABS = [
  { key: 'openai', label: 'OpenAI' },
  { key: 'cohere', label: 'Cohere' },
  { key: 'jina', label: 'Jina' },
  { key: 'voyage', label: 'Voyage' },
  { key: 'siliconflow', label: 'Siliconflow' },
  { key: 'local', label: 'Local' },
  { key: 'custom', label: 'Custom' },
]
</script>

<template>
  <a-tabs tab-position="left">
    <a-tab-pane v-for="backend in EMBEDDING_BACKEND_TABS" :key="backend.key" :tab="backend.label">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <EmbeddingBackendSettings v-model="backends[backend.key]" :endpoints="props.endpoints" />
      </a-form>
    </a-tab-pane>
  </a-tabs>
</template>
