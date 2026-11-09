<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import {
  Add,
  BookOpen,
  Search,
  Control,
  ToTop,
  ToBottom,
  Edit,
  Delete,
  Upload,
  FolderOpen,
  DocDetail,
  ViewGridCard,
  ListOne,
  Refresh, Close } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatTaskTime } from '@/utils/taskAgentPresentation'
import { formatIntegrationError, extractSkillDiagnostics } from '@/utils/taskAgentErrors'
import { fileSize } from '@/utils/taskAgentTimeline'

const { t, locale } = useI18n()
const route = useRoute(), router = useRouter()
const skills = ref([]), loading = ref(true), failed = ref(false)
const search = ref(String(route.query.search || ''))
const filter = computed(() => ['enabled', 'disabled'].includes(route.query.filter) ? route.query.filter : 'all')
const sort = computed(() => ['name', 'oldest'].includes(route.query.sort) ? route.query.sort : 'recent')
const view = computed(() => route.query.view === 'list' ? 'list' : 'grid')
const page = computed(() => Math.max(1, Number.parseInt(route.query.page, 10) || 1))
const pageSize = 24
const togglingIds = reactive({})

const importOpen = ref(false)
const importSaving = ref(false)
const importError = ref('')
const importDiagnostics = ref([])
const importMode = ref('manual')
const localRoots = ref([]), localSkills = ref([]), localSelected = ref([])
const localLoading = ref(false), localFailed = ref(false), localLoaded = ref(false), localLimited = ref(false)
const localSearch = ref(''), localSource = ref('all')
let localScanGeneration = 0
const localVisible = computed(() => {
  const query = localSearch.value.trim().toLocaleLowerCase()
  return localSkills.value.filter(item => (localSource.value === 'all' || item.sources.includes(localSource.value)) &&
    (!query || `${item.name} ${item.description} ${item.path}`.toLocaleLowerCase().includes(query)))
})
const localSelectable = computed(() => localVisible.value.filter(item => !item.error_code && !item.imported_id))
const localAllSelected = computed(() => localSelectable.value.length > 0 && localSelectable.value.every(item => localSelected.value.includes(item.path)))
const localSomeSelected = computed(() => localSelectable.value.some(item => localSelected.value.includes(item.path)))
const localError = item => item.import_error || (item.error_code ? formatIntegrationError({
  data: { integration_error: { kind: 'skills', code: item.error_code } },
}, t) : '')
const importDraft = reactive({
  skill_id: '',
  path: '',
  enabled: true,
})

const filters = computed(() => [
  { key: 'all', label: t('workspace.taskAgentSpace.skills_filter_all') },
  { key: 'enabled', label: t('workspace.taskAgentSpace.skills_filter_enabled') },
  { key: 'disabled', label: t('workspace.taskAgentSpace.skills_filter_disabled') },
])

const updateQuery = patch => {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key] || (key === 'page' && Number(query[key]) === 1)) delete query[key]
  return router.replace({ name: 'taskAgentSkills', query })
}

const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return skills.value.filter(skill =>
    (filter.value === 'all' || (filter.value === 'enabled' ? skill.enabled : !skill.enabled)) &&
    (!query || `${skill.name || ''} ${skill.description || ''}`.toLocaleLowerCase().includes(query)))
    .sort((left, right) => sort.value === 'name'
      ? String(left.name || '').localeCompare(String(right.name || ''), locale.value)
      : ((Date.parse(right.updated_at || '') || 0) - (Date.parse(left.updated_at || '') || 0)) * (sort.value === 'oldest' ? -1 : 1) ||
        String(left.name || '').localeCompare(String(right.name || ''), locale.value))
})

const currentPage = computed(() => Math.min(page.value, Math.max(1, Math.ceil(filtered.value.length / pageSize))))
const visible = computed(() => filtered.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize))

let alive = true, generation = 0, importGeneration = 0, searchTimer = null
const load = async () => {
  const version = ++generation
  loading.value = true; failed.value = false
  try {
    const response = await taskAgentAPI('skills')
    if (!alive || version !== generation) return
    if (response.status !== 200 || !Array.isArray(response.data?.skills)) throw new Error()
    skills.value = response.data.skills
  } catch {
    if (alive && version === generation) failed.value = true
  } finally {
    if (alive && version === generation) loading.value = false
  }
}

