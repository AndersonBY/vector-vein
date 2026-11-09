<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import { Left, BookOpen, Save, Delete, DocDetail, Refresh, FolderOpen } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatTaskTime } from '@/utils/taskAgentPresentation'
import { formatIntegrationError, extractSkillDiagnostics } from '@/utils/taskAgentErrors'
import { fileSize } from '@/utils/taskAgentTimeline'

const DEFAULT_SKILL_MD = `---
name: my-custom-skill
description: Explain when the Agent should activate this skill and what it provides.
---

# My Custom Skill

Provide step-by-step instructions, conventions, and references to bundled files here.
`

const route = useRoute(), router = useRouter()
const { t, locale } = useI18n()
const creating = computed(() => route.name === 'taskAgentSkillCreate')
const requestedVersion = computed(() => {
  const v = Number.parseInt(route.query.version, 10)
  return Number.isInteger(v) && v > 0 ? v : undefined
})
const isHistoricalInspection = computed(() => !creating.value && requestedVersion.value !== undefined)
const listQuery = computed(() => Object.fromEntries(['search', 'filter', 'sort', 'view', 'page'].filter(key => route.query[key]).map(key => [key, route.query[key]])))

const loading = ref(true), failed = ref(false), missing = ref(false), saving = ref(false), openingDirectory = ref(false)
const saveError = ref(''), saveDiagnostics = ref([]), saveConflict = ref(false)
const skill = ref(null)
const draft = ref(null)
const baseline = ref('')
const activeTab = ref('instructions')

const resourceFiles = ref([]), filesLimited = ref(false), filesLoading = ref(false), filesFailed = ref(false)
const selectedPath = ref(''), previewLoading = ref(false), previewFailed = ref(false), previewData = ref(null)

const dirty = computed(() => Boolean(!isHistoricalInspection.value && draft.value && baseline.value && JSON.stringify(draft.value) !== baseline.value))
const readonlyView = computed(() => Boolean(isHistoricalInspection.value || skill.value?.archived_only))

let alive = true, generation = 0, previewGeneration = 0

const selectResourceFile = async (path, expectedGen = generation) => {
  if (!path || creating.value) return
  const sid = skill.value?.skill_id || String(route.params.skillId || '')
  const ver = requestedVersion.value
  const reqId = ++previewGeneration
  selectedPath.value = path
  previewLoading.value = true
  previewFailed.value = false
  previewData.value = null
  try {
    const payload = { skill_id: sid, path }
    if (ver !== undefined) payload.version = ver
    const response = await taskAgentAPI('skill_preview_file', payload)
    if (!alive || expectedGen !== generation || reqId !== previewGeneration) return
    if (response.status !== 200 || !response.data?.kind) throw new Error()
    previewData.value = response.data
  } catch {
    if (alive && expectedGen === generation && reqId === previewGeneration) previewFailed.value = true
  } finally {
    if (alive && expectedGen === generation && reqId === previewGeneration) previewLoading.value = false
  }
}

const loadResourceFiles = async (sid, ver, expectedGen = generation) => {
  filesLoading.value = true
  filesFailed.value = false
  try {
    const payload = { skill_id: sid }
    if (ver !== undefined) payload.version = ver
    const response = await taskAgentAPI('skill_files', payload)
    if (!alive || expectedGen !== generation) return
    if (response.status !== 200 || !Array.isArray(response.data?.files)) throw new Error()
    resourceFiles.value = response.data.files
    filesLimited.value = Boolean(response.data.limited)
    if (resourceFiles.value.length > 0) {
      const preferred = resourceFiles.value.find(item => item.path !== 'SKILL.md') || resourceFiles.value[0]
      await selectResourceFile(preferred.path, expectedGen)
    } else {
      selectedPath.value = ''
      previewData.value = null
    }
  } catch {
    if (alive && expectedGen === generation) filesFailed.value = true
  } finally {
    if (alive && expectedGen === generation) filesLoading.value = false
  }
}

