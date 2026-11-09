<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  Add,
  Connection,
  Search,
  Control,
  ToTop,
  ToBottom,
  Edit,
  Delete,
  Refresh,
  Tool,
  Code,
  FolderOpen,
  Plus,
  Close, Undo } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatTaskTime } from '@/utils/taskAgentPresentation'
import { formatIntegrationError } from '@/utils/taskAgentErrors'

const { t, locale } = useI18n()
const route = useRoute(), router = useRouter()
const servers = ref([]), loading = ref(true), failed = ref(false)
const search = ref(String(route.query.search || ''))
const filter = computed(() => ['enabled', 'disabled', 'stdio', 'remote'].includes(route.query.filter) ? route.query.filter : 'all')
const sort = computed(() => ['name', 'oldest'].includes(route.query.sort) ? route.query.sort : 'recent')

const togglingServerIds = reactive({})
const testingServerIds = reactive({})

const editorOpen = ref(false)
const editorLoading = ref(false)
const editorSaving = ref(false)
const editorError = ref('')
const editorConflict = ref(false)
const editingServer = ref(null)

const formState = reactive({
  server_id: '',
  expected_updated_at: '',
  name: '',
  description: '',
  enabled: true,
  transport: 'stdio',
  timeout_seconds: 30,
  command: '',
  args: [],
  cwd: '',
  savedEnvKeys: [],
  clearEnvKeys: [],
  envReplacements: {},
  newEnvRows: [],
  url: '',
  display_url: '',
  url_configured: false,
  savedHeaderKeys: [],
  clearHeaderKeys: [],
  headerReplacements: {},
  newHeaderRows: [],
})

const toolsModalOpen = ref(false)
const toolsModalLoading = ref(false)
const toolsModalFailed = ref(false)
const toolsServer = ref(null)
const toolToggling = reactive({})
const schemaTool = ref(null)

const filters = computed(() => [
  { key: 'all', label: t('workspace.taskAgentSpace.mcp_filter_all') },
  { key: 'enabled', label: t('workspace.taskAgentSpace.mcp_filter_enabled') },
  { key: 'disabled', label: t('workspace.taskAgentSpace.mcp_filter_disabled') },
  { key: 'stdio', label: 'Stdio' },
  { key: 'remote', label: t('workspace.taskAgentSpace.mcp_filter_remote') },
])

const updateQuery = patch => {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  return router.replace({ name: 'taskAgentMCP', query })
}

const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return servers.value.filter(srv => {
    if (filter.value === 'enabled' && !srv.enabled) return false
    if (filter.value === 'disabled' && srv.enabled) return false
    if (filter.value === 'stdio' && srv.transport !== 'stdio') return false
    if (filter.value === 'remote' && srv.transport === 'stdio') return false
    if (!query) return true
    const target = `${srv.name || ''} ${srv.description || ''} ${srv.command || ''} ${srv.display_url || ''}`.toLocaleLowerCase()
    return target.includes(query)
  }).sort((left, right) => sort.value === 'name'
    ? String(left.name || '').localeCompare(String(right.name || ''), locale.value)
    : ((Date.parse(right.updated_at || '') || 0) - (Date.parse(left.updated_at || '') || 0)) * (sort.value === 'oldest' ? -1 : 1) ||
      String(left.name || '').localeCompare(String(right.name || ''), locale.value))
})

let alive = true, generation = 0, editorGeneration = 0, toolsGeneration = 0, searchTimer = null
const load = async () => {
  const version = ++generation
  loading.value = true; failed.value = false
  try {
    const response = await taskAgentAPI('mcp_servers')
    if (!alive || version !== generation) return
    if (response.status !== 200 || !Array.isArray(response.data?.servers)) throw new Error()
    servers.value = response.data.servers
  } catch {
    if (alive && version === generation) failed.value = true
  } finally {
    if (alive && version === generation) loading.value = false
  }
}

const updateServerInList = updated => {
  if (!updated?.server_id) return
  const idx = servers.value.findIndex(item => item.server_id === updated.server_id)
  if (idx >= 0) servers.value[idx] = { ...servers.value[idx], ...updated }
  else servers.value.unshift(updated)
  if (toolsServer.value?.server_id === updated.server_id) {
    toolsServer.value = { ...toolsServer.value, ...updated }
  }
}

const toggleServerEnabled = async (srv, nextEnabled) => {
  if (togglingServerIds[srv.server_id]) return
  togglingServerIds[srv.server_id] = true
  try {
    const response = await taskAgentAPI('save_mcp_server', {
      server_id: srv.server_id,
      enabled: Boolean(nextEnabled),
      expected_updated_at: srv.updated_at,
    })
    if (!alive) return
    if (response.status !== 200 || !response.data?.server_id) {
      message.error(formatIntegrationError(response, t))
      if (response.status === 409) await load()
      return
    }
    updateServerInList(response.data)
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.save_failed'))
  } finally {
    delete togglingServerIds[srv.server_id]
  }
}

const runServerTest = async srv => {
  const sid = srv.server_id
  if (testingServerIds[sid]) return
  testingServerIds[sid] = true
  try {
    const response = await taskAgentAPI('test_mcp_server', { server_id: sid })
    if (!alive) return
    if (response.status !== 200 || !response.data?.server_id) {
      message.error(formatIntegrationError(response, t))
      await load()
      if (alive && toolsModalOpen.value && toolsServer.value?.server_id === sid) {
        const reqToolsGen = toolsGeneration
        try {
          const detail = await taskAgentAPI('mcp_server', { server_id: sid })
          if (alive && reqToolsGen === toolsGeneration && toolsServer.value?.server_id === sid && detail.status === 200 && detail.data?.server_id) {
            toolsServer.value = detail.data
          }
        } catch { /* ignore secondary detail refresh error */ }
      }
      return
    }
    updateServerInList(response.data)
    if (toolsModalOpen.value && toolsServer.value?.server_id === sid) {
      toolsServer.value = response.data
    }
    message.success(t('workspace.taskAgentSpace.mcp_test_succeeded', { count: response.data.tool_count || 0 }))
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.integration_error_mcp_default'))
  } finally {
    delete testingServerIds[sid]
  }
}
const resetEditorForm = srv => {
  editingServer.value = srv || null
  editorError.value = ''
  editorConflict.value = false
  formState.server_id = srv?.server_id || ''
  formState.expected_updated_at = srv?.updated_at || ''
  formState.name = srv?.name || ''
  formState.description = srv?.description || ''
  formState.enabled = srv ? Boolean(srv.enabled) : true
  formState.transport = srv?.transport || 'stdio'
  formState.timeout_seconds = srv?.timeout_seconds !== undefined ? Number(srv.timeout_seconds) : 30
  formState.command = srv?.command || ''
  formState.args = Array.isArray(srv?.args) ? [...srv.args] : []
  formState.cwd = srv?.cwd || ''
  formState.savedEnvKeys = Array.isArray(srv?.env_keys) ? [...srv.env_keys] : []
  formState.clearEnvKeys = []
  formState.envReplacements = Object.fromEntries((srv?.env_keys || []).map(k => [k, '']))
  formState.newEnvRows = []
  formState.url = ''
  formState.display_url = srv?.display_url || ''
  formState.url_configured = Boolean(srv?.url_configured)
  formState.savedHeaderKeys = Array.isArray(srv?.header_keys) ? [...srv.header_keys] : []
  formState.clearHeaderKeys = []
  formState.headerReplacements = Object.fromEntries((srv?.header_keys || []).map(k => [k, '']))
  formState.newHeaderRows = []
}