const toggleSkillEnabled = async (skill, nextEnabled) => {
  if (togglingIds[skill.skill_id]) return
  togglingIds[skill.skill_id] = true
  try {
    const response = await taskAgentAPI('save_skill', {
      skill_id: skill.skill_id,
      enabled: Boolean(nextEnabled),
      expected_updated_at: skill.updated_at,
    })
    if (!alive) return
    if (response.status !== 200 || !response.data?.skill_id) {
      message.error(formatIntegrationError(response, t))
      if (response.status === 409) await load()
      return
    }
    const idx = skills.value.findIndex(item => item.skill_id === skill.skill_id)
    if (idx >= 0) skills.value[idx] = { ...skills.value[idx], ...response.data }
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.save_failed'))
  } finally {
    delete togglingIds[skill.skill_id]
  }
}

const confirmDeleteSkill = skill => {
  Modal.confirm({
    title: t('workspace.taskAgentSpace.skill_delete_title', { name: skill.name }),
    content: t('workspace.taskAgentSpace.skill_delete_confirm', { name: skill.name }),
    okText: t('workspace.taskAgentSpace.skill_delete_action'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      try {
        const response = await taskAgentAPI('delete_skill', {
          skill_id: skill.skill_id,
          expected_updated_at: skill.updated_at,
        })
        if (response.status !== 200) {
          if (alive) message.error(formatIntegrationError(response, t))
          if (alive && (response.status === 409 || response.status === 404)) await load()
          return Promise.reject(new Error('delete_failed'))
        }
        if (alive) {
          skills.value = skills.value.filter(item => item.skill_id !== skill.skill_id)
          message.success(t('workspace.taskAgentSpace.skill_deleted'))
        }
      } catch (err) {
        if (err?.message !== 'delete_failed' && alive) {
          message.error(t('workspace.taskAgentSpace.delete_error_failed'))
        }
        return Promise.reject(err)
      }
    },
  })
}

const openImportModal = () => {
  if (importSaving.value) return
  importGeneration++
  importDraft.skill_id = 'skill_' + uuidv4().replaceAll('-', '').slice(0, 16)
  importDraft.path = ''
  importDraft.enabled = true
  importError.value = ''
  importDiagnostics.value = []
  importOpen.value = true
  importMode.value = 'manual'
  localScanGeneration++
  localRoots.value = []; localSkills.value = []; localSelected.value = []
  localSearch.value = ''; localSource.value = 'all'
  localLoaded.value = false; localFailed.value = false; localLoading.value = false; localLimited.value = false
}

const closeImportModal = () => {
  if (importSaving.value) return
  importGeneration++
  localScanGeneration++
  importOpen.value = false
}

const scanLocalSkills = async () => {
  if (importSaving.value) return
  const scan = ++localScanGeneration, draft = importGeneration
  localLoading.value = true
  localFailed.value = false
  try {
    const response = await taskAgentAPI('local_skills')
    if (!alive || scan !== localScanGeneration || draft !== importGeneration || !importOpen.value) return
    if (response.status !== 200 || !Array.isArray(response.data?.roots) || !Array.isArray(response.data?.skills)) throw new Error()
    if (!response.data.roots.every(root => root && typeof root.id === 'string' && typeof root.label === 'string' &&
      typeof root.path === 'string' && ['ready', 'missing', 'unavailable', 'limited'].includes(root.status) && Number.isInteger(root.count)) ||
      !response.data.skills.every(item => item && typeof item.path === 'string' && typeof item.name === 'string' &&
        typeof item.description === 'string' && typeof item.error_code === 'string' && Array.isArray(item.sources))) throw new Error()
    const previous = new Map(localSkills.value.map(item => [item.path, item]))
    localRoots.value = response.data.roots
    localSkills.value = response.data.skills.map(item => ({ ...item,
      import_id: previous.get(item.path)?.import_id || 'skill_' + uuidv4().replaceAll('-', '').slice(0, 16),
      imported_id: previous.get(item.path)?.imported_id || '', import_error: '',
    }))
    const available = new Set(localSkills.value.filter(item => !item.error_code && !item.imported_id).map(item => item.path))
    localSelected.value = localSelected.value.filter(path => available.has(path))
    localLimited.value = Boolean(response.data.truncated)
    localLoaded.value = true
  } catch {
    if (alive && scan === localScanGeneration && draft === importGeneration) localFailed.value = true
  } finally {
    if (alive && scan === localScanGeneration && draft === importGeneration) localLoading.value = false
  }
}
const selectLocalSkill = path => {
  if (importSaving.value || localLoading.value) return
  localSelected.value = localSelected.value.includes(path) ? localSelected.value.filter(value => value !== path) : [...localSelected.value, path]
}
const selectVisibleLocalSkills = () => {
  if (importSaving.value || localLoading.value) return
  const visiblePaths = new Set(localSelectable.value.map(item => item.path))
  localSelected.value = localAllSelected.value ? localSelected.value.filter(path => !visiblePaths.has(path)) : [...new Set([...localSelected.value, ...visiblePaths])]
}
const submitLocalImports = async () => {
  if (importSaving.value || localLoading.value || localFailed.value || !localSelected.value.length) return
  const targets = localSkills.value.filter(item => localSelected.value.includes(item.path) && !item.error_code && !item.imported_id)
  if (!targets.length) return
  const request = ++importGeneration
  importSaving.value = true
  let imported = 0
  try {
    for (const item of targets) {
      if (!alive || request !== importGeneration) return
      item.import_error = ''
      try {
        const response = await taskAgentAPI('import_skill', { skill_id: item.import_id, path: item.path, enabled: Boolean(importDraft.enabled) })
        if (!alive || request !== importGeneration) return
        if (response.status !== 200 || !response.data?.skill_id) {
          item.import_error = formatIntegrationError(response, t)
          if (response.status >= 500) break
          continue
        }
        item.imported_id = response.data.skill_id
        localSelected.value = localSelected.value.filter(path => path !== item.path)
        imported++
      } catch {
        if (alive && request === importGeneration) item.import_error = t('workspace.taskAgentSpace.save_failed')
        break
      }
    }
    if (!alive || request !== importGeneration) return
    if (imported) {
      message.success(t('workspace.taskAgentSpace.skill_local_imported_count', { count: imported }))
      await load()
      if (alive && request === importGeneration && !localSelected.value.length) importOpen.value = false
    }
  } finally {
    if (alive && request === importGeneration) importSaving.value = false
  }
}
watch(importMode, mode => { if (mode === 'local' && importOpen.value && !localLoaded.value && !localLoading.value) scanLocalSkills() })

