<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlayOne } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { settingAPI } from '@/api/user'
import { retrievalTestEndpoints, useRetrievalModelTest } from '@/utils/retrievalModelTest'

const props = defineProps({
  kind: { type: String, required: true },
  backend: { type: String, required: true },
  modelKey: { type: String, default: '' },
  modelConfig: { type: Object, default: null },
  endpoints: { type: Array, default: () => [] },
  defaultEndpoint: { type: String, default: null },
})
const { t } = useI18n()
const open = ref(false), selected = ref('0')
const options = computed(() => retrievalTestEndpoints(props.modelConfig, props.defaultEndpoint, props.endpoints))
watch(options, value => { if (!value.some(item => item.value === selected.value)) selected.value = value[0]?.value }, { immediate: true })
const selectedEndpoint = computed(() => options.value.find(item => item.value === selected.value))
const { state, submit } = useRetrievalModelTest(() => ({
  active: open.value, kind: props.kind, backend: props.backend, modelKey: props.modelKey,
  modelConfig: props.modelConfig, endpoint: selectedEndpoint.value?.endpoint, binding: selectedEndpoint.value?.binding,
}), settingAPI, t)
</script>

<template>
  <IconButton :text="t('settings.retrieval_test')" @click="open = true"><template #icon><PlayOne /></template></IconButton>
  <a-modal v-model:open="open" :title="t('settings.retrieval_test_title', { model: modelKey })" :footer="null" destroy-on-close>
    <p>{{ t('settings.retrieval_test_tip') }}</p>
    <a-form layout="vertical">
      <a-form-item :label="t('settings.endpoint')">
        <a-select v-model:value="selected" :options="options.map(({ value, label }) => ({ value, label }))"
          :placeholder="t('settings.select_endpoint')" :aria-label="t('settings.endpoint')" />
      </a-form-item>
      <a-button :loading="state.loading" @click="submit"><template #icon><PlayOne /></template>{{ t('settings.retrieval_test') }}</a-button>
    </a-form>
    <div class="retrieval-test-result" aria-live="polite" :aria-busy="state.loading">
      <a-alert v-if="state.error" type="error" show-icon :message="state.error" />
      <a-alert v-else-if="state.result" type="success" show-icon :message="t('settings.retrieval_test_success')">
        <template #description>
          <p>{{ t('settings.retrieval_test_elapsed', { ms: state.result.elapsed_ms }) }}</p>
          <p v-if="kind === 'embedding'">{{ t('settings.retrieval_test_dimensions', { dimensions: state.result.dimensions, count: state.result.count }) }}</p>
          <ol v-else><li v-for="item in state.result.results" :key="item.index">{{ t('settings.retrieval_test_score', { index: item.index + 1, score: Number(item.score).toFixed(4) }) }}</li></ol>
        </template>
      </a-alert>
    </div>
  </a-modal>
</template>

<style scoped>
.retrieval-test-result { margin-top: 16px; }
.retrieval-test-result p { margin: 0; }
.retrieval-test-result ol { margin: 6px 0 0; padding-left: 20px; }
</style>