const openCreateModal = () => {
  if (editorSaving.value) return
  editorGeneration++
  editorLoading.value = false
  resetEditorForm(null)
  editorOpen.value = true
}

const closeEditorModal = () => {
  if (editorSaving.value) return
  editorGeneration++
  editorLoading.value = false
  editorOpen.value = false
}

const openEditModal = async srv => {
  if (editorSaving.value) return
  const reqGen = ++editorGeneration
  const sid = srv.server_id
  editorOpen.value = true
  editorLoading.value = true
  resetEditorForm(srv)
  try {
    const response = await taskAgentAPI('mcp_server', { server_id: sid })
    if (!alive || reqGen !== editorGeneration || !editorOpen.value || formState.server_id !== sid) return
    if (response.status === 200 && response.data?.server_id === sid) {
      resetEditorForm(response.data)
    } else {
      editorError.value = formatIntegrationError(response, t)
    }
  } catch {
    if (alive && reqGen === editorGeneration && editorOpen.value && formState.server_id === sid) {
      editorError.value = t('workspace.taskAgentSpace.load_failed')
    }
  } finally {
    if (alive && reqGen === editorGeneration) {
      editorLoading.value = false
    }
  }
}

const refreshEditorKeepDraft = async () => {
  if (!formState.server_id || editorSaving.value || editorLoading.value) return
  const reqGen = ++editorGeneration
  const sid = formState.server_id
  try {
    const response = await taskAgentAPI('mcp_server', { server_id: sid })
    if (!alive || reqGen !== editorGeneration || !editorOpen.value || formState.server_id !== sid) return
    if (response.status === 200 && response.data?.server_id === sid) {
      editingServer.value = response.data
      formState.expected_updated_at = response.data.updated_at || ''
      formState.display_url = response.data.display_url || ''
      formState.url_configured = Boolean(response.data.url_configured)
      const nextEnvKeys = Array.isArray(response.data.env_keys) ? response.data.env_keys : []
      formState.savedEnvKeys = [...nextEnvKeys]
      formState.clearEnvKeys = formState.clearEnvKeys.filter(k => nextEnvKeys.includes(k))
      for (const k of nextEnvKeys) {
        if (!(k in formState.envReplacements)) formState.envReplacements[k] = ''
      }
      const nextHdrKeys = Array.isArray(response.data.header_keys) ? response.data.header_keys : []
      formState.savedHeaderKeys = [...nextHdrKeys]
      formState.clearHeaderKeys = formState.clearHeaderKeys.filter(k => nextHdrKeys.includes(k))
      for (const k of nextHdrKeys) {
        if (!(k in formState.headerReplacements)) formState.headerReplacements[k] = ''
      }
      editorError.value = ''
      editorConflict.value = false
      updateServerInList(response.data)
    } else {
      editorError.value = formatIntegrationError(response, t)
    }
  } catch {
    if (alive && reqGen === editorGeneration) {
      editorError.value = t('workspace.taskAgentSpace.load_failed')
    }
  }
}

const pickCwdFolder = async () => {
  if (editorSaving.value || editorLoading.value) return
  const reqGen = editorGeneration
  const sid = formState.server_id
  try {
    if (typeof window?.pywebview?.api?.open_folder_dialog !== 'function') {
      message.warning(t('workspace.taskAgentSpace.project_pick_failed'))
      return
    }
    const selected = await window.pywebview.api.open_folder_dialog(formState.cwd || '')
    if (!alive || reqGen !== editorGeneration || !editorOpen.value || formState.server_id !== sid || editorSaving.value) return
    const folder = Array.isArray(selected) ? selected[0] : selected
    if (typeof folder === 'string' && folder.trim()) {
      formState.cwd = folder.trim()
    }
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.project_pick_failed'))
  }
}

const toggleClearEnvKey = key => {
  if (editorSaving.value) return
  const idx = formState.clearEnvKeys.indexOf(key)
  if (idx >= 0) formState.clearEnvKeys.splice(idx, 1)
  else {
    formState.clearEnvKeys.push(key)
    formState.envReplacements[key] = ''
  }
}