const pickImportFolder = async () => {
  if (importSaving.value) return
  const draftId = importDraft.skill_id
  const reqGen = importGeneration
  try {
    if (typeof window?.pywebview?.api?.open_folder_dialog !== 'function') {
      message.warning(t('workspace.taskAgentSpace.project_pick_failed'))
      return
    }
    const selected = await window.pywebview.api.open_folder_dialog('')
    if (!alive || reqGen !== importGeneration || importDraft.skill_id !== draftId || importSaving.value) return
    const folder = Array.isArray(selected) ? selected[0] : selected
    if (typeof folder === 'string' && folder.trim()) {
      importDraft.path = folder.trim()
    }
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.project_pick_failed'))
  }
}

const pickImportFile = async () => {
  if (importSaving.value) return
  const draftId = importDraft.skill_id
  const reqGen = importGeneration
  try {
    if (typeof window?.pywebview?.api?.open_file_dialog !== 'function') {
      message.warning(t('workspace.taskAgentSpace.project_pick_failed'))
      return
    }
    const selected = await window.pywebview.api.open_file_dialog(false)
    if (!alive || reqGen !== importGeneration || importDraft.skill_id !== draftId || importSaving.value) return
    const file = Array.isArray(selected) ? selected[0] : selected
    if (typeof file === 'string' && file.trim()) {
      importDraft.path = file.trim()
    }
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.project_pick_failed'))
  }
}

const submitImport = async () => {
  if (importMode.value === 'local') return submitLocalImports()
  if (importSaving.value) return
  const trimmedPath = String(importDraft.path || '').trim()
  if (!trimmedPath) {
    importError.value = t('workspace.taskAgentSpace.integration_error_skills_invalid_source')
    importDiagnostics.value = []
    return
  }
  const reqGen = ++importGeneration
  const draftId = importDraft.skill_id
  importSaving.value = true
  importError.value = ''
  importDiagnostics.value = []
  try {
    const response = await taskAgentAPI('import_skill', {
      skill_id: draftId,
      path: trimmedPath,
      enabled: Boolean(importDraft.enabled),
    })
    if (!alive || reqGen !== importGeneration || importDraft.skill_id !== draftId) return
    if (response.status !== 200 || !response.data?.skill_id) {
      importError.value = formatIntegrationError(response, t)
      importDiagnostics.value = extractSkillDiagnostics(response)
      return
    }
    importOpen.value = false
    message.success(t('workspace.taskAgentSpace.skill_imported'))
    await router.push({ name: 'taskAgentSkillDetail', params: { skillId: response.data.skill_id } })
  } catch {
    if (alive && reqGen === importGeneration && importDraft.skill_id === draftId) {
      importError.value = t('workspace.taskAgentSpace.save_failed')
    }
  } finally {
    if (alive && reqGen === importGeneration && importDraft.skill_id === draftId) {
      importSaving.value = false
    }
  }
}

