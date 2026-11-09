<script setup>
import { Refresh, Redo, Upload, FolderOpen, Add, More, OpenExternal } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { knowledgeRequest, knowledgeErrorKey } from '@/api/knowledgeBase'
import { folderOptions, indexingErrorKey } from '@/utils/knowledgeBase'

const { t } = useI18n(), route = useRoute()
const kbId = computed(() => String(route.params.kbId || ''))
const base = ref(null), folders = ref([]), items = ref([]), breadcrumbs = ref([])
const parentId = ref(null), query = ref(''), page = ref(1), total = ref(0)
const loading = ref(false), failed = ref(false), busy = ref(false), loadCode = ref('')
const skipped = ref([]), picking = ref(false), operationConflict = ref(false)
const preview = ref(null), previewLoading = ref(false), previewFailed = ref(false), previewTab = ref('text')
const rightTab = ref('preview'), searchQuery = ref(''), searchMode = ref('hybrid'), searchLoading = ref(false)
const results = ref([]), searched = ref(false), searchFailed = ref(false), searchErrorCode = ref(''), warnings = ref([])
const dialog = ref(''), target = ref(null), name = ref(''), destination = ref('__root__')
let alive = true, generation = 0, previewGeneration = 0, searchGeneration = 0, mutationGeneration = 0, timer, confirmModal
const tree = computed(() => [{ id: '__root__', name: t('knowledgeBase.root'), children: folders.value }])
const moveOptions = computed(() => [{ value: '__root__', label: t('knowledgeBase.root') }, ...folderOptions(folders.value, target.value?.kind === 'folder' ? target.value.id : null)])
const columns = computed(() => ['name', 'status', 'byte_size', 'actions'].map(key => ({ key, title: t(`knowledgeBase.${key}`) })))
const statusColor = status => ({ queued: 'processing', indexing: 'processing', ready: 'success', failed: 'error' }[status] || 'default')
const canConfigureEmbedding = code => ['embedding_unavailable', 'embedding_failed', 'invalid_embedding', 'invalid_model', 'invalid_dimensions', 'dimension_mismatch', 'indexing_failed'].includes(code)
const load = async (silent = false) => {
  const request = ++generation, id = kbId.value, folder = parentId.value
  clearTimeout(timer)
  if (!alive || !id) { loading.value = false; return }
  if (!silent) loading.value = true
  failed.value = false
  try {
    const [record, hierarchy, listing] = await Promise.all([
      knowledgeRequest('get', { id }),
      knowledgeRequest('tree', { kb_id: id }),
      knowledgeRequest('items', { kb_id: id, parent_id: folder, search: query.value, offset: (page.value - 1) * 50, limit: 50 }),
    ])
    if (!alive || request !== generation) return
    base.value = record; folders.value = hierarchy.folders || []; items.value = listing.items || []
    loadCode.value = ''
    total.value = listing.total || 0; breadcrumbs.value = listing.breadcrumbs || []
    const selected = listing.items?.find(item => item.id === preview.value?.item?.id)
    if (selected && !previewLoading.value) {
      if (['ready', 'failed'].includes(selected.status) && (preview.value.item.status !== selected.status || (!preview.value.text && selected.updated_at !== preview.value.item.updated_at))) openPreview(selected, true)
      else preview.value.item = selected
    }
    if (!selected && preview.value && !previewLoading.value && ['queued', 'indexing'].includes(preview.value.item.status)) openPreview(preview.value.item, true)
    // Poll the KB even when jobs are in another folder or page.
  } catch (error) {
    if (alive && request === generation) { failed.value = true; loadCode.value = error.code || '' }
  } finally {
    if (alive && request === generation) {
      loading.value = false
      if (loadCode.value !== 'not_found') timer = setTimeout(() => load(true), 5000)
    }
  }
}
const navigate = id => {
  searchGeneration++; results.value = []; searched.value = false; searchLoading.value = false; searchFailed.value = false; searchErrorCode.value = ''; warnings.value = []
  parentId.value = id === '__root__' ? null : id
  query.value = ''; page.value = 1; load()
}
const openPreview = async (item, background = false) => {
  if (item.kind === 'folder') { navigate(item.id); return }
  const request = ++previewGeneration, id = kbId.value
  if (!background) { preview.value = { item, text: '' }; rightTab.value = 'preview'; previewTab.value = 'text' }
  previewLoading.value = true; previewFailed.value = false
  try {
    const data = await knowledgeRequest('preview', { kb_id: id, id: item.id })
    if (alive && request === previewGeneration) preview.value = data
  } catch { if (alive && request === previewGeneration) previewFailed.value = true }
  finally { if (alive && request === previewGeneration) previewLoading.value = false }
}
const mutate = async (action, payload = {}) => {
  if (busy.value) return false
  const id = kbId.value, operation = ++mutationGeneration
  busy.value = true; operationConflict.value = false
  try {
    const data = await knowledgeRequest(action, { kb_id: id, ...payload })
    if (!alive || id !== kbId.value || operation !== mutationGeneration) return false
    if (action === 'import_files' || action === 'import_directory') skipped.value = data?.skipped || []
    if (data?.skipped?.length) message.warning(t('knowledgeBase.import_skipped', { count: data.skipped.length }))
    else message.success(t(action === 'reindex' ? 'knowledgeBase.index_queued' : 'knowledgeBase.saved'))
    await load()
    return true
  } catch (error) {
    if (!alive || id !== kbId.value || operation !== mutationGeneration) return false
    if (error.code === 'conflict' || error.code === 'changed' || (error.status === 409 && error.code !== 'name_conflict')) {
      operationConflict.value = true
      await load()
      if (['rename', 'move'].includes(action) && target.value?.id === payload.id) {
        const fresh = !failed.value && items.value.find(item => item.id === payload.id)
        if (fresh) target.value = fresh
        else { dialog.value = ''; target.value = null }
      }
    }
    message.error(t(knowledgeErrorKey(error)))
    return false
  } finally { if (alive && operation === mutationGeneration) busy.value = false }
}
const importNative = async directory => {
  if (busy.value || picking.value) return
  const id = kbId.value, folder = parentId.value
  picking.value = true
  try {
    const bridge = window.pywebview?.api
    if (typeof bridge?.[directory ? 'open_folder_dialog' : 'open_file_dialog'] !== 'function') {
      message.warning(t('knowledgeBase.native_only')); return
    }
    const selection = directory ? await bridge.open_folder_dialog() : await bridge.open_file_dialog(true)
    if (!alive || id !== kbId.value || folder !== parentId.value) return
    if (!selection || (Array.isArray(selection) && !selection.length)) return
    await mutate(directory ? 'import_directory' : 'import_files', {
      parent_id: parentId.value,
      ...(directory ? { path: Array.isArray(selection) ? selection[0] : selection } : { paths: Array.isArray(selection) ? selection : [selection] }),
    })
  } catch { message.error(t('knowledgeBase.import_failed')) }
  finally { if (alive) picking.value = false }
}
const edit = (action, item = null) => {
  dialog.value = action; target.value = item; name.value = item?.name || ''
  destination.value = item?.parent_id || '__root__'
}
const saveDialog = async () => {
  if (dialog.value !== 'move' && !name.value.trim()) return
  const payload = dialog.value === 'create_folder' ? { parent_id: parentId.value, name: name.value.trim() }
    : { id: target.value.id, expected_updated_at: target.value.updated_at, ...(dialog.value === 'move' ? { parent_id: destination.value === '__root__' ? null : destination.value } : { name: name.value.trim() }) }
  if (await mutate(dialog.value, payload)) dialog.value = ''
}
const remove = item => {
  const id = kbId.value
  return confirmModal = Modal.confirm({
  title: t('knowledgeBase.delete_item'), content: t('knowledgeBase.delete_item_confirm', { name: item.name }),
  okText: t('knowledgeBase.delete'), cancelText: t('knowledgeBase.cancel'), okType: 'danger',
  async onOk() {
    if (!alive || kbId.value !== id) return
    if (!await mutate('delete_item', { id: item.id, expected_updated_at: item.updated_at })) {
      if (operationConflict.value) return
      return Promise.reject()
    }
    if (preview.value?.item?.id === item.id || item.kind === 'folder') { previewGeneration++; preview.value = null }
  },
  })
}
const reindex = item => {
  const id = kbId.value
  return confirmModal = Modal.confirm({
  title: t('knowledgeBase.reindex'), content: t('knowledgeBase.reindex_confirm'),
  okText: t('knowledgeBase.reindex'), cancelText: t('knowledgeBase.cancel'), okType: 'default',
  async onOk() {
    if (!alive || kbId.value !== id) return
    if (!await mutate('reindex', item ? { id: item.id } : {})) return Promise.reject()
  },
  })
}
const openOriginal = async () => {
  try { await knowledgeRequest('open_file', { kb_id: kbId.value, id: preview.value.item.id }) }
  catch { message.error(t('knowledgeBase.open_failed')) }
}
const search = async () => {
  if (!searchQuery.value.trim()) return
  const request = ++searchGeneration
  searchLoading.value = true; searchFailed.value = false; searchErrorCode.value = ''; searched.value = true; results.value = []; warnings.value = []
  try {
    const data = await knowledgeRequest('search', { kb_ids: [kbId.value], query: searchQuery.value.trim(), mode: searchMode.value, ...(parentId.value ? { folder_id: parentId.value } : {}), limit: 20 })
    if (alive && request === searchGeneration) { results.value = data.results || []; warnings.value = data.warnings || [] }
  } catch (error) {
    if (alive && request === searchGeneration) {
      searchFailed.value = true
      searchErrorCode.value = error.code === 'invalid_query' ? 'invalid_query' : ''
    }
  }
  finally { if (alive && request === searchGeneration) searchLoading.value = false }
}
watch(kbId, () => {
  generation++; clearTimeout(timer); loading.value = false; failed.value = false; loadCode.value = ''
  confirmModal?.destroy?.(); confirmModal = null
  mutationGeneration++; busy.value = false
  previewGeneration++; searchGeneration++; preview.value = null; results.value = []; searched.value = false
  previewLoading.value = false; searchLoading.value = false; searchQuery.value = ''
  dialog.value = ''; target.value = null; skipped.value = []; searchFailed.value = false; searchErrorCode.value = ''; warnings.value = []; operationConflict.value = false
  parentId.value = null; page.value = 1; query.value = ''; base.value = null
  folders.value = []; items.value = []; breadcrumbs.value = []; total.value = 0
  if (kbId.value) load()
}, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++; previewGeneration++; searchGeneration++; clearTimeout(timer); confirmModal?.destroy?.() })
</script>