const toggleClearHeaderKey = key => {
  if (editorSaving.value) return
  const idx = formState.clearHeaderKeys.indexOf(key)
  if (idx >= 0) formState.clearHeaderKeys.splice(idx, 1)
  else {
    formState.clearHeaderKeys.push(key)
    formState.headerReplacements[key] = ''
  }
}
const submitServerEditor = async () => {
  if (editorSaving.value || editorLoading.value) return
  editorConflict.value = false
  const trimmedName = String(formState.name || '').trim()
  if (!trimmedName) {
    editorError.value = t('workspace.taskAgentSpace.integration_error_mcp_invalid_name')
    return
  }
  const rawTimeout = Number(formState.timeout_seconds)
  if (!Number.isFinite(rawTimeout) || rawTimeout < 1 || rawTimeout > 300) {
    editorError.value = t('workspace.taskAgentSpace.integration_error_mcp_invalid_timeout')
    return
  }

  const payload = {
    name: trimmedName,
    description: String(formState.description || '').trim(),
    enabled: Boolean(formState.enabled),
    transport: formState.transport,
    timeout_seconds: rawTimeout,
  }
  const targetServerId = formState.server_id
  if (targetServerId) {
    payload.server_id = targetServerId
    if (formState.expected_updated_at) payload.expected_updated_at = formState.expected_updated_at
  }

  if (formState.transport === 'stdio') {
    const trimmedCmd = String(formState.command || '').trim()
    if (!trimmedCmd) {
      editorError.value = t('workspace.taskAgentSpace.integration_error_mcp_invalid_command')
      return
    }
    payload.command = trimmedCmd
    // Preserve exact argument array, including intentional empty string arguments!
    payload.args = formState.args.map(item => String(item ?? ''))
    payload.cwd = String(formState.cwd || '').trim()

    const activeEnvNames = new Set(formState.savedEnvKeys.filter(k => !formState.clearEnvKeys.includes(k)))
    const envUpdates = {}
    for (const key of formState.savedEnvKeys) {
      if (formState.clearEnvKeys.includes(key)) continue
      const val = String(formState.envReplacements[key] || '')
      if (val.trim()) envUpdates[key] = val
    }
    for (const row of formState.newEnvRows) {
      const k = String(row.key || '').trim()
      const v = String(row.value || '')
      if (!k && !v.trim()) continue
      if (!k || !v.trim()) {
        editorError.value = t('workspace.taskAgentSpace.integration_error_mcp_invalid_env')
        return
      }
      if (activeEnvNames.has(k)) {
        editorError.value = t('workspace.taskAgentSpace.mcp_duplicate_env_key', { key: k })
        return
      }
      activeEnvNames.add(k)
      envUpdates[k] = v
    }
    if (Object.keys(envUpdates).length > 0) payload.env = envUpdates
    if (formState.clearEnvKeys.length > 0) payload.clear_env_keys = [...formState.clearEnvKeys]
  } else {
    const trimmedUrl = String(formState.url || '').trim()
    if (!trimmedUrl && !formState.url_configured) {
      editorError.value = t('workspace.taskAgentSpace.integration_error_mcp_invalid_url')
      return
    }
    if (trimmedUrl) payload.url = trimmedUrl

    const clearedLower = new Set(formState.clearHeaderKeys.map(k => k.toLowerCase()))
    const activeHeaderLower = new Set(
      formState.savedHeaderKeys.filter(k => !clearedLower.has(k.toLowerCase())).map(k => k.toLowerCase()),
    )
    const headerUpdates = {}
    for (const key of formState.savedHeaderKeys) {
      if (clearedLower.has(key.toLowerCase())) continue
      const val = String(formState.headerReplacements[key] || '')
      if (val.trim()) headerUpdates[key] = val
    }
    for (const row of formState.newHeaderRows) {
      const k = String(row.key || '').trim()
      const v = String(row.value || '')
      if (!k && !v.trim()) continue
      if (!k || !v.trim()) {
        editorError.value = t('workspace.taskAgentSpace.integration_error_mcp_invalid_header')
        return
      }
      const lower = k.toLowerCase()
      if (activeHeaderLower.has(lower)) {
        editorError.value = t('workspace.taskAgentSpace.mcp_duplicate_header_key', { key: k })
        return
      }
      activeHeaderLower.add(lower)
      headerUpdates[k] = v
    }
    if (Object.keys(headerUpdates).length > 0) payload.headers = headerUpdates
    if (formState.clearHeaderKeys.length > 0) payload.clear_header_keys = [...formState.clearHeaderKeys]
  }

  const reqGen = ++editorGeneration
  editorSaving.value = true
  editorError.value = ''
  try {
    const response = await taskAgentAPI('save_mcp_server', payload)
    if (!alive || reqGen !== editorGeneration || !editorOpen.value || formState.server_id !== targetServerId) return
    if (response.status !== 200 || !response.data?.server_id) {
      editorError.value = formatIntegrationError(response, t)
      editorConflict.value = response.status === 409
      if (response.status === 409) await load()
      return
    }
    updateServerInList(response.data)
    editorOpen.value = false
    message.success(t('workspace.taskAgentSpace.mcp_server_saved'))
  } catch {
    if (alive && reqGen === editorGeneration && editorOpen.value && formState.server_id === targetServerId) {
      editorError.value = t('workspace.taskAgentSpace.save_failed')
    }
  } finally {
    if (alive && reqGen === editorGeneration) {
      editorSaving.value = false
    }
  }
}

