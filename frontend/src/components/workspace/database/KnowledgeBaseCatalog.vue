<script setup>
import { Refresh, Add, Setting, Delete } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { knowledgeRequest, knowledgeErrorKey } from '@/api/knowledgeBase'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import { validChunkSettings } from '@/utils/knowledgeBase'

const { t } = useI18n(), catalog = useModelCatalogStore()
const bases = ref([]), loading = ref(false), failed = ref(false), saving = ref(false), open = ref(false), search = ref('')
const editing = ref(null)
const form = reactive({ name: '', description: '', embedding_provider: '', embedding_model: '', chunk_size: 1000, chunk_overlap: 150 })
const models = computed(() => catalog.embeddingModels.filter(model => model.provider === form.embedding_provider))
const filtered = computed(() => bases.value.filter(base => `${base.name} ${base.description || ''}`.toLowerCase().includes(search.value.toLowerCase())))
let alive = true
const load = async () => {
  loading.value = true; failed.value = false
  try { const data = await knowledgeRequest('list'); if (alive) bases.value = data.bases || [] }
  catch { if (alive) failed.value = true }
  finally { if (alive) loading.value = false }
}
const edit = (base = null) => {
  editing.value = base
  Object.assign(form, { name: base?.name || '', description: base?.description || '', embedding_provider: '', embedding_model: '', chunk_size: 1000, chunk_overlap: 150 })
  open.value = true
  catalog.ensureLoaded()
}
const save = async () => {
  if (saving.value) return
  if (!form.name.trim() || (!editing.value && (!models.value.some(model => model.key === form.embedding_model) || !validChunkSettings(form.chunk_size, form.chunk_overlap)))) {
    message.warning(t('knowledgeBase.invalid_config')); return
  }
  saving.value = true
  try {
    const model = models.value.find(model => model.key === form.embedding_model)
    await knowledgeRequest(editing.value ? 'update' : 'create', editing.value
      ? { id: editing.value.id, name: form.name.trim(), description: form.description, expected_updated_at: editing.value.updated_at }
      : { ...form, name: form.name.trim(), ...(model?.dimensions ? { embedding_dimensions: model.dimensions } : {}) })
    open.value = false
    await load()
  } catch (error) {
    if (editing.value && (error.code === 'conflict' || error.status === 409 && error.code !== 'name_conflict')) {
      try { editing.value = await knowledgeRequest('get', { id: editing.value.id }) }
      catch { open.value = false }
      await load()
    }
    message.error(t(knowledgeErrorKey(error, 'save_failed')))
  }
  finally { saving.value = false }
}
const remove = base => Modal.confirm({
  title: t('knowledgeBase.delete_base'), content: t('knowledgeBase.delete_base_confirm', { name: base.name }),
  okText: t('knowledgeBase.delete'), cancelText: t('knowledgeBase.cancel'), okType: 'danger',
  async onOk() {
    if (!alive) return
    try { await knowledgeRequest('delete', { id: base.id, expected_updated_at: base.updated_at }); await load() }
    catch (error) {
      message.error(t(knowledgeErrorKey(error)))
      if (error.code === 'conflict' || error.status === 409 && error.code !== 'name_conflict') { await load(); return }
      return Promise.reject()
    }
  },
})
onMounted(load)
onBeforeUnmount(() => { alive = false })
</script>

<template>
  <section class="kb-catalog">
    <a-flex justify="space-between" gap="middle" wrap="wrap">
      <a-input-search v-model:value="search" :placeholder="t('knowledgeBase.find_base')" :aria-label="t('knowledgeBase.find_base')" style="max-width: 320px" />
      <a-space><IconButton :text="t('knowledgeBase.refresh')" :loading="loading" @click="load"><template #icon><Refresh /></template></IconButton><IconButton :text="t('knowledgeBase.create')" type="text" @click="edit()"><template #icon><Add /></template></IconButton></a-space>
    </a-flex>
    <a-alert v-if="failed" type="warning" show-icon :message="t('knowledgeBase.load_failed')"><template #action><IconButton :text="t('knowledgeBase.retry')" @click="load"><template #icon><Refresh /></template></IconButton></template></a-alert>
    <a-table :loading="loading" :data-source="filtered" row-key="id" :pagination="{ pageSize: 10, hideOnSinglePage: true }">
      <a-table-column key="name" :title="t('knowledgeBase.name')"><template #default="{ record }"><router-link :to="{ name: 'KnowledgeBaseDetail', params: { kbId: record.id } }"><strong>{{ record.name }}</strong></router-link><p class="description">{{ record.description }}</p></template></a-table-column>
      <a-table-column key="model" :title="t('knowledgeBase.model')"><template #default="{ record }">{{ record.embedding_provider }} / {{ record.embedding_model }}</template></a-table-column>
      <a-table-column key="count" data-index="document_count" :title="t('knowledgeBase.documents')" />
      <a-table-column key="actions" :title="t('knowledgeBase.actions')"><template #default="{ record }"><a-space><IconButton :text="t('knowledgeBase.configure')" size="small" @click="edit(record)"><template #icon><Setting /></template></IconButton><IconButton :text="t('knowledgeBase.delete')" size="small" danger @click="remove(record)"><template #icon><Delete /></template></IconButton></a-space></template></a-table-column>
    </a-table>
    <a-modal ok-type="default" v-model:open="open" :title="t(editing ? 'knowledgeBase.configure' : 'knowledgeBase.create')" :confirm-loading="saving" :ok-text="t('knowledgeBase.save')" :cancel-text="t('knowledgeBase.cancel')" @ok="save">
      <a-form layout="vertical" :disabled="saving">
        <a-form-item :label="t('knowledgeBase.name')" required><a-input v-model:value="form.name" :maxlength="160" /></a-form-item>
        <a-form-item :label="t('knowledgeBase.description')"><a-textarea v-model:value="form.description" :maxlength="2000" /></a-form-item>
        <template v-if="!editing">
          <a-alert v-if="!catalog.embeddingModels.length" type="info" show-icon :message="t('knowledgeBase.configure_embeddings')"><template #action><router-link :to="{ name: 'settings', query: { section: 'embedding_models' } }">{{ t('settings.embedding_models') }}</router-link></template></a-alert>
          <a-form-item :label="t('knowledgeBase.provider')" required><a-select v-model:value="form.embedding_provider" :options="catalog.embeddingProviders.map(item => ({ value: item.key, label: item.label }))" @change="form.embedding_model = ''" /></a-form-item>
          <a-form-item :label="t('knowledgeBase.model')" required><a-select v-model:value="form.embedding_model" :options="models.map(item => ({ value: item.key, label: item.id }))" /></a-form-item>
          <a-form-item :label="t('knowledgeBase.chunk_size')"><a-input-number v-model:value="form.chunk_size" :min="64" :max="16000" :precision="0" /></a-form-item>
          <a-form-item :label="t('knowledgeBase.chunk_overlap')"><a-input-number v-model:value="form.chunk_overlap" :min="0" :max="Math.max(0, form.chunk_size - 1)" :precision="0" /></a-form-item>
        </template>
        <a-alert v-else type="info" :message="t('knowledgeBase.model_fixed')" />
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.kb-catalog { display: flex; flex-direction: column; gap: 20px; }
.description { color: var(--site-secondary-text-color); margin: 4px 0 0; max-width: 36em; }
</style>