<template>
  <main class="kb-detail">
    <header class="kb-header">
      <a-breadcrumb>
        <a-breadcrumb-item><router-link :to="{ name: 'DataSpaceMain', query: { tab: 'knowledge-bases' } }">{{ t('knowledgeBase.title') }}</router-link></a-breadcrumb-item>
        <a-breadcrumb-item><span class="kb-name" :title="base?.name">{{ base?.name || t('knowledgeBase.title') }}</span></a-breadcrumb-item>
      </a-breadcrumb>
      <a-space class="kb-header-actions">
        <IconButton :text="t('knowledgeBase.refresh')" :loading="loading" @click="load()"><template #icon><Refresh /></template></IconButton>
        <IconButton :text="t('knowledgeBase.reindex_all')" :disabled="busy || !base" @click="reindex()"><template #icon><Redo /></template></IconButton>
      </a-space>
    </header>
    <div v-if="base" class="kb-meta">
      <span v-if="base.description">{{ base.description }}</span>
      <span>{{ base.embedding_provider }} / {{ base.embedding_model }}</span>
      <span>{{ t('knowledgeBase.document_count', { count: base.document_count || 0 }) }}</span>
    </div>
    <a-alert v-if="failed" type="warning" show-icon :message="t(loadCode === 'not_found' ? 'knowledgeBase.not_found' : 'knowledgeBase.load_failed')"><template #action><IconButton :text="t('knowledgeBase.retry')" @click="load()"><template #icon><Refresh /></template></IconButton></template></a-alert>
    <div v-if="base" class="kb-layout">
      <aside class="folders"><h2>{{ t('knowledgeBase.folders') }}</h2><a-tree :tree-data="tree" :field-names="{ key: 'id', title: 'name', children: 'children' }" :selected-keys="[parentId || '__root__']" default-expand-all @select="keys => keys.length && navigate(keys[0])" /></aside>
      <section class="files">
        <a-breadcrumb><a-breadcrumb-item><a-button type="link" size="small" @click="navigate(null)">{{ t('knowledgeBase.root') }}</a-button></a-breadcrumb-item><a-breadcrumb-item v-for="crumb in breadcrumbs" :key="crumb.id"><a-button type="link" size="small" @click="navigate(crumb.id)">{{ crumb.name }}</a-button></a-breadcrumb-item></a-breadcrumb>
        <a-flex wrap="wrap" gap="small" class="file-toolbar"><IconButton :text="t('knowledgeBase.import_files')" type="text" :loading="picking || busy" @click="importNative(false)"><template #icon><Upload /></template></IconButton><IconButton :text="t('knowledgeBase.import_folder')" :disabled="picking || busy" @click="importNative(true)"><template #icon><FolderOpen /></template></IconButton><IconButton :text="t('knowledgeBase.create_folder')" :disabled="busy" @click="edit('create_folder')"><template #icon><Add /></template></IconButton></a-flex>
        <a-alert v-if="skipped.length" type="warning" show-icon closable :message="t('knowledgeBase.import_skipped', { count: skipped.length })" @close="skipped = []"><template #description><ul><li v-for="(entry, index) in skipped" :key="index">{{ entry.name }} — {{ t(['unsupported_type', 'file_too_large', 'unsafe_path', 'file_missing'].includes(entry.error_code) ? 'knowledgeBase.' + entry.error_code : 'knowledgeBase.import_failed') }}</li></ul></template></a-alert>
        <a-input-search v-model:value="query" allow-clear :placeholder="t('knowledgeBase.find_files')" :aria-label="t('knowledgeBase.find_files')" @search="page = 1; load()" />
        <a-table :columns="columns" :data-source="items" :loading="loading" row-key="id" size="middle" :scroll="{ x: 560 }" :pagination="{ current: page, pageSize: 50, total, showSizeChanger: false, hideOnSinglePage: true }" @change="pagination => { page = pagination.current; load() }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'"><a-button type="link" class="file-link" @click="openPreview(record)">{{ record.kind === 'folder' ? '▸ ' : '' }}{{ record.name }}</a-button><small v-if="query">{{ record.path }}</small></template>
            <template v-else-if="column.key === 'status'"><a-tag v-if="record.kind === 'file'" :color="statusColor(record.status)">{{ t('knowledgeBase.status_' + record.status) }}</a-tag><p v-if="record.status === 'failed'" class="file-error">{{ t(indexingErrorKey(record.error_code)) }} <router-link v-if="canConfigureEmbedding(record.error_code)" :to="{ name: 'settings', query: { section: 'embedding_models' } }">{{ t('settings.embedding_models') }}</router-link></p><IconButton :text="t('knowledgeBase.retry')" v-if="record.status === 'failed' || record.status === 'unindexed'" type="link" size="small" :disabled="busy" @click="reindex(record)"><template #icon><Redo /></template></IconButton></template>
            <template v-else-if="column.key === 'byte_size'">{{ record.kind === 'folder' ? '—' : t('knowledgeBase.bytes', { count: record.byte_size || 0 }) }}</template>
            <template v-else-if="column.key === 'actions'"><a-dropdown :disabled="busy"><IconButton :text="t('knowledgeBase.actions')" size="small"><template #icon><More /></template></IconButton><template #overlay><a-menu><a-menu-item @click="edit('rename', record)">{{ t('knowledgeBase.rename') }}</a-menu-item><a-menu-item @click="edit('move', record)">{{ t('knowledgeBase.move') }}</a-menu-item><a-menu-item @click="reindex(record)">{{ t('knowledgeBase.reindex') }}</a-menu-item><a-menu-divider /><a-menu-item danger @click="remove(record)">{{ t('knowledgeBase.delete') }}</a-menu-item></a-menu></template></a-dropdown></template>
          </template>
        </a-table>
      </section>
      <aside class="right-pane">
        <a-tabs v-model:activeKey="rightTab">
          <a-tab-pane key="preview" :tab="t('knowledgeBase.preview')">
            <a-spin :spinning="previewLoading">
              <template v-if="preview"><h2>{{ preview.item.name }}</h2><p class="source-path">{{ preview.item.path }}</p><a-alert v-if="previewFailed" type="warning" :message="t('knowledgeBase.preview_failed')"><template #action><IconButton :text="t('knowledgeBase.retry')" @click="openPreview(preview.item)"><template #icon><Refresh /></template></IconButton></template></a-alert><a-alert v-if="preview.item.status === 'failed'" type="warning" show-icon :message="t(indexingErrorKey(preview.item.error_code))"><template #action><router-link v-if="canConfigureEmbedding(preview.item.error_code)" :to="{ name: 'settings', query: { section: 'embedding_models' } }">{{ t('settings.embedding_models') }}</router-link></template></a-alert><a-tabs v-model:activeKey="previewTab"><a-tab-pane key="text" :tab="t('knowledgeBase.text')"><a-alert v-if="preview.truncated" type="info" :message="t('knowledgeBase.truncated')" /><pre v-if="preview.text" class="source-text">{{ preview.text }}</pre><a-empty v-else-if="!previewLoading && !previewFailed" :description="t('knowledgeBase.no_text')" /></a-tab-pane><a-tab-pane key="info" :tab="t('knowledgeBase.info')"><a-descriptions :column="1" size="small"><a-descriptions-item :label="t('knowledgeBase.status')">{{ t('knowledgeBase.status_' + preview.item.status) }}</a-descriptions-item><a-descriptions-item :label="t('knowledgeBase.chunks')">{{ preview.item.chunk_count || 0 }}</a-descriptions-item><a-descriptions-item :label="t('knowledgeBase.updated')">{{ preview.item.updated_at }}</a-descriptions-item></a-descriptions><IconButton :text="t('knowledgeBase.open_original')" @click="openOriginal"><template #icon><OpenExternal /></template></IconButton><IconButton :text="t('knowledgeBase.reindex')" :disabled="busy" @click="reindex(preview.item)"><template #icon><Redo /></template></IconButton></a-tab-pane></a-tabs></template>
              <a-empty v-else :description="t('knowledgeBase.select_file')" />
            </a-spin>
          </a-tab-pane>
          <a-tab-pane key="search" :tab="t('knowledgeBase.search')">
            <p>{{ t('knowledgeBase.search_scope') }}</p><a-select v-model:value="searchMode" :aria-label="t('knowledgeBase.search_mode')" style="width: 100%; margin-bottom: 12px" :options="['hybrid', 'keyword', 'semantic'].map(mode => ({ value: mode, label: t('knowledgeBase.' + mode) }))" /><a-input-search v-model:value="searchQuery" :loading="searchLoading" :placeholder="t('knowledgeBase.search_hint')" :aria-label="t('knowledgeBase.search_hint')" @search="search" />
            <a-alert v-if="searchFailed" type="warning" :message="t(searchErrorCode === 'invalid_query' ? 'knowledgeBase.invalid_query' : 'knowledgeBase.search_failed')"><template #action><IconButton :text="t('knowledgeBase.retry')" @click="search"><template #icon><Refresh /></template></IconButton></template></a-alert><a-alert v-if="warnings.some(warning => warning.error_code !== 'rerank_unavailable')" type="warning" :message="t(warnings.some(warning => warning.error_code === 'index_incomplete') ? 'knowledgeBase.index_incomplete' : 'knowledgeBase.search_warning')" /><a-alert v-if="warnings.some(warning => warning.error_code === 'rerank_unavailable')" type="warning" show-icon :message="t('knowledgeBase.rerank_unavailable')"><template #action><router-link :to="{ name: 'settings', query: { section: 'rerank_models' } }">{{ t('settings.rerank_models') }}</router-link></template></a-alert>
            <a-spin :spinning="searchLoading"><a-list v-if="results.length" :data-source="results"><template #renderItem="{ item }"><a-list-item><article><a-button type="link" class="file-link" @click="openPreview({ id: item.document_id, name: item.document_name, path: item.path, kind: 'file' })">{{ item.document_name }}</a-button><p class="source-path">{{ item.path }}</p><pre class="source-text">{{ item.text }}</pre></article></a-list-item></template></a-list><a-empty v-if="searched && !searchLoading && !searchFailed && !results.length" :description="t('knowledgeBase.no_results')" /></a-spin>
          </a-tab-pane>
        </a-tabs>
      </aside>
    </div>
    <a-modal ok-type="default" :open="Boolean(dialog)" :title="t('knowledgeBase.' + (dialog || 'name'))" :confirm-loading="busy" :ok-text="t('knowledgeBase.save')" :cancel-text="t('knowledgeBase.cancel')" @cancel="dialog = ''" @ok="saveDialog"><a-form layout="vertical"><a-form-item v-if="dialog === 'move'" :label="t('knowledgeBase.destination')"><a-select v-model:value="destination" :options="moveOptions" show-search option-filter-prop="label" /></a-form-item><a-form-item v-else :label="t('knowledgeBase.name')" required><a-input v-model:value="name" :maxlength="255" @press-enter="saveDialog" /></a-form-item></a-form></a-modal>
  </main>
