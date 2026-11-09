<script setup>
import { watch } from 'vue'
import EmbeddingBackendSettings from "@/components/settings/EmbeddingBackendSettings.vue"

const props = defineProps({
  kind: { type: String, default: 'embedding' },
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

watch(backends, value => {
  const normalized = { ...(value || {}) }
  let changed = !value
  for (const { key } of EMBEDDING_BACKEND_TABS) {
    if (!normalized[key] || typeof normalized[key] !== 'object' || Array.isArray(normalized[key])) {
      normalized[key] = { models: {}, default_endpoint: null }
      changed = true
    }
  }
  if (changed) backends.value = normalized
}, { immediate: true })
</script>

<template>
  <a-tabs tab-position="left">
    <a-tab-pane v-for="backend in EMBEDDING_BACKEND_TABS" :key="backend.key" :tab="backend.label">
      <EmbeddingBackendSettings v-if="backends?.[backend.key]" v-model="backends[backend.key]" :endpoints="props.endpoints" :kind="kind" :backend="backend.key" />
    </a-tab-pane>
  </a-tabs>
</template>