const load = async () => {
  const version = ++generation
  previewGeneration++
  loading.value = true
  failed.value = false
  missing.value = false
  saveError.value = ''
  saveDiagnostics.value = []
  saveConflict.value = false
  skill.value = null
  draft.value = null
  baseline.value = ''
  resourceFiles.value = []
  selectedPath.value = ''
  previewData.value = null

  if (creating.value) {
    const initial = {
      skill_id: 'skill_' + uuidv4().replaceAll('-', '').slice(0, 16),
      enabled: true,
      content: DEFAULT_SKILL_MD,
    }
    draft.value = initial
    baseline.value = JSON.stringify(initial)
    activeTab.value = 'editor'
    loading.value = false
    return
  }

  const sid = String(route.params.skillId || '')
  const reqVer = requestedVersion.value
  try {
    if (reqVer !== undefined) {
      // Explicit version route: always inspect the immutable pinned revision!
      const [filesRes, mdRes] = await Promise.all([
        taskAgentAPI('skill_files', { skill_id: sid, version: reqVer }),
        taskAgentAPI('skill_preview_file', { skill_id: sid, path: 'SKILL.md', version: reqVer }),
      ])
      if (!alive || version !== generation) return
      if (filesRes.status === 404 || mdRes.status === 404) {
        missing.value = true
        return
      }
      if (filesRes.status !== 200 || !Array.isArray(filesRes.data?.files) || mdRes.status !== 200 || mdRes.data?.kind !== 'text') throw new Error()
      const rawMd = String(mdRes.data.text || '')
      const totalBytes = filesRes.data.files.reduce((sum, f) => sum + (Number(f.size) || 0), 0)
      skill.value = {
        skill_id: sid,
        name: filesRes.data.name,
        description: filesRes.data.description,
        version: filesRes.data.version || reqVer,
        enabled: false,
        archived_only: true,
        content: rawMd,
        instructions: rawMd.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, '').trim(),
        file_count: filesRes.data.files.length,
        total_bytes: totalBytes,
        files: filesRes.data.files,
      }
      resourceFiles.value = filesRes.data.files
      filesLimited.value = Boolean(filesRes.data.limited)
      if (!['instructions', 'resources'].includes(activeTab.value)) {
        activeTab.value = 'instructions'
      }
      if (resourceFiles.value.length > 0) {
        const preferred = resourceFiles.value.find(item => item.path !== 'SKILL.md') || resourceFiles.value[0]
        await selectResourceFile(preferred.path, version)
      }
      return
    }

    const detailRes = await taskAgentAPI('skill', { skill_id: sid })
    if (!alive || version !== generation) return
    if (detailRes.status === 404) {
      missing.value = true
      return
    }
    if (detailRes.status !== 200 || !detailRes.data?.skill_id) throw new Error()
    skill.value = detailRes.data
    const editState = {
      skill_id: detailRes.data.skill_id,
      enabled: Boolean(detailRes.data.enabled),
      content: String(detailRes.data.content || ''),
    }
    draft.value = editState
    baseline.value = JSON.stringify(editState)
    if (!['instructions', 'editor', 'resources'].includes(activeTab.value)) {
      activeTab.value = 'instructions'
    }
    await loadResourceFiles(sid, undefined, version)
  } catch {
    if (alive && version === generation) failed.value = true
  } finally {
    if (alive && version === generation) loading.value = false
  }
}