const confirmDeleteServer = srv => {
  Modal.confirm({
    title: t('workspace.taskAgentSpace.mcp_delete_title', { name: srv.name }),
    content: t('workspace.taskAgentSpace.mcp_delete_confirm', { name: srv.name }),
    okText: t('workspace.taskAgentSpace.mcp_delete_action'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      try {
        const response = await taskAgentAPI('delete_mcp_server', {
          server_id: srv.server_id,
          expected_updated_at: srv.updated_at,
        })
        if (response.status !== 200) {
          if (alive) message.error(formatIntegrationError(response, t))
          if (alive && (response.status === 409 || response.status === 404)) await load()
          return Promise.reject(new Error('delete_failed'))
        }
        if (alive) {
          servers.value = servers.value.filter(item => item.server_id !== srv.server_id)
          if (toolsServer.value?.server_id === srv.server_id) {
            toolsGeneration++
            toolsModalOpen.value = false
          }
          message.success(t('workspace.taskAgentSpace.mcp_server_deleted'))
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

const closeToolsModal = () => {
  toolsGeneration++
  toolsModalLoading.value = false
  toolsModalOpen.value = false
}

const loadToolsModalServer = async sid => {
  const reqGen = ++toolsGeneration
  toolsModalLoading.value = true
  toolsModalFailed.value = false
  try {
    const response = await taskAgentAPI('mcp_server', { server_id: sid })
    if (!alive || reqGen !== toolsGeneration || !toolsModalOpen.value || toolsServer.value?.server_id !== sid) return
    if (response.status === 200 && response.data?.server_id === sid) {
      toolsServer.value = response.data
      updateServerInList(response.data)
    } else {
      toolsModalFailed.value = true
    }
  } catch {
    if (alive && reqGen === toolsGeneration && toolsModalOpen.value && toolsServer.value?.server_id === sid) {
      toolsModalFailed.value = true
    }
  } finally {
    if (alive && reqGen === toolsGeneration) {
      toolsModalLoading.value = false
    }
  }
}

const openToolsModal = async srv => {
  toolsServer.value = srv
  schemaTool.value = null
  toolsModalOpen.value = true
  await loadToolsModalServer(srv.server_id)
}

const toggleToolEnabled = async (tool, nextEnabled) => {
  if (!toolsServer.value) return
  const sid = toolsServer.value.server_id
  const reqGen = toolsGeneration
  const key = `${sid}:${tool.name}`
  if (toolToggling[key]) return
  toolToggling[key] = true
  try {
    const response = await taskAgentAPI('set_mcp_tool_enabled', {
      server_id: sid,
      tool_name: tool.name,
      enabled: Boolean(nextEnabled),
      expected_updated_at: toolsServer.value.updated_at,
    })
    if (!alive) return
    if (response.status !== 200 || !response.data?.server_id) {
      message.error(formatIntegrationError(response, t))
      if (response.status === 409 && reqGen === toolsGeneration && toolsModalOpen.value && toolsServer.value?.server_id === sid) {
        await loadToolsModalServer(sid)
      }
      return
    }
    updateServerInList(response.data)
    if (reqGen === toolsGeneration && toolsModalOpen.value && toolsServer.value?.server_id === sid) {
      toolsServer.value = response.data
    }
  } catch {
    if (alive) message.error(t('workspace.taskAgentSpace.save_failed'))
  } finally {
    delete toolToggling[key]
  }
}

const transportLabel = transport => {
  if (transport === 'streamable_http') return 'Streamable HTTP'
  if (transport === 'sse') return 'SSE'
  return 'Stdio'
}

const pastTestStatusLabel = srv => {
  if (srv.discovery_stale || srv.last_test_status === 'stale') {
    return t('workspace.taskAgentSpace.mcp_test_status_stale')
  }
  if (srv.last_test_status === 'ok') {
    return t('workspace.taskAgentSpace.mcp_test_status_ok')
  }
  if (srv.last_test_status === 'error') {
    return t('workspace.taskAgentSpace.mcp_test_status_error')
  }
  return t('workspace.taskAgentSpace.mcp_test_status_untested')
}

const pastTestStatusClass = srv => {
  if (srv.discovery_stale || srv.last_test_status === 'stale') return 'stale'
  if (srv.last_test_status === 'ok') return 'ok'
  if (srv.last_test_status === 'error') return 'error'
  return 'untested'
}

const localizedLastError = srv => {
  const code = srv?.last_error?.code
  if (!code) return ''
  return formatIntegrationError({ status: 400, data: { integration_error: { kind: 'mcp', code } } }, t)
}

watch(search, value => {
  clearTimeout(searchTimer)
  if (value === String(route.query.search || '')) return
  searchTimer = setTimeout(() => updateQuery({ search: value.trim() || undefined }), 200)
})
watch(() => route.query.search, value => { clearTimeout(searchTimer); search.value = String(value || '') })
onMounted(load)
onBeforeUnmount(() => { alive = false; editorGeneration++; toolsGeneration++; clearTimeout(searchTimer) })
</script>
<template>
  <main class="mcp-catalog">
    <header class="catalog-header">
      <div class="catalog-title">
        <h1>{{ t('workspace.taskAgentSpace.mcp_title') }}</h1>
        <span>{{ t('workspace.taskAgentSpace.profile_total', { count: servers.length }) }}</span>
      </div>
      <div class="header-actions">
        <IconButton type="primary" @click="openCreateModal" :text="t('workspace.taskAgentSpace.mcp_add_server')"><template #icon><Add /></template></IconButton>
      </div>
    </header>

    <div class="catalog-toolbar">
      <a-input
        v-model:value="search"
        allow-clear
        class="catalog-search"
        :aria-label="t('workspace.taskAgentSpace.mcp_search')"
        :placeholder="t('workspace.taskAgentSpace.mcp_search')"
      >
        <template #prefix><Search /></template>
      </a-input>
      <div class="toolbar-actions">
        <a-dropdown :trigger="['click']">
          <IconButton
              type="text"
              class="toolbar-icon-btn"
              :aria-label="`${t('workspace.taskAgentSpace.profile_filter')}: ${filters.find(f => f.key === filter)?.label || t('workspace.taskAgentSpace.mcp_filter_all')}`"
             :text="`${t('workspace.taskAgentSpace.profile_filter')}: ${filters.find(f => f.key === filter)?.label || t('workspace.taskAgentSpace.mcp_filter_all')}`"><template #icon><Control /></template></IconButton>
          <template #overlay>
            <a-menu :selected-keys="[filter]" @click="({ key }) => updateQuery({ filter: key === 'all' ? undefined : key })">
              <a-menu-item v-for="item in filters" :key="item.key">{{ item.label }}</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
        <a-dropdown :trigger="['click']">
          <IconButton
              type="text"
              class="toolbar-icon-btn"
              :aria-label="t('workspace.taskAgentSpace.profile_sort_' + sort)"
             :text="t('workspace.taskAgentSpace.profile_sort_' + sort)"><template #icon><ToTop v-if="sort === 'oldest'" /><ToBottom v-else /></template></IconButton>
          <template #overlay>
            <a-menu :selected-keys="[sort]" @click="({ key }) => updateQuery({ sort: key === 'recent' ? undefined : key })">
              <a-menu-item key="recent">{{ t('workspace.taskAgentSpace.profile_sort_recent') }}</a-menu-item>
              <a-menu-item key="oldest">{{ t('workspace.taskAgentSpace.profile_sort_oldest') }}</a-menu-item>
              <a-menu-item key="name">{{ t('workspace.taskAgentSpace.profile_sort_name') }}</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </div>

    <div class="catalog-content">
      <div v-if="loading" class="catalog-loading"><a-spin size="large" /></div>
      <div v-else-if="failed" class="catalog-empty">
        <a-empty :description="t('workspace.taskAgentSpace.load_failed')">
          <IconButton type="primary" @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
        </a-empty>
      </div>
      <div v-else-if="filtered.length === 0" class="catalog-empty">
        <a-empty :description="servers.length ? t('workspace.taskAgentSpace.mcp_no_results') : t('workspace.taskAgentSpace.mcp_empty')">
          <a-space>
            <IconButton v-if="search || filter !== 'all'" @click="search = ''; updateQuery({ search: undefined, filter: undefined })" :text="t('workspace.taskAgentSpace.profile_clear_filters')"><template #icon><Close /></template></IconButton>
            <a-button type="primary" @click="openCreateModal">
              <template #icon><Add /></template>
              {{ t('workspace.taskAgentSpace.mcp_add_server') }}
            </a-button>
          </a-space>
        </a-empty>
      </div>
      <template v-else>
        <p class="catalog-summary">{{ t('workspace.taskAgentSpace.mcp_showing', { count: filtered.length }) }}</p>
        <div class="server-grid">
          <article v-for="srv in filtered" :key="srv.server_id" class="server-card" :class="{ 'is-disabled': !srv.enabled }">
            <div class="card-top">
              <div class="server-avatar"><Connection size="20" /></div>
              <div class="card-copy">
                <div class="card-heading">
                  <h2>{{ srv.name }}</h2>
                  <span class="transport-badge">{{ transportLabel(srv.transport) }}</span>
                  <span class="test-pill" :class="pastTestStatusClass(srv)">{{ pastTestStatusLabel(srv) }}</span>
                </div>
                <p class="server-description">{{ srv.description || t('workspace.taskAgentSpace.profile_no_description') }}</p>
              </div>
            </div>

            <div class="endpoint-box">
              <code v-if="srv.transport === 'stdio'">{{ srv.command }} {{ (srv.args || []).join(' ') }}</code>
              <code v-else>{{ srv.display_url || '-' }}</code>
            </div>

            <div class="card-meta">
              <span><Tool />{{ t('workspace.taskAgentSpace.mcp_tool_summary', { enabled: srv.enabled_tool_count || 0, total: srv.tool_count || 0 }) }}</span>
              <span v-if="srv.transport === 'stdio' && srv.env_keys?.length">
                {{ t('workspace.taskAgentSpace.mcp_saved_env_count', { count: srv.env_keys.length }) }}
              </span>
              <span v-if="srv.transport !== 'stdio' && srv.header_keys?.length">
                {{ t('workspace.taskAgentSpace.mcp_saved_header_count', { count: srv.header_keys.length }) }}
              </span>
              <span v-if="srv.last_test_at">
                {{ t('workspace.taskAgentSpace.mcp_last_test_time', { time: formatTaskTime(srv.last_test_at, locale) }) }}
              </span>
            </div>

            <p v-if="srv.discovery_stale" class="stale-hint">{{ t('workspace.taskAgentSpace.mcp_stale_hint') }}</p>
            <p v-else-if="srv.last_test_status === 'error' && srv.last_error" class="error-hint">{{ localizedLastError(srv) }}</p>

            <div class="card-actions" @click.stop>
              <a-switch
                size="small"
                :checked="srv.enabled"
                :loading="Boolean(togglingServerIds[srv.server_id])"
                :aria-label="t('workspace.taskAgentSpace.mcp_toggle_label', { name: srv.name })"
                @change="checked => toggleServerEnabled(srv, checked)"
              />
              <IconButton
                  type="text"
                  size="small"
                  :loading="Boolean(testingServerIds[srv.server_id])"
                  :aria-label="t('workspace.taskAgentSpace.mcp_test_server_name', { name: srv.name })"
                  @click="runServerTest(srv)"
                 :text="t('workspace.taskAgentSpace.mcp_test_server_name', { name: srv.name })"><template #icon><Refresh /></template></IconButton>
              <IconButton
                  type="text"
                  size="small"
                  :aria-label="t('workspace.taskAgentSpace.mcp_view_tools_name', { name: srv.name })"
                  @click="openToolsModal(srv)"
                 :text="t('workspace.taskAgentSpace.mcp_view_tools_name', { name: srv.name })"><template #icon><Tool /></template></IconButton>
              <IconButton
                  type="text"
                  size="small"
                  :aria-label="t('workspace.taskAgentSpace.mcp_edit_server_name', { name: srv.name })"
                  @click="openEditModal(srv)"
                 :text="t('workspace.taskAgentSpace.mcp_edit_server_name', { name: srv.name })"><template #icon><Edit /></template></IconButton>
              <IconButton
                  type="text"
                  size="small"
                  danger
                  :aria-label="t('workspace.taskAgentSpace.mcp_delete_server_name', { name: srv.name })"
                  @click="confirmDeleteServer(srv)"
                 :text="t('workspace.taskAgentSpace.mcp_delete_server_name', { name: srv.name })"><template #icon><Delete /></template></IconButton>
            </div>
          </article>
        </div>
      </template>
    </div>
    <a-modal
      :open="editorOpen"
      :width="660"
      :title="editingServer ? t('workspace.taskAgentSpace.mcp_edit_server') : t('workspace.taskAgentSpace.mcp_add_server')"
      :confirm-loading="editorSaving"
      :closable="!editorSaving"
      :mask-closable="!editorSaving"
      :keyboard="!editorSaving"
      :cancel-button-props="{ disabled: editorSaving }"
      :ok-text="t('workspace.taskAgentSpace.mcp_save_server')"
      :cancel-text="t('common.cancel')"
      @cancel="closeEditorModal"
      @ok="submitServerEditor"
    >
      <div v-if="editorLoading" class="modal-loading"><a-spin /></div>
      <a-form v-else layout="vertical" class="mcp-editor-form">
        <a-alert v-if="editorError" type="error" show-icon class="editor-alert" :message="editorError">
          <template v-if="editorConflict && formState.server_id" #action>
            <IconButton size="small" :disabled="editorSaving" @click="refreshEditorKeepDraft" :text="t('workspace.taskAgentSpace.mcp_refresh_metadata')"><template #icon><Refresh /></template></IconButton>
          </template>
        </a-alert>

        <div class="form-row-two">
          <a-form-item :label="t('workspace.taskAgentSpace.mcp_server_name')" required>
            <a-input
              v-model:value="formState.name"
              :disabled="editorSaving"
              :aria-label="t('workspace.taskAgentSpace.mcp_server_name')"
              :placeholder="t('workspace.taskAgentSpace.mcp_server_name_placeholder')"
              :maxlength="160"
            />
          </a-form-item>
          <a-form-item :label="t('workspace.taskAgentSpace.mcp_transport')" required>
            <a-select
              v-model:value="formState.transport"
              :disabled="editorSaving"
              :aria-label="t('workspace.taskAgentSpace.mcp_transport')"
              :options="[
                { value: 'stdio', label: 'Stdio' },
                { value: 'streamable_http', label: 'Streamable HTTP' },
                { value: 'sse', label: 'SSE' },
              ]"
            />
          </a-form-item>
        </div>

        <a-form-item :label="t('workspace.taskAgentSpace.mcp_server_description')">
          <a-textarea
            v-model:value="formState.description"
            :disabled="editorSaving"
            :aria-label="t('workspace.taskAgentSpace.mcp_server_description')"
            :rows="2"
            :maxlength="2000"
          />
        </a-form-item>

        <div class="form-row-two">
          <a-form-item :label="t('workspace.taskAgentSpace.mcp_timeout_seconds')">
            <a-input-number
              v-model:value="formState.timeout_seconds"
              :disabled="editorSaving"
              :aria-label="t('workspace.taskAgentSpace.mcp_timeout_seconds')"
              :min="1"
              :max="300"
              style="width: 100%"
            />
          </a-form-item>
          <a-form-item :label="t('workspace.taskAgentSpace.mcp_server_enabled')">
            <div class="switch-inline">
              <a-switch v-model:checked="formState.enabled" :disabled="editorSaving" :aria-label="t('workspace.taskAgentSpace.mcp_server_enabled')" />
              <span>{{ formState.enabled ? t('workspace.taskAgentSpace.skill_status_enabled') : t('workspace.taskAgentSpace.skill_status_disabled') }}</span>
            </div>
          </a-form-item>
        </div>

        <template v-if="formState.transport === 'stdio'">
          <a-form-item :label="t('workspace.taskAgentSpace.mcp_stdio_command')" required>
            <a-input
              v-model:value="formState.command"
              :disabled="editorSaving"
              :aria-label="t('workspace.taskAgentSpace.mcp_stdio_command')"
              placeholder="npx, uvx, python..."
            />
          </a-form-item>

          <a-form-item :label="t('workspace.taskAgentSpace.mcp_stdio_args')">
            <div class="structured-list">
              <div v-for="(_, idx) in formState.args" :key="idx" class="structured-row">
                <a-input
                  v-model:value="formState.args[idx]"
                  :disabled="editorSaving"
                  :aria-label="`${t('workspace.taskAgentSpace.mcp_stdio_args')} ${idx + 1}`"
                  :placeholder="t('workspace.taskAgentSpace.mcp_arg_placeholder')"
                />
                <IconButton type="text" danger :disabled="editorSaving" :aria-label="t('workspace.taskAgentSpace.mcp_remove_item')" @click="formState.args.splice(idx, 1)" :text="t('workspace.taskAgentSpace.mcp_remove_item')"><template #icon><Close /></template></IconButton>
              </div>
              <IconButton size="small" type="dashed" :disabled="editorSaving" @click="formState.args.push('')" :text="t('workspace.taskAgentSpace.mcp_add_arg')"><template #icon><Plus /></template></IconButton>
            </div>
          </a-form-item>

          <a-form-item :label="t('workspace.taskAgentSpace.mcp_stdio_cwd')">
            <div class="structured-row">
              <a-input
                v-model:value="formState.cwd"
                :disabled="editorSaving"
                :aria-label="t('workspace.taskAgentSpace.mcp_stdio_cwd')"
                :placeholder="t('workspace.taskAgentSpace.mcp_cwd_placeholder')"
              />
              <IconButton :disabled="editorSaving" @click="pickCwdFolder" :text="t('workspace.taskAgentSpace.skill_pick_folder')"><template #icon><FolderOpen /></template></IconButton>
            </div>
          </a-form-item>

          <a-form-item :label="t('workspace.taskAgentSpace.mcp_stdio_env')">
            <p class="secret-help">{{ t('workspace.taskAgentSpace.mcp_secret_preserve_hint') }}</p>
            <div class="structured-list">
              <div
                v-for="key in formState.savedEnvKeys"
                :key="key"
                class="structured-row saved-secret-row"
                :class="{ 'is-removed': formState.clearEnvKeys.includes(key) }"
              >
                <span class="secret-key-chip">{{ key }}</span>
                <a-input-password
                  v-model:value="formState.envReplacements[key]"
                  :disabled="editorSaving || formState.clearEnvKeys.includes(key)"
                  :aria-label="t('workspace.taskAgentSpace.mcp_replace_secret_for', { key })"
                  :placeholder="formState.clearEnvKeys.includes(key) ? t('workspace.taskAgentSpace.mcp_secret_marked_remove') : t('workspace.taskAgentSpace.mcp_secret_saved_placeholder')"
                />
                <IconButton
                  size="small"
                  :disabled="editorSaving"
                  :danger="!formState.clearEnvKeys.includes(key)"
                  @click="toggleClearEnvKey(key)"
                 :text="formState.clearEnvKeys.includes(key) ? t('workspace.taskAgentSpace.mcp_undo_remove') : t('workspace.taskAgentSpace.mcp_remove_secret')"><template #icon><Undo v-if="formState.clearEnvKeys.includes(key)" /><Delete v-else /></template></IconButton>
              </div>

              <div v-for="(row, idx) in formState.newEnvRows" :key="'new-env-' + idx" class="structured-row">
                <a-input
                  v-model:value="row.key"
                  :disabled="editorSaving"
                  class="key-input"
                  :aria-label="`${t('workspace.taskAgentSpace.mcp_env_key')} ${idx + 1}`"
                  :placeholder="t('workspace.taskAgentSpace.mcp_env_key')"
                />
                <a-input-password
                  v-model:value="row.value"
                  :disabled="editorSaving"
                  :aria-label="`${t('workspace.taskAgentSpace.mcp_env_value')} ${idx + 1}`"
                  :placeholder="t('workspace.taskAgentSpace.mcp_env_value')"
                />
                <IconButton type="text" danger :disabled="editorSaving" :aria-label="t('workspace.taskAgentSpace.mcp_remove_item')" @click="formState.newEnvRows.splice(idx, 1)" :text="t('workspace.taskAgentSpace.mcp_remove_item')"><template #icon><Close /></template></IconButton>
              </div>

              <IconButton size="small" type="dashed" :disabled="editorSaving" @click="formState.newEnvRows.push({ key: '', value: '' })" :text="t('workspace.taskAgentSpace.mcp_add_env')"><template #icon><Plus /></template></IconButton>
            </div>
          </a-form-item>
        </template>

        <template v-else>
          <a-form-item :label="t('workspace.taskAgentSpace.mcp_remote_url')" :required="!formState.url_configured">
            <p v-if="formState.url_configured && formState.display_url" class="secret-help">
              {{ t('workspace.taskAgentSpace.mcp_saved_url_hint', { url: formState.display_url }) }}
            </p>
            <a-input
              v-model:value="formState.url"
              :disabled="editorSaving"
              :aria-label="t('workspace.taskAgentSpace.mcp_remote_url')"
              :placeholder="formState.url_configured ? t('workspace.taskAgentSpace.mcp_url_preserve_placeholder') : 'https://example.com/mcp'"
            />
          </a-form-item>

          <a-form-item :label="t('workspace.taskAgentSpace.mcp_remote_headers')">
            <p class="secret-help">{{ t('workspace.taskAgentSpace.mcp_secret_preserve_hint') }}</p>
            <div class="structured-list">
              <div
                v-for="key in formState.savedHeaderKeys"
                :key="key"
                class="structured-row saved-secret-row"
                :class="{ 'is-removed': formState.clearHeaderKeys.includes(key) }"
              >
                <span class="secret-key-chip">{{ key }}</span>
                <a-input-password
                  v-model:value="formState.headerReplacements[key]"
                  :disabled="editorSaving || formState.clearHeaderKeys.includes(key)"
                  :aria-label="t('workspace.taskAgentSpace.mcp_replace_secret_for', { key })"
                  :placeholder="formState.clearHeaderKeys.includes(key) ? t('workspace.taskAgentSpace.mcp_secret_marked_remove') : t('workspace.taskAgentSpace.mcp_secret_saved_placeholder')"
                />
                <IconButton
                  size="small"
                  :disabled="editorSaving"
                  :danger="!formState.clearHeaderKeys.includes(key)"
                  @click="toggleClearHeaderKey(key)"
                 :text="formState.clearHeaderKeys.includes(key) ? t('workspace.taskAgentSpace.mcp_undo_remove') : t('workspace.taskAgentSpace.mcp_remove_secret')"><template #icon><Undo v-if="formState.clearHeaderKeys.includes(key)" /><Delete v-else /></template></IconButton>
              </div>

              <div v-for="(row, idx) in formState.newHeaderRows" :key="'new-hdr-' + idx" class="structured-row">
                <a-input
                  v-model:value="row.key"
                  :disabled="editorSaving"
                  class="key-input"
                  :aria-label="`${t('workspace.taskAgentSpace.mcp_header_key')} ${idx + 1}`"
                  :placeholder="t('workspace.taskAgentSpace.mcp_header_key')"
                />
                <a-input-password
                  v-model:value="row.value"
                  :disabled="editorSaving"
                  :aria-label="`${t('workspace.taskAgentSpace.mcp_header_value')} ${idx + 1}`"
                  :placeholder="t('workspace.taskAgentSpace.mcp_header_value')"
                />
                <IconButton type="text" danger :disabled="editorSaving" :aria-label="t('workspace.taskAgentSpace.mcp_remove_item')" @click="formState.newHeaderRows.splice(idx, 1)" :text="t('workspace.taskAgentSpace.mcp_remove_item')"><template #icon><Close /></template></IconButton>
              </div>

              <IconButton size="small" type="dashed" :disabled="editorSaving" @click="formState.newHeaderRows.push({ key: '', value: '' })" :text="t('workspace.taskAgentSpace.mcp_add_header')"><template #icon><Plus /></template></IconButton>
            </div>
          </a-form-item>
        </template>
      </a-form>
    </a-modal>
    <a-modal
      :open="toolsModalOpen"
      :width="760"
      :footer="null"
      :title="t('workspace.taskAgentSpace.mcp_tools_modal_title', { name: toolsServer?.name || '' })"
      @cancel="closeToolsModal"
    >
      <div v-if="toolsModalLoading" class="modal-loading"><a-spin /></div>
      <div v-else-if="toolsModalFailed" class="modal-loading">
        <a-empty :description="t('workspace.taskAgentSpace.load_failed')">
          <IconButton v-if="toolsServer?.server_id" type="primary" @click="loadToolsModalServer(toolsServer.server_id)" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
        </a-empty>
      </div>
      <div v-else-if="toolsServer" class="tools-modal-body">
        <div class="tools-modal-Banner">
          <div>
            <span class="test-pill" :class="pastTestStatusClass(toolsServer)">{{ pastTestStatusLabel(toolsServer) }}</span>
            <span v-if="toolsServer.last_test_at" class="banner-time">
              {{ t('workspace.taskAgentSpace.mcp_last_test_time', { time: formatTaskTime(toolsServer.last_test_at, locale) }) }}
            </span>
          </div>
          <IconButton
            size="small"
            type="primary"
            :loading="Boolean(testingServerIds[toolsServer.server_id])"
            @click="runServerTest(toolsServer)"
           :text="t('workspace.taskAgentSpace.mcp_test_discover')"><template #icon><Refresh /></template></IconButton>
        </div>

        <a-alert
          v-if="toolsServer.discovery_stale"
          type="warning"
          show-icon
          class="tools-alert"
          :message="t('workspace.taskAgentSpace.mcp_stale_hint')"
        />

        <div v-if="!toolsServer.tools?.length" class="modal-loading">
          <a-empty :description="t('workspace.taskAgentSpace.mcp_no_tools_discovered')" />
        </div>
        <div v-else class="discovered-tools-list">
          <div v-for="tool in toolsServer.tools" :key="tool.name" class="discovered-tool-item">
            <div class="tool-row-main">
              <div class="tool-copy">
                <div class="tool-title-row">
                  <strong>{{ tool.title || tool.name }}</strong>
                  <code v-if="tool.title && tool.title !== tool.name">{{ tool.name }}</code>
                  <code v-else>{{ tool.name }}</code>
                </div>
                <p v-if="tool.description">{{ tool.description }}</p>
              </div>
              <div class="tool-row-controls">
                <IconButton
                    size="small"
                    type="text"
                    :aria-label="t('workspace.taskAgentSpace.mcp_view_schema')"
                    @click="schemaTool = schemaTool?.name === tool.name ? null : tool"
                   :text="t('workspace.taskAgentSpace.mcp_view_schema')"><template #icon><Code /></template></IconButton>
                <a-switch
                  size="small"
                  :checked="tool.enabled"
                  :loading="Boolean(toolToggling[`${toolsServer.server_id}:${tool.name}`])"
                  :aria-label="t('workspace.taskAgentSpace.mcp_toggle_tool_label', { name: tool.name })"
                  @change="checked => toggleToolEnabled(tool, checked)"
                />
              </div>
            </div>
            <pre v-if="schemaTool?.name === tool.name" class="schema-pre">{{ JSON.stringify(tool.input_schema || {}, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </a-modal>
  </main>
</template>

<style scoped>
.mcp-catalog { display: flex; flex-direction: column; min-height: 100%; background: var(--gray-background); color: var(--site-text-color); }
.catalog-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 24px 14px; background: var(--component-background); border-bottom: var(--light-border); }
.catalog-title { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
.header-actions { display: flex; align-items: center; gap: 10px; }
h1 { margin: 0; font-size: 20px; font-weight: 600; line-height: 1.3; }
.catalog-title span, .catalog-summary { color: var(--site-secondary-text-color); font-size: 12px; }
.catalog-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 24px 0; max-width: 1560px; width: 100%; margin: 0 auto; }
.catalog-search { max-width: 340px; }
.toolbar-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
:deep(.toolbar-icon-btn) { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; padding: 0; color: var(--site-secondary-text-color); border-radius: 6px; }
.catalog-content { flex: 1; max-width: 1560px; width: 100%; margin: 0 auto; padding: 12px 24px 32px; }
.catalog-summary { margin: 0 0 8px; }
.server-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.server-card { position: relative; display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border: 1px solid color-mix(in srgb, var(--site-text-color) 7%, transparent); border-radius: 8px; background: var(--component-background); min-width: 0; }
.server-card.is-disabled { opacity: 0.78; }
.card-top { display: flex; align-items: flex-start; gap: 11px; min-width: 0; }
.server-avatar { width: 40px; height: 40px; flex: 0 0 40px; display: flex; align-items: center; justify-content: center; background: color-mix(in srgb, var(--color-primary) 8%, var(--component-background)); border: var(--light-border); color: color-mix(in srgb, var(--color-primary) 72%, var(--site-text-color)); border-radius: 7px; }
.card-copy { min-width: 0; flex: 1; }
.card-heading { display: flex; align-items: center; gap: 6px; padding-right: 148px; flex-wrap: wrap; }
h2 { margin: 0; font-size: 14px; font-weight: 600; line-height: 1.5; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.transport-badge { padding: 1px 6px; border-radius: 4px; background: var(--gray-background); color: var(--site-secondary-text-color); font-size: 11px; }
.test-pill { padding: 1px 6px; border-radius: 4px; font-size: 11px; }
.test-pill.ok { color: #2f855a; background: color-mix(in srgb, #2f855a 12%, transparent); }
.test-pill.stale { color: #b7791f; background: color-mix(in srgb, #b7791f 14%, transparent); }
.test-pill.error { color: #c53030; background: color-mix(in srgb, #c53030 12%, transparent); }
.test-pill.untested { color: var(--site-secondary-text-color); background: var(--gray-background); }
.server-description { margin: 4px 0 0; color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.65; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; overflow-wrap: anywhere; }
.endpoint-box { padding: 6px 10px; border-radius: 5px; background: var(--gray-background); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.endpoint-box code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; color: var(--site-text-color); }
.card-meta { display: flex; flex-wrap: wrap; gap: 12px; margin-top: auto; color: var(--site-secondary-text-color); font-size: 11px; }
.card-meta span { display: inline-flex; align-items: center; gap: 4px; }
.card-meta :deep(svg) { width: 12px; height: 12px; }
.stale-hint { margin: 0; font-size: 11.5px; color: #b7791f; }
.error-hint { margin: 0; font-size: 11.5px; color: #c53030; }
.card-actions { position: absolute; top: 10px; right: 10px; display: flex; align-items: center; gap: 3px; padding: 2px 4px; border-radius: 5px; background: var(--component-background); }
.card-actions :deep(.ant-btn) { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; padding: 0; color: var(--site-secondary-text-color); border-radius: 4px; }
.card-actions :deep(.ant-btn-dangerous) { color: #c53030; }
.card-actions :deep(svg) { width: 14px; height: 14px; }
.catalog-loading, .catalog-empty, .modal-loading { padding: 64px 16px; text-align: center; }
.editor-alert, .tools-alert { margin-bottom: 14px; }
.form-row-two { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 12px; }
.switch-inline { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; }
.structured-list { display: flex; flex-direction: column; gap: 8px; }
.structured-row { display: flex; align-items: center; gap: 8px; }
.saved-secret-row.is-removed { opacity: 0.65; }
.secret-key-chip { display: inline-flex; align-items: center; padding: 4px 8px; border: var(--light-border); border-radius: 4px; background: var(--gray-background); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; min-width: 120px; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.key-input { max-width: 180px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.secret-help { margin: 0 0 8px; font-size: 12px; color: var(--site-secondary-text-color); line-height: 1.6; overflow-wrap: anywhere; }
.tools-modal-Banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: var(--light-border); }
.banner-time { margin-left: 8px; font-size: 12px; color: var(--site-secondary-text-color); }
.discovered-tools-list { display: flex; flex-direction: column; gap: 8px; max-height: 480px; overflow: auto; }
.discovered-tool-item { padding: 10px 12px; border: var(--light-border); border-radius: 6px; background: var(--component-background); }
.tool-row-main { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.tool-copy { min-width: 0; flex: 1; }
.tool-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tool-title-row code { padding: 1px 5px; border-radius: 4px; background: var(--gray-background); font-size: 11px; }
.tool-copy p { margin: 4px 0 0; font-size: 12px; color: var(--site-secondary-text-color); line-height: 1.6; overflow-wrap: anywhere; }
.tool-row-controls { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.schema-pre { margin: 10px 0 0; padding: 10px; border: var(--light-border); border-radius: 5px; background: var(--gray-background); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11.5px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 260px; overflow: auto; }
@media (hover: hover) and (pointer: fine) {
  .server-card:hover { border-color: color-mix(in srgb, var(--site-text-color) 22%, transparent); }
  .card-actions :deep(.ant-btn:not(.ant-btn-dangerous):hover) { background: var(--gray-background); color: var(--site-text-color); }
}
@media (max-width: 960px) {
  .server-grid { grid-template-columns: minmax(0, 1fr); }
  .form-row-two { grid-template-columns: minmax(0, 1fr); }
  .catalog-header, .catalog-toolbar, .catalog-content { padding-left: 16px; padding-right: 16px; }
}
@media (max-width: 560px) {
  .card-heading { padding-right: 0; }
  .card-actions { position: static; justify-content: flex-end; padding: 4px 0 0; }
}
</style>
