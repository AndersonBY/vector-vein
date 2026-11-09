<script setup>
import IconButton from '@/components/IconButton.vue'
import { Delete, Refresh } from '@/icons'
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { knowledgeRequest } from '@/api/knowledgeBase'
import { knowledgeOptions } from '@/utils/knowledgeBase'

const props = defineProps({ disabled: Boolean, readonly: Boolean })
const ids = defineModel({ type: Array, default: () => [] })
const { t } = useI18n()
const bases = ref([]), loading = ref(false), failed = ref(false)
const unavailable = computed(() => failed.value || loading.value ? [] : ids.value.filter(id => !bases.value.some(base => base.id === id)))
let alive = true, generation = 0
const options = computed(() => knowledgeOptions(bases.value, ids.value, id => t('knowledgeBase.missing', { id }))
  .map(option => ({ ...option, disabled: option.disabled || (ids.value.length >= 20 && !ids.value.includes(option.value)) })))
const select = values => { if (!props.disabled && (values.length <= 20 || values.length < ids.value.length)) ids.value = values }
const removeUnavailable = () => {
  if (!props.disabled && !failed.value && !loading.value) ids.value = ids.value.filter(id => !unavailable.value.includes(id))
}
const load = async () => {
  const request = ++generation
  loading.value = true; failed.value = false
  try {
    const data = await knowledgeRequest('list')
    if (alive && request === generation) bases.value = data.bases || []
  } catch { if (alive && request === generation) failed.value = true }
  finally { if (alive && request === generation) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { alive = false; generation++ })
</script>

<template>
  <div class="knowledge-picker">
    <p>{{ t(readonly ? 'knowledgeBase.inherited' : 'knowledgeBase.mount_hint') }}</p>
    <a-alert v-if="failed" type="warning" show-icon :message="t('knowledgeBase.load_failed')">
      <template #action><IconButton size="small" :loading="loading" @click="load" :text="t('knowledgeBase.retry')"><template #icon><Refresh /></template></IconButton></template>
    </a-alert>
    <template v-if="readonly">
      <a-space v-if="ids.length" wrap><router-link v-for="id in ids" :key="id" :to="{ name: 'KnowledgeBaseDetail', params: { kbId: id } }">{{ options.find(option => option.value === id)?.label || id }}</router-link></a-space>
      <span v-else>{{ t('knowledgeBase.no_mounts') }}</span>
    </template>
    <template v-else>
      <a-select :value="ids" mode="multiple" :options="options" :loading="loading" :disabled="props.disabled || failed || loading" option-filter-prop="label" allow-clear :placeholder="t('knowledgeBase.select')" :aria-label="t('knowledgeBase.title')" @update:value="select" />
      <small>{{ t('knowledgeBase.mount_limit', { count: ids.length }) }}</small>
      <IconButton v-if="unavailable.length" danger :disabled="props.disabled" class="remove-unavailable" @click="removeUnavailable" :text="t('knowledgeBase.remove_unavailable', { count: unavailable.length })"><template #icon><Delete /></template></IconButton>
    </template>
    <router-link :to="{ name: 'DataSpaceMain', query: { tab: 'knowledge-bases' } }">{{ t('knowledgeBase.manage') }}</router-link>
  </div>
</template>

<style scoped>
.knowledge-picker { display: flex; flex-direction: column; gap: 10px; padding: 12px 0; min-width: 0; width: 100%; }
.knowledge-picker :deep(.ant-select) { width: 100%; min-width: 0; }
:deep(.remove-unavailable) { align-self: flex-start; height: auto; padding: 0; white-space: normal; text-align: left; }
small { color: var(--site-secondary-text-color); }
p { margin: 0; color: var(--site-secondary-text-color); font-size: 12px; }
.knowledge-picker > a { font-size: 12px; }
</style>