const refreshLatestKeepDraft = async () => {
  if (!skill.value?.skill_id || creating.value || readonlyView.value || saving.value) return
  const expectedGen = generation
  const sid = skill.value.skill_id
  try {
    const detailRes = await taskAgentAPI('skill', { skill_id: sid })
    if (!alive || expectedGen !== generation) return
    if (detailRes.status === 200 && detailRes.data?.skill_id) {
      skill.value = { ...skill.value, ...detailRes.data }
      saveError.value = ''
      saveDiagnostics.value = []
      saveConflict.value = false
      await loadResourceFiles(sid, undefined, expectedGen)
    } else {
      saveError.value = formatIntegrationError(detailRes, t)
    }
  } catch {
    if (alive && expectedGen === generation) {
      saveError.value = t('workspace.taskAgentSpace.load_failed')
    }
  }
}
const saveSkill = async () => {
  if (!draft.value || saving.value || readonlyView.value) return
  const rawContent = String(draft.value.content || '')
  if (!rawContent.trim()) {
    saveError.value = t('workspace.taskAgentSpace.integration_error_skills_invalid_frontmatter')
    saveDiagnostics.value = []
    saveConflict.value = false
    return
  }
  const expectedGen = generation
  const wasCreating = creating.value
  const targetSkillId = draft.value.skill_id
  saving.value = true
  saveError.value = ''
  saveDiagnostics.value = []
  saveConflict.value = false
  try {
    const payload = {
      skill_id: targetSkillId,
      content: rawContent,
      enabled: Boolean(draft.value.enabled),
    }
    if (!wasCreating && skill.value?.updated_at) {
      payload.expected_updated_at = skill.value.updated_at
    }
    const response = await taskAgentAPI('save_skill', payload)
    if (!alive || expectedGen !== generation) return
    if (response.status !== 200 || !response.data?.skill_id) {
      saveError.value = formatIntegrationError(response, t)
      saveDiagnostics.value = extractSkillDiagnostics(response)
      saveConflict.value = response.status === 409
      return
    }
    skill.value = response.data
    const nextDraft = {
      skill_id: response.data.skill_id,
      enabled: Boolean(response.data.enabled),
      content: String(response.data.content || ''),
    }
    draft.value = nextDraft
    baseline.value = JSON.stringify(nextDraft)
    message.success(t('workspace.taskAgentSpace.skill_saved'))
    saving.value = false
    if (wasCreating) {
      await router.replace({ name: 'taskAgentSkillDetail', params: { skillId: response.data.skill_id }, query: listQuery.value })
    } else {
      await loadResourceFiles(response.data.skill_id, undefined, expectedGen)
    }
  } catch {
    if (alive && expectedGen === generation) {
      saveError.value = t('workspace.taskAgentSpace.save_failed')
    }
  } finally {
    if (alive && expectedGen === generation) {
      saving.value = false
    }
  }
}

const openSkillDirectory = async () => {
  if (creating.value || !skill.value?.skill_id || openingDirectory.value) return
  const expectedGen = generation
  const sid = skill.value.skill_id
  const ver = isHistoricalInspection.value ? (requestedVersion.value ?? skill.value.version) : undefined
  openingDirectory.value = true
  try {
    const payload = { skill_id: sid }
    if (ver !== undefined) payload.version = ver
    const response = await taskAgentAPI('open_skill_directory', payload)
    if (!alive || expectedGen !== generation) return
    if (response.status !== 200 || !response.data?.opened) {
      message.error(formatIntegrationError(response, t, 'workspace.taskAgentSpace.skill_open_directory_failed'))
    }
  } catch {
    if (alive && expectedGen === generation) {
      message.error(t('workspace.taskAgentSpace.skill_open_directory_failed'))
    }
  } finally {
    if (alive && expectedGen === generation) {
      openingDirectory.value = false
    }
  }
}