</template>

<style scoped>
.kb-detail { padding: 24px; color: var(--site-text-color); }
.kb-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 8px; }
.kb-header .ant-breadcrumb { flex: 1; min-width: 0; }
.kb-header :deep(.ant-breadcrumb ol) { flex-wrap: nowrap; }
.kb-header :deep(.ant-breadcrumb li:last-child) { min-width: 0; }
.kb-header-actions { flex-shrink: 0; }
.kb-name { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-bottom: 16px; font-size: 12px; color: var(--site-secondary-text-color); overflow-wrap: anywhere; }
h2 { font-size: 14px; overflow-wrap: anywhere; }
small, .source-path { color: var(--site-secondary-text-color); overflow-wrap: anywhere; }
.kb-layout { display: grid; grid-template-columns: 200px minmax(350px, 1fr) minmax(280px, 360px); border: var(--light-border); background: var(--component-background); min-height: 600px; }
.folders, .files, .right-pane { padding: 16px; min-width: 0; }
.folders, .files { border-right: var(--light-border); }.file-toolbar { margin: 16px 0; }
.files > .ant-input-search { margin-bottom: 16px; }.file-link { padding: 0; height: auto; white-space: normal; text-align: left; overflow-wrap: anywhere; }
.files small { display: block; }.source-text { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; font-size: 13px; line-height: 1.75; max-height: 65vh; overflow: auto; }
.file-error { margin: 6px 0; max-width: 240px; font-size: 12px; color: var(--site-secondary-text-color); }.source-path { font-size: 12px; }article { min-width: 0; width: 100%; }
@media (max-width: 1200px) { .kb-layout { grid-template-columns: 170px minmax(0, 1fr); }.right-pane { grid-column: 1 / -1; border-top: var(--light-border); } }
@media (max-width: 650px) { .kb-detail { padding: 12px; }.kb-layout { grid-template-columns: minmax(0, 1fr); }.right-pane { grid-column: auto; }.folders { max-height: 200px; overflow: auto; } }
</style>