const sourceKindLabel = kind => {
  if (kind === 'directory') return t('workspace.taskAgentSpace.skill_source_directory')
  if (kind === 'archive') return t('workspace.taskAgentSpace.skill_source_archive')
  return t('workspace.taskAgentSpace.skill_source_manual')
}

watch(search, value => {
  clearTimeout(searchTimer)
  if (value === String(route.query.search || '')) return
  searchTimer = setTimeout(() => updateQuery({ search: value.trim() || undefined, page: undefined }), 200)
})
watch(() => route.query.search, value => { clearTimeout(searchTimer); search.value = String(value || '') })
onMounted(load)
onBeforeUnmount(() => { alive = false; importGeneration++; localScanGeneration++; clearTimeout(searchTimer) })
</script>

<template>
  <main class="skill-catalog">
    <header class="catalog-header">
      <div class="catalog-title">
        <h1>{{ t('workspace.taskAgentSpace.skills_title') }}</h1>
        <span>{{ t('workspace.taskAgentSpace.profile_total', { count: skills.length }) }}</span>
      </div>
      <div class="header-actions">
        <IconButton @click="openImportModal" :text="t('workspace.taskAgentSpace.skill_import')"><template #icon><Upload /></template></IconButton>
        <router-link :to="{ name: 'taskAgentSkillCreate', query: route.query }">
          <IconButton type="primary" :text="t('workspace.taskAgentSpace.skill_create')"><template #icon><Add /></template></IconButton>
        </router-link>
      </div>
    </header>

    <div class="catalog-toolbar">
      <a-input
        v-model:value="search"
        allow-clear
        class="catalog-search"
        :aria-label="t('workspace.taskAgentSpace.skills_search')"
        :placeholder="t('workspace.taskAgentSpace.skills_search')"
      >
        <template #prefix><Search /></template>
      </a-input>
      <div class="toolbar-actions">
        <a-dropdown :trigger="['click']">
          <IconButton :class="{ 'filter-active': filter !== 'all' }" :text="t('workspace.taskAgentSpace.profile_filter') + ': ' + t('workspace.taskAgentSpace.skills_filter_' + filter)"><template #icon><Control /></template></IconButton>
          <template #overlay>
            <a-menu :selected-keys="[filter]" @click="({ key }) => updateQuery({ filter: key === 'all' ? undefined : key, page: undefined })">
              <a-menu-item v-for="item in filters" :key="item.key">{{ item.label }}</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
        <a-dropdown :trigger="['click']">
          <IconButton :aria-label="t('workspace.taskAgentSpace.profile_sort_' + sort)" :text="t('workspace.taskAgentSpace.profile_sort_' + sort)"><template #icon><ToTop v-if="sort === 'oldest'" /><ToBottom v-else /></template></IconButton>
          <template #overlay>
            <a-menu :selected-keys="[sort]" @click="({ key }) => updateQuery({ sort: key === 'recent' ? undefined : key, page: undefined })">
              <a-menu-item key="recent">{{ t('workspace.taskAgentSpace.profile_sort_recent') }}</a-menu-item>
              <a-menu-item key="oldest">{{ t('workspace.taskAgentSpace.profile_sort_oldest') }}</a-menu-item>
              <a-menu-item key="name">{{ t('workspace.taskAgentSpace.profile_sort_name') }}</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
        <div class="view-toggle" role="group" :aria-label="t('workspace.taskAgentSpace.profile_view')">
          <IconButton :type="view === 'grid' ? 'primary' : 'text'" size="small" :aria-label="t('workspace.taskAgentSpace.profile_grid')" @click="updateQuery({ view: undefined })" :text="t('workspace.taskAgentSpace.profile_grid')"><template #icon><ViewGridCard /></template></IconButton>
          <IconButton :type="view === 'list' ? 'primary' : 'text'" size="small" :aria-label="t('workspace.taskAgentSpace.profile_list')" @click="updateQuery({ view: 'list' })" :text="t('workspace.taskAgentSpace.profile_list')"><template #icon><ListOne /></template></IconButton>
        </div>
      </div>
    </div>

    <div class="catalog-content">
      <div v-if="loading" class="catalog-loading"><a-spin size="large" /></div>
      <div v-else-if="failed" class="catalog-empty">
        <a-empty :description="t('workspace.taskAgentSpace.load_failed')">
          <IconButton type="primary" @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
        </a-empty>
      </div>
      <div v-else-if="visible.length === 0" class="catalog-empty">
        <a-empty :description="skills.length ? t('workspace.taskAgentSpace.skills_no_results') : t('workspace.taskAgentSpace.skills_empty')">
          <a-space>
            <IconButton v-if="search || filter !== 'all'" @click="search = ''; updateQuery({ search: undefined, filter: undefined, page: undefined })" :text="t('workspace.taskAgentSpace.profile_clear_filters')"><template #icon><Close /></template></IconButton>
            <a-button @click="openImportModal">
              <template #icon><Upload /></template>
              {{ t('workspace.taskAgentSpace.skill_import') }}
            </a-button>
            <router-link :to="{ name: 'taskAgentSkillCreate', query: route.query }">
              <a-button type="primary">{{ t('workspace.taskAgentSpace.skill_create') }}</a-button>
            </router-link>
          </a-space>
        </a-empty>
      </div>
      <template v-else>
        <p class="catalog-summary">{{ t('workspace.taskAgentSpace.skills_showing', { count: filtered.length }) }}</p>
        <div class="skill-grid" :class="{ 'list-view': view === 'list' }">
          <article v-for="skill in visible" :key="skill.skill_id" class="skill-card" :class="{ 'is-disabled': !skill.enabled }">
            <router-link :to="{ name: 'taskAgentSkillDetail', params: { skillId: skill.skill_id }, query: route.query }" class="skill-card-link">
              <div class="card-top">
                <div class="skill-avatar"><BookOpen size="20" /></div>
                <div class="card-copy">
                  <div class="card-heading">
                    <h2>{{ skill.name }}</h2>
                    <span class="version-badge">v{{ skill.version }}</span>
                    <span class="status-pill" :class="skill.enabled ? 'enabled' : 'disabled'">
                      {{ skill.enabled ? t('workspace.taskAgentSpace.skill_status_enabled') : t('workspace.taskAgentSpace.skill_status_disabled') }}
                    </span>
                  </div>
                  <p class="skill-description">{{ skill.description }}</p>
                </div>
              </div>
              <div class="card-meta">
                <span><DocDetail />{{ t('workspace.taskAgentSpace.skill_file_count', { count: skill.file_count || 1 }) }}</span>
                <span>{{ fileSize(skill.total_bytes || 0) }}</span>
              </div>
              <div class="card-footer">
                <span class="source-label"><i></i>{{ sourceKindLabel(skill.source_kind) }}</span>
                <time :datetime="skill.updated_at">{{ formatTaskTime(skill.updated_at, locale) }}</time>
              </div>
            </router-link>
            <div class="card-actions" @click.stop>
              <a-switch
                size="small"
                :checked="skill.enabled"
                :loading="Boolean(togglingIds[skill.skill_id])"
                :aria-label="t('workspace.taskAgentSpace.skill_toggle_label', { name: skill.name })"
                @change="checked => toggleSkillEnabled(skill, checked)"
              />
              <router-link
                :to="{ name: 'taskAgentSkillDetail', params: { skillId: skill.skill_id }, query: route.query }"
                :aria-label="t('workspace.taskAgentSpace.skill_inspect_name', { name: skill.name })"
                :title="t('workspace.taskAgentSpace.skill_inspect_name', { name: skill.name })"
              >
                <Edit />
              </router-link>
              <IconButton
                type="text"
                size="small"
                danger
                :aria-label="t('workspace.taskAgentSpace.skill_delete_name', { name: skill.name })"
                @click="confirmDeleteSkill(skill)"
               :text="t('workspace.taskAgentSpace.skill_delete_name', { name: skill.name })"><template #icon><Delete /></template></IconButton>
            </div>
          </article>
        </div>
        <div v-if="filtered.length > pageSize" class="catalog-pagination">
          <a-pagination :current="currentPage" :total="filtered.length" :page-size="pageSize" :show-size-changer="false" @change="next => updateQuery({ page: next })" />
        </div>
      </template>
    </div>

    <a-modal
      :open="importOpen"
      :title="t('workspace.taskAgentSpace.skill_import_title')"
      :width="importMode === 'local' ? 760 : 520"
      :confirm-loading="importSaving"
      :closable="!importSaving"
      :mask-closable="!importSaving"
      :keyboard="!importSaving"
      :cancel-button-props="{ disabled: importSaving }"
      :ok-text="importMode === 'local' ? t('workspace.taskAgentSpace.skill_local_import_selected', { count: localSelected.length }) : t('workspace.taskAgentSpace.skill_import_confirm')"
      :ok-button-props="{ disabled: importMode === 'local' && (localLoading || localFailed || !localSelected.length) }"
      :cancel-text="t('common.cancel')"
      @cancel="closeImportModal"
      @ok="submitImport"
    >
      <a-tabs v-model:activeKey="importMode" class="skill-import-tabs">
        <a-tab-pane key="manual" :tab="t('workspace.taskAgentSpace.skill_import_manual_tab')" :disabled="importSaving">
      <p class="modal-hint">{{ t('workspace.taskAgentSpace.skill_import_hint') }}</p>
      <a-alert
        v-if="importError"
        type="error"
        show-icon
        class="import-alert"
        :message="importError"
      >
        <template v-if="importDiagnostics.length" #description>
          <ul class="diagnostic-list">
            <li v-for="(diag, index) in importDiagnostics" :key="index">{{ diag }}</li>
          </ul>
        </template>
      </a-alert>
      <a-form layout="vertical">
        <a-form-item :label="t('workspace.taskAgentSpace.skill_import_path')" required>
          <a-input
            v-model:value="importDraft.path"
            :disabled="importSaving"
            :aria-label="t('workspace.taskAgentSpace.skill_import_path')"
            :placeholder="t('workspace.taskAgentSpace.skill_import_path_placeholder')"
            @pressEnter="submitImport"
          />
          <div class="picker-actions">
            <IconButton size="small" :disabled="importSaving" @click="pickImportFolder" :text="t('workspace.taskAgentSpace.skill_pick_folder')"><template #icon><FolderOpen /></template></IconButton>
            <IconButton size="small" :disabled="importSaving" @click="pickImportFile" :text="t('workspace.taskAgentSpace.skill_pick_file')"><template #icon><DocDetail /></template></IconButton>
          </div>
        </a-form-item>
      </a-form>
        </a-tab-pane>
        <a-tab-pane key="local" :tab="t('workspace.taskAgentSpace.skill_import_local_tab')" :disabled="importSaving">
          <p class="modal-hint">{{ t('workspace.taskAgentSpace.skill_local_hint') }}</p>
          <div class="local-skill-toolbar">
            <a-input v-model:value="localSearch" allow-clear :disabled="importSaving" :placeholder="t('workspace.taskAgentSpace.skills_search')" :aria-label="t('workspace.taskAgentSpace.skills_search')"><template #prefix><Search /></template></a-input>
            <a-select v-model:value="localSource" :disabled="importSaving" :aria-label="t('workspace.taskAgentSpace.skill_local_source')" :options="[{ value: 'all', label: t('workspace.taskAgentSpace.skill_local_all_sources') }, ...localRoots.map(root => ({ value: root.id, label: `${root.label} (${root.count})` }))]" />
            <IconButton type="text" :loading="localLoading" :disabled="importSaving" :aria-label="t('workspace.taskAgentSpace.skill_local_refresh')" @click="scanLocalSkills" :text="t('workspace.taskAgentSpace.skill_local_refresh')"><template #icon><Refresh /></template></IconButton>
          </div>
          <div class="local-skill-roots"><span v-for="root in localRoots" :key="root.id" :title="root.path">{{ root.label }}<small v-if="root.status !== 'ready'"> · {{ t('workspace.taskAgentSpace.skill_local_source_' + root.status) }}</small></span></div>
          <a-alert v-if="localFailed" type="warning" show-icon :message="t('workspace.taskAgentSpace.skill_local_scan_failed')"><template #action><IconButton size="small" :disabled="importSaving" @click="scanLocalSkills" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
          <a-alert v-if="localLimited" type="info" show-icon :message="t('workspace.taskAgentSpace.skill_local_scan_limited')" />
          <div v-if="localLoading" class="local-skill-loading"><a-spin /></div>
          <template v-else-if="localVisible.length">
            <div class="local-skill-selection"><a-checkbox :checked="localAllSelected" :indeterminate="localSomeSelected && !localAllSelected" :disabled="importSaving || localFailed || !localSelectable.length" @change="selectVisibleLocalSkills">{{ t('workspace.taskAgentSpace.skill_local_select_visible') }}</a-checkbox><span>{{ t('workspace.taskAgentSpace.skill_local_selected_count', { count: localSelected.length }) }}</span></div>
            <div class="local-skill-list">
              <div v-for="item in localVisible" :key="item.path" class="local-skill-row" :class="{ 'is-imported': item.imported_id }">
                <a-checkbox :checked="localSelected.includes(item.path)" :disabled="importSaving || localFailed || Boolean(item.error_code || item.imported_id)" @change="selectLocalSkill(item.path)">
                  <span class="local-skill-copy"><strong>{{ item.name }}</strong><small v-if="item.imported_id" class="local-imported">{{ t('workspace.taskAgentSpace.skill_local_imported') }}</small><small v-else-if="skills.some(skill => skill.name === item.name)">{{ t('workspace.taskAgentSpace.skill_local_same_name') }}</small><span v-if="item.description" class="local-skill-description">{{ item.description }}</span><code>{{ item.path }}</code></span>
                </a-checkbox>
                <p v-if="localError(item)" class="local-skill-error" role="alert">{{ localError(item) }}</p>
              </div>
            </div>
          </template>
          <a-empty v-else-if="localLoaded && !localFailed" :description="localSearch || localSource !== 'all' ? t('workspace.taskAgentSpace.skills_no_results') : t('workspace.taskAgentSpace.skill_local_empty')" />
        </a-tab-pane>
      </a-tabs>
      <div class="import-switch-row">
        <span>{{ t('workspace.taskAgentSpace.skill_enable_after_import') }}</span>
        <a-switch v-model:checked="importDraft.enabled" :disabled="importSaving" :aria-label="t('workspace.taskAgentSpace.skill_enable_after_import')" />
      </div>
    </a-modal>
  </main>