const confirmDelete = () => {
  if (!skill.value || creating.value || readonlyView.value || saving.value) return
  const expectedGen = generation
  const target = { skill_id: skill.value.skill_id, updated_at: skill.value.updated_at, name: skill.value.name }
  Modal.confirm({
    title: t('workspace.taskAgentSpace.skill_delete_title', { name: target.name }),
    content: t('workspace.taskAgentSpace.skill_delete_confirm', { name: target.name }),
    okText: t('workspace.taskAgentSpace.skill_delete_action'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      try {
        const response = await taskAgentAPI('delete_skill', {
          skill_id: target.skill_id,
          expected_updated_at: target.updated_at,
        })
        if (response.status !== 200) {
          if (alive) message.error(formatIntegrationError(response, t))
          if (alive && expectedGen === generation && response.status === 409) {
            await refreshLatestKeepDraft()
          }
          return Promise.reject(new Error('delete_failed'))
        }
        if (alive && expectedGen === generation) {
          baseline.value = JSON.stringify(draft.value)
          message.success(t('workspace.taskAgentSpace.skill_deleted'))
          await router.push({ name: 'taskAgentSkills', query: listQuery.value })
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

const sourceKindLabel = kind => {
  if (kind === 'directory') return t('workspace.taskAgentSpace.skill_source_directory')
  if (kind === 'archive') return t('workspace.taskAgentSpace.skill_source_archive')
  return t('workspace.taskAgentSpace.skill_source_manual')
}

const confirmLeave = () => {
  if (saving.value) return false
  return !dirty.value || window.confirm(t('workspace.taskAgentSpace.skill_unsaved'))
}
const beforeUnload = event => { if (dirty.value || saving.value) event.preventDefault() }

watch(() => [route.name, route.params.skillId, route.query.version], load)
onBeforeRouteLeave(confirmLeave)
onBeforeRouteUpdate((to, from) => (to.params.skillId === from.params.skillId && to.name === from.name && to.query.version === from.query.version) || confirmLeave())
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); load() })
onBeforeUnmount(() => { alive = false; generation++; previewGeneration++; window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <main class="skill-detail-page">
    <header class="skill-detail-header">
      <div class="detail-breadcrumb">
        <router-link :to="{ name: 'taskAgentSkills', query: listQuery }">
          <Left />
          <span>{{ t('workspace.taskAgentSpace.skills_back') }}</span>
        </router-link>
        <span class="breadcrumb-separator">/</span>
        <h1>{{ creating ? t('workspace.taskAgentSpace.skill_create') : (skill?.name || route.params.skillId) }}</h1>
        <span v-if="skill?.version" class="version-badge">v{{ skill.version }}</span>
        <span v-if="readonlyView" class="readonly-badge">{{ t('workspace.taskAgentSpace.skill_historical_revision_badge') }}</span>
        <span v-if="dirty" class="unsaved-indicator">{{ t('workspace.taskAgentSpace.profile_unsaved_label') }}</span>
      </div>
      <div class="detail-header-actions">
        <IconButton v-if="saveConflict && !creating && !readonlyView" type="text" :disabled="saving" @click="refreshLatestKeepDraft" :text="t('workspace.taskAgentSpace.skill_refresh_metadata')"><template #icon><Refresh /></template></IconButton>
        <IconButton v-if="!creating && skill"
            type="text"
            :loading="openingDirectory"
            :disabled="saving || openingDirectory"
            :aria-label="t('workspace.taskAgentSpace.skill_open_directory')"
            @click="openSkillDirectory"
           :text="t('workspace.taskAgentSpace.skill_open_directory')"><template #icon><FolderOpen /></template></IconButton>
        <IconButton v-if="!creating && skill && !readonlyView" type="text" danger :disabled="saving" @click="confirmDelete" :text="t('workspace.taskAgentSpace.skill_delete_action')"><template #icon><Delete /></template></IconButton>
        <IconButton v-if="!readonlyView" type="text" class="skill-save-btn" :loading="saving" :disabled="!draft || saving" @click="saveSkill" :text="t('workspace.taskAgentSpace.skill_save')"><template #icon><Save /></template></IconButton>
      </div>
    </header>

    <div class="skill-detail-content">
      <div v-if="loading" class="detail-loading"><a-spin size="large" /></div>
      <div v-else-if="missing" class="detail-loading">
        <a-empty :description="t('workspace.taskAgentSpace.skill_not_found')">
          <router-link :to="{ name: 'taskAgentSkills', query: listQuery }">
            <a-button type="primary">{{ t('workspace.taskAgentSpace.skills_back') }}</a-button>
          </router-link>
        </a-empty>
      </div>
      <div v-else-if="failed" class="detail-loading">
        <a-empty :description="t('workspace.taskAgentSpace.load_failed')">
          <IconButton type="primary" @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
        </a-empty>
      </div>
      <template v-else-if="draft || readonlyView">
        <a-alert v-if="saveError" type="error" show-icon class="detail-save-error" :message="saveError">
          <template v-if="saveDiagnostics.length" #description>
            <ul class="diagnostic-list">
              <li v-for="(diag, index) in saveDiagnostics" :key="index">{{ diag }}</li>
            </ul>
          </template>
        </a-alert>

        <a-alert
          v-if="readonlyView && skill?.version"
          type="info"
          show-icon
          class="detail-save-error"
          :message="t('workspace.taskAgentSpace.skill_historical_revision_hint', { version: skill.version })"
        />

        <div class="skill-detail-grid">
          <aside class="skill-sidebar">
            <section class="configuration-section">
              <h2><BookOpen />{{ t('workspace.taskAgentSpace.skill_overview') }}</h2>
              <div class="section-body">
                <div class="skill-identity">
                  <BookOpen />
                  <div>
                    <strong>{{ creating ? t('workspace.taskAgentSpace.skill_create') : skill?.name }}</strong>
                    <p v-if="skill?.description">{{ skill.description }}</p>
                  </div>
                </div>
                <div v-if="!readonlyView" class="switch-row">
                  <span>{{ t('workspace.taskAgentSpace.skill_enabled_label') }}</span>
                  <a-switch v-model:checked="draft.enabled" :disabled="saving" :aria-label="t('workspace.taskAgentSpace.skill_enabled_label')" />
                </div>
                <dl v-if="skill" class="meta-list">
                  <div>
                    <dt>{{ t('workspace.taskAgentSpace.skill_version_label') }}</dt>
                    <dd>v{{ skill.version }}</dd>
                  </div>
                  <div v-if="skill.source_kind">
                    <dt>{{ t('workspace.taskAgentSpace.skill_source_label') }}</dt>
                    <dd>{{ sourceKindLabel(skill.source_kind) }}</dd>
                  </div>
                  <div>
                    <dt>{{ t('workspace.taskAgentSpace.skill_resources_tab') }}</dt>
                    <dd>{{ t('workspace.taskAgentSpace.skill_file_count', { count: skill.file_count || resourceFiles.length || 1 }) }}</dd>
                  </div>
                  <div v-if="skill.total_bytes !== undefined">
                    <dt>{{ t('workspace.taskAgentSpace.skill_size_label') }}</dt>
                    <dd>{{ fileSize(skill.total_bytes || 0) }}</dd>
                  </div>
                  <div v-if="skill.license">
                    <dt>{{ t('workspace.taskAgentSpace.skill_license_label') }}</dt>
                    <dd>{{ skill.license }}</dd>
                  </div>
                  <div v-if="skill.compatibility">
                    <dt>{{ t('workspace.taskAgentSpace.skill_compatibility_label') }}</dt>
                    <dd>{{ skill.compatibility }}</dd>
                  </div>
                  <div v-if="skill.updated_at">
                    <dt>{{ t('workspace.taskAgentSpace.skill_updated_label') }}</dt>
                    <dd>{{ formatTaskTime(skill.updated_at, locale) }}</dd>
                  </div>
                </dl>
                <a-alert
                  v-if="skill?.warnings?.length"
                  type="warning"
                  show-icon
                  class="warnings-alert"
                  :message="t('workspace.taskAgentSpace.skill_warnings_title')"
                >
                  <template #description>
                    <ul class="diagnostic-list">
                      <li v-for="(warn, idx) in skill.warnings" :key="idx">{{ warn }}</li>
                    </ul>
                  </template>
                </a-alert>
                <p class="field-help">{{ t('workspace.taskAgentSpace.skill_immutable_hint') }}</p>
              </div>
            </section>
          </aside>

          <div class="skill-main">
            <section class="configuration-section">
              <div class="tabs-wrapper">
                <a-tabs v-model:activeKey="activeTab">
                  <a-tab-pane v-if="!creating" key="instructions" :tab="t('workspace.taskAgentSpace.skill_instructions_tab')">
                    <div class="pane-body">
                      <p class="field-help">{{ t('workspace.taskAgentSpace.skill_instructions_hint') }}</p>
                      <pre class="safe-pre">{{ skill?.instructions || skill?.content || '' }}</pre>
                    </div>
                  </a-tab-pane>

                  <a-tab-pane v-if="!readonlyView" key="editor" :tab="t('workspace.taskAgentSpace.skill_editor_tab')">
                    <div class="pane-body">
                      <p class="field-help">{{ t('workspace.taskAgentSpace.skill_editor_hint') }}</p>
                      <a-textarea
                        v-model:value="draft.content"
                        :disabled="saving"
                        :aria-label="t('workspace.taskAgentSpace.skill_editor_tab')"
                        :rows="18"
                        class="skill-md-textarea"
                      />
                    </div>
                  </a-tab-pane>

                  <a-tab-pane v-if="!creating" key="resources">
                    <template #tab>
                      {{ t('workspace.taskAgentSpace.skill_resources_tab') }}
                      <span class="tab-count">{{ resourceFiles.length }}</span>
                    </template>
                    <div class="pane-body">
                      <p v-if="filesLimited" class="field-help">{{ t('workspace.taskAgentSpace.files_limited') }}</p>
                      <div v-if="filesLoading" class="resources-loading"><a-spin /></div>
                      <div v-else-if="filesFailed" class="resources-loading">
                        <IconButton @click="loadResourceFiles(skill.skill_id, requestedVersion, generation)" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
                      </div>
                      <div v-else-if="resourceFiles.length === 0" class="resources-loading">
                        <a-empty :description="t('workspace.taskAgentSpace.skill_no_resources')" />
                      </div>
                      <div v-else class="resources-split">
                        <nav class="resources-file-list" :aria-label="t('workspace.taskAgentSpace.skill_resources_tab')">
                          <button
                            v-for="file in resourceFiles"
                            :key="file.path"
                            type="button"
                            class="resource-file-item"
                            :aria-current="selectedPath === file.path ? 'true' : undefined"
                            :class="{ active: selectedPath === file.path }"
                            @click="selectResourceFile(file.path, generation)"
                          >
                            <DocDetail />
                            <span class="resource-path">{{ file.path }}</span>
                            <small>{{ fileSize(file.size || 0) }}</small>
                          </button>
                        </nav>
                        <div class="resource-preview-pane">
                          <div class="preview-header">
                            <strong>{{ selectedPath }}</strong>
                          </div>
                          <div v-if="previewLoading" class="resources-loading"><a-spin /></div>
                          <div v-else-if="previewFailed" class="resources-loading">
                            <p>{{ t('workspace.taskAgentSpace.file_failed') }}</p>
                            <IconButton size="small" @click="selectResourceFile(selectedPath, generation)" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
                          </div>
                          <template v-else-if="previewData">
                            <div v-if="previewData.kind === 'image' && previewData.url" class="image-preview-wrap">
                              <img :src="previewData.url" :alt="selectedPath" />
                            </div>
                            <template v-else-if="previewData.kind === 'text'">
                              <p v-if="previewData.truncated" class="field-help">{{ t('workspace.taskAgentSpace.preview_limited') }}</p>
                              <pre class="safe-pre">{{ previewData.text }}</pre>
                            </template>
                            <div v-else class="resources-loading">
                              <p class="field-help">{{ t('workspace.taskAgentSpace.no_preview') }}</p>
                            </div>
                          </template>
                        </div>
                      </div>
                    </div>
                  </a-tab-pane>
                </a-tabs>
              </div>
            </section>
          </div>
        </div>
      </template>
    </div>
  </main>
</template>

<style scoped>
.skill-detail-page { display: flex; height: 100%; min-width: 0; flex-direction: column; color: var(--site-text-color); }
.skill-detail-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 64px; gap: 20px; padding: 12px 24px; background: var(--component-background); border-bottom: var(--light-border); }
.detail-breadcrumb { display: flex; align-items: center; gap: 12px; min-width: 0; }
.detail-breadcrumb > a { display: inline-flex; align-items: center; gap: 8px; color: var(--site-secondary-text-color); white-space: nowrap; text-decoration: none; }
.detail-breadcrumb svg { height: 16px; width: 16px; flex-shrink: 0; }
.breadcrumb-separator { color: var(--site-secondary-text-color); }
h1 { margin: 0; font-size: 16px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.version-badge { padding: 1px 6px; border-radius: 4px; background: var(--gray-background); color: var(--site-secondary-text-color); font-size: 11px; font-variant-numeric: tabular-nums; }
.readonly-badge { padding: 1px 6px; border-radius: 4px; background: color-mix(in srgb, var(--color-primary) 12%, transparent); color: var(--color-primary); font-size: 11px; white-space: nowrap; }
.unsaved-indicator { font-size: 12px; color: var(--site-secondary-text-color); }
.detail-header-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.detail-header-actions :deep(.skill-save-btn):not(:disabled) { color: var(--color-primary); font-weight: 500; }
.skill-detail-content { flex: 1; min-height: 0; padding: 24px; background: var(--gray-background); overflow: auto; }
.skill-detail-grid { display: grid; grid-template-columns: minmax(260px, 320px) minmax(0, 1fr); gap: 24px; max-width: 1560px; margin: 0 auto; align-items: start; }
.skill-sidebar, .skill-main { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.configuration-section { min-width: 0; background: var(--component-background); border: 1px solid color-mix(in srgb, var(--site-text-color) 7%, transparent); border-radius: 8px; }
h2 { display: flex; align-items: center; gap: 8px; margin: 0; padding: 15px 20px; border-bottom: var(--light-border); font-size: 14px; font-weight: 500; }
h2 svg { width: 16px; height: 16px; color: var(--site-secondary-text-color); }
.section-body { padding: 20px; }
.skill-identity { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 18px; min-width: 0; }
.skill-identity > svg { box-sizing: content-box; width: 24px; height: 24px; padding: 10px; border: var(--light-border); border-radius: 8px; background: color-mix(in srgb, var(--color-primary) 7%, var(--component-background)); color: var(--color-primary); flex-shrink: 0; }
.skill-identity strong { display: block; font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
.skill-identity p { margin: 4px 0 0; font-size: 12px; color: var(--site-secondary-text-color); line-height: 1.6; overflow-wrap: anywhere; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 0; border-top: var(--light-border); border-bottom: var(--light-border); margin-bottom: 14px; font-size: 13px; }
.meta-list { margin: 0 0 14px; display: flex; flex-direction: column; gap: 8px; font-size: 12px; }
.meta-list > div { display: flex; justify-content: space-between; gap: 12px; }
.meta-list dt { color: var(--site-secondary-text-color); }
.meta-list dd { margin: 0; font-weight: 500; text-align: right; overflow-wrap: anywhere; }
.warnings-alert { margin-bottom: 12px; }
.diagnostic-list { margin: 6px 0 0; padding-left: 18px; font-size: 12px; }
.field-help { color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.7; margin: 0 0 12px; overflow-wrap: anywhere; }
.tabs-wrapper :deep(.ant-tabs-nav) { padding: 0 20px; margin-bottom: 0; }
.pane-body { padding: 20px; }
.safe-pre { margin: 0; padding: 14px; border: var(--light-border); border-radius: 6px; background: var(--gray-background); color: var(--site-text-color); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12.5px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 540px; overflow: auto; }
.skill-md-textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; line-height: 1.65; }
.tab-count { margin-left: 6px; padding: 1px 6px; border-radius: 8px; background: var(--gray-background); font-size: 11px; color: var(--site-secondary-text-color); }
.resources-split { display: grid; grid-template-columns: minmax(200px, 280px) minmax(0, 1fr); gap: 16px; min-height: 360px; }
.resources-file-list { display: flex; flex-direction: column; gap: 4px; padding: 8px; border: var(--light-border); border-radius: 6px; background: var(--gray-background); max-height: 520px; overflow: auto; }
.resource-file-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 7px 10px; border: 0; border-radius: 5px; background: transparent; color: var(--site-text-color); font-size: 12px; text-align: left; cursor: pointer; }
.resource-file-item:hover { background: color-mix(in srgb, var(--site-text-color) 6%, transparent); }
.resource-file-item:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 1px; }
.resource-file-item.active { color: var(--color-primary); background: color-mix(in srgb, var(--color-primary) 12%, transparent); font-weight: 500; }
.resource-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resource-file-item small { color: var(--site-secondary-text-color); font-size: 11px; flex-shrink: 0; }
.resource-preview-pane { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.preview-header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 8px; border-bottom: var(--light-border); font-size: 12px; overflow-wrap: anywhere; }
.image-preview-wrap { display: flex; justify-content: center; align-items: center; padding: 16px; border: var(--light-border); border-radius: 6px; background: var(--gray-background); }
.image-preview-wrap img { max-width: 100%; max-height: 420px; object-fit: contain; }
.detail-loading, .resources-loading { text-align: center; padding: 64px 20px; }
.detail-save-error { max-width: 1560px; margin: 0 auto 20px; }
@media (max-width: 900px) {
  .skill-detail-grid { grid-template-columns: minmax(0, 1fr); }
  .resources-split { grid-template-columns: minmax(0, 1fr); }
  .skill-detail-header { flex-wrap: wrap; padding: 12px 16px; }
  .skill-detail-content { padding: 16px; }
}
</style>
