<script setup>
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Help } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { addVekaiPreset } from './retrievalSettings'

defineProps({ kind: { type: String, required: true, validator: value => ['embedding', 'rerank'].includes(value) } })
const settings = defineModel({ required: true })
const { t } = useI18n()
const open = ref(false)
const status = ref('')
const forms = reactive({
  embedding: { address: 'http://127.0.0.1:8013', modelId: 'local-embedding' },
  rerank: { address: 'http://127.0.0.1:8012', modelId: 'local-reranker' },
})
const add = kind => {
  try {
    const added = addVekaiPreset(settings.value, kind, forms[kind])
    status.value = t(added ? (kind === 'embedding' ? 'settings.vekai_embedding_added' : 'settings.vekai_added') : 'settings.vekai_exists')
  } catch (error) {
    status.value = t(error.message === 'endpoint_conflict' ? 'settings.vekai_endpoint_conflict' : 'settings.vekai_invalid')
  }
}
</script>

<template>
  <span class="vekai-entry">
    <a-button @click="open = true">{{ t('settings.vekai_connect') }}</a-button>
    <IconButton :text="t('settings.vekai_help')" size="small"
      href="https://github.com/AndersonBY/vekai" target="_blank" rel="noopener noreferrer">
      <template #icon><Help /></template>
    </IconButton>
  </span>
  <a-modal v-model:open="open" :title="t('settings.vekai_connect')" :footer="null">
    <p>{{ t('settings.vekai_tip') }}</p>
    <a-form layout="vertical">
      <a-typography-title :level="5">{{ t(`settings.${kind}_models`) }}</a-typography-title>
      <a-form-item :label="t('settings.vekai_address')" :extra="kind === 'rerank' ? t('settings.vekai_rerank_path') : ''">
        <a-input v-model:value="forms[kind].address" />
      </a-form-item>
      <a-form-item :label="t('settings.model_id')">
        <a-input v-model:value="forms[kind].modelId" />
      </a-form-item>
      <a-button :disabled="!forms[kind].modelId.trim()" @click="add(kind)">{{ t('settings.vekai_add') }}</a-button>
    </a-form>
    <p role="status">{{ status }}</p>
  </a-modal>
</template>

<style scoped>
.vekai-entry { display: inline-flex; align-items: center; gap: 4px; }
</style>