</template>

<style scoped>
.toolbar-actions :deep(.filter-active) { color: var(--color-primary); }
.skill-catalog { display: flex; flex-direction: column; min-height: 100%; background: var(--gray-background); color: var(--site-text-color); }
.catalog-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 24px 14px; background: var(--component-background); border-bottom: var(--light-border); }
.catalog-title { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
.header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
h1 { margin: 0; font-size: 20px; font-weight: 600; line-height: 1.3; }
.catalog-title span, .catalog-summary { color: var(--site-secondary-text-color); font-size: 12px; }
.catalog-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 24px 0; max-width: 1560px; width: 100%; margin: 0 auto; }
.catalog-search { max-width: 340px; }
.toolbar-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.view-toggle { display: inline-flex; padding: 2px; border: var(--light-border); border-radius: 6px; background: var(--component-background); }
.catalog-content { flex: 1; max-width: 1560px; width: 100%; margin: 0 auto; padding: 12px 24px 32px; }
.catalog-summary { margin: 0 0 8px; }
.skill-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.skill-card { position: relative; min-width: 0; border: 1px solid color-mix(in srgb, var(--site-text-color) 7%, transparent); border-radius: 8px; background: var(--component-background); content-visibility: auto; contain-intrinsic-size: auto 164px; }
.skill-card.is-disabled { opacity: 0.78; }
.skill-card-link { color: inherit; display: flex; height: 100%; min-height: 164px; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: inherit; text-decoration: none; }
.card-top { display: flex; align-items: flex-start; gap: 11px; min-width: 0; }
.skill-avatar { width: 40px; height: 40px; flex: 0 0 40px; display: flex; align-items: center; justify-content: center; background: color-mix(in srgb, var(--color-primary) 8%, var(--component-background)); border: var(--light-border); color: color-mix(in srgb, var(--color-primary) 72%, var(--site-text-color)); border-radius: 7px; }
.card-copy { min-width: 0; flex: 1; }
.card-heading { display: flex; align-items: center; gap: 6px; padding-right: 88px; flex-wrap: wrap; }
h2 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; font-weight: 600; line-height: 1.5; max-width: 100%; }
.version-badge { padding: 1px 6px; border-radius: 4px; background: var(--gray-background); color: var(--site-secondary-text-color); font-size: 11px; font-variant-numeric: tabular-nums; }
.status-pill { padding: 1px 6px; border-radius: 4px; font-size: 11px; }
.status-pill.enabled { color: #2f855a; background: color-mix(in srgb, #2f855a 12%, transparent); }
.status-pill.disabled { color: var(--site-secondary-text-color); background: var(--gray-background); }
.skill-description { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; overflow-wrap: anywhere; margin: 4px 0 0; color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.7; }
.card-meta { display: flex; flex-wrap: wrap; gap: 10px; color: var(--site-secondary-text-color); font-size: 11px; line-height: 1.5; }
.card-meta span { display: inline-flex; align-items: center; gap: 4px; }
.card-meta :deep(svg) { width: 12px; height: 12px; }
.card-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: auto; min-width: 0; font-size: 11px; color: var(--site-secondary-text-color); }
.source-label { display: inline-flex; min-width: 0; max-width: 72%; align-items: center; gap: 5px; padding: 2px 7px; border-radius: 4px; background: var(--gray-background); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-label i { height: 6px; width: 6px; border-radius: 1px; background: var(--color-primary); flex-shrink: 0; }
time { white-space: nowrap; font-variant-numeric: tabular-nums; }
.card-actions { position: absolute; top: 10px; right: 10px; display: flex; align-items: center; gap: 4px; padding: 2px 4px; border-radius: 5px; background: var(--component-background); opacity: 0; pointer-events: none; }
.card-actions :deep(.ant-btn), .card-actions > :deep(a), .card-actions :deep(a) { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; padding: 0; color: var(--site-secondary-text-color); border-radius: 4px; }
.card-actions :deep(svg) { width: 14px; height: 14px; }
.skill-card:focus-within .card-actions { opacity: 1; pointer-events: auto; }
.skill-card-link:focus-visible, .card-actions a:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.catalog-loading, .catalog-empty { padding: 80px 16px; text-align: center; }
.catalog-pagination { margin-top: 24px; text-align: right; }
.list-view { grid-template-columns: minmax(0, 1fr); }
.list-view .skill-card { contain-intrinsic-size: auto 96px; }
.list-view .skill-card-link { min-height: 96px; display: grid; grid-template-columns: minmax(240px, 1.6fr) minmax(150px, 1fr) minmax(160px, 1fr); align-items: center; gap: 20px; }
.list-view .card-footer { flex-wrap: wrap; justify-content: flex-end; padding-right: 110px; }
.modal-hint { margin: 0 0 12px; color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.65; }
.import-alert { margin-bottom: 14px; }
.diagnostic-list { margin: 6px 0 0; padding-left: 18px; font-size: 12px; }
.picker-actions { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.import-switch-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 4px; font-size: 13px; }
.local-skill-toolbar { display: flex; gap: 8px; align-items: center; }
.local-skill-toolbar > :first-child { flex: 1; min-width: 0; }
.local-skill-toolbar :deep(.ant-select) { width: 200px; }
.local-skill-roots { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 10px 0; color: var(--site-secondary-text-color); font-size: 12px; }
.local-skill-roots small { font-size: inherit; }
.local-skill-loading { padding: 60px; text-align: center; }
.local-skill-selection { display: flex; justify-content: space-between; gap: 12px; margin: 16px 0 8px; }
.local-skill-selection > span { font-size: 12px; color: var(--site-secondary-text-color); }
.local-skill-list { max-height: 360px; overflow-y: auto; border-top: var(--light-border); }
.local-skill-row { padding: 12px 0; border-bottom: var(--light-border); }
.local-skill-row :deep(.ant-checkbox-wrapper) { display: flex; align-items: flex-start; width: 100%; }
.local-skill-row :deep(.ant-checkbox) { align-self: flex-start; margin-top: 3px; }
.local-skill-row :deep(.ant-checkbox + span) { min-width: 0; flex: 1; }
.local-skill-copy { display: block; overflow-wrap: anywhere; line-height: 1.6; }
.local-skill-copy strong { font-weight: 500; }
.local-skill-copy small { margin-left: 10px; color: var(--site-secondary-text-color); font-size: 12px; }
.local-skill-copy small.local-imported { color: var(--color-primary); }
.local-skill-description { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; color: var(--site-secondary-text-color); font-size: 12px; }
.local-skill-copy code { display: block; white-space: normal; color: var(--site-secondary-text-color); font-size: 11px; }
.local-skill-error { margin: 5px 0 0 24px; color: var(--error-color, #b4453c); font-size: 12px; line-height: 1.6; }
@media (hover: hover) and (pointer: fine) {
  .skill-card:hover { border-color: color-mix(in srgb, var(--site-text-color) 22%, transparent); }
  .skill-card:hover .card-actions { opacity: 1; pointer-events: auto; }
  .card-actions :deep(a:hover) { background: var(--gray-background); color: var(--site-text-color); }
}
@media (hover: none) { .card-actions { opacity: 1; pointer-events: auto; } }
@media (max-width: 1250px) {
  .skill-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .list-view { grid-template-columns: minmax(0, 1fr); }
  .list-view .skill-card-link { grid-template-columns: minmax(0, 1fr) minmax(140px, .8fr); }
  .list-view .card-meta { display: none; }
}
@media (max-width: 850px) {
  .catalog-header, .catalog-toolbar, .catalog-content { padding-left: 16px; padding-right: 16px; }
  .catalog-header { flex-wrap: wrap; }
  .skill-grid { grid-template-columns: minmax(0, 1fr); }
  .catalog-toolbar { flex-wrap: wrap; }
  .catalog-search { max-width: none; flex: 1; min-width: 180px; }
  .list-view .skill-card-link { display: flex; align-items: stretch; }
  .list-view .card-footer { padding-right: 0; }
}
</style>
