<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import { Left, Robot, Save, PlayOne, Copy, User, Setting, Tool, Code, CheckOne, Delete, Refresh, Undo } from '@/icons'
import ModelPicker from '@/components/ModelPicker.vue'
import KnowledgeBasePicker from '@/components/taskAgent/KnowledgeBasePicker.vue'
import TaskAgentPermissions from './TaskAgentPermissions.vue'
import TaskAgentModelError from './TaskAgentModelError.vue'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatIntegrationError } from '@/utils/taskAgentErrors'
import { getChatModelOptions } from '@/utils/common'
import { validModelPair } from '@/utils/modelPreferences'
import { useModelCatalogStore } from '@/stores/modelCatalog'

const route = useRoute(), router = useRouter()
const { t } = useI18n()
const catalog = useModelCatalogStore()
const form = ref(null), draft = ref(null), workflows = ref([]), skills = ref([]), mcpTools = ref([])
const loading = ref(true), failed = ref(false), missing = ref(false), saving = ref(false), saveError = ref('')
const skillsFailed = ref(false), skillsLoading = ref(false), mcpFailed = ref(false), mcpLoading = ref(false)
const baseline = ref(''), preference = ref('custom'), capabilityTab = ref('tools')
const modelFailure = ref(null)
const lastLimitedCycles = ref(50)
const cycleLimitEnabled = computed({
  get: () => Boolean(draft.value && draft.value.max_cycles !== 0),
  set: enabled => {
    if (!draft.value) return
    if (enabled) draft.value.max_cycles = lastLimitedCycles.value
    else {
      if (Number.isInteger(draft.value.max_cycles) && draft.value.max_cycles > 0) lastLimitedCycles.value = draft.value.max_cycles
      draft.value.max_cycles = 0
    }
  },
})
const creating = computed(() => route.name === 'taskAgentCreate')
const isBuiltinGeneral = computed(() => !creating.value && (draft.value?.agent_id === 'general' || route.params.agentId === 'general'))
const identity = computed(() => creating.value ? 'new:' + String(route.query.copy || '') : String(route.params.agentId || ''))
const listQuery = computed(() => Object.fromEntries(['tab', 'search', 'filter', 'sort', 'view', 'page'].filter(key => route.query[key]).map(key => [key, route.query[key]])))
const modelOptions = computed(() => getChatModelOptions())
const dirty = computed(() => Boolean(draft.value && baseline.value && JSON.stringify(draft.value) !== baseline.value))
const modelReady = computed(() => !draft.value?.model_provider && !draft.value?.model || validModelPair(modelOptions.value, draft.value?.model_provider, draft.value?.model))
const textLimit = (value, limit, key) => new TextEncoder().encode(String(value || '').trim()).length > limit ? Promise.reject(new Error(t('workspace.taskAgentSpace.' + key))) : Promise.resolve()
const rules = computed(() => ({ name: [{ required: true, whitespace: true, message: t('workspace.taskAgentSpace.profile_name_required') }, { validator: (_, value) => textLimit(value, 160, 'profile_name_too_long') }], instructions: [...(isBuiltinGeneral.value ? [] : [{ required: true, whitespace: true, message: t('workspace.taskAgentSpace.profile_instructions_required') }]), { validator: (_, value) => textLimit(value, 32768, 'profile_instructions_too_long') }], max_cycles: cycleLimitEnabled.value ? [{ type: 'integer', required: true, min: 1, max: 4294967295, message: t('workspace.taskAgentSpace.profile_cycles_required') }] : [] }))
const workflowOptions = computed(() => {
  const available = workflows.value.map(item => ({ value: item.workflow_id, label: item.title }))
  for (const id of draft.value?.workflow_ids || []) if (!available.some(item => item.value === id)) available.push({ value: id, label: t('workspace.taskAgentSpace.profile_missing_workflow', { id }) })
  return available
})
const enabledSkills = computed(() => skills.value.filter(item => item && item.enabled === true))
const skillOptions = computed(() => {
  const available = enabledSkills.value.map(item => ({
    value: item.skill_id,
    label: item.description ? `${item.name} — ${item.description}` : item.name,
  }))
  for (const id of draft.value?.skill_ids || []) {
    if (!available.some(item => item.value === id)) {
      if (skillsFailed.value) {
        available.push({ value: id, label: id })
      } else {
        const disabledItem = skills.value.find(item => item.skill_id === id)
        const display = disabledItem ? `${disabledItem.name} (${id})` : id
        available.push({ value: id, label: t('workspace.taskAgentSpace.profile_missing_skill', { id: display }) })
      }
    }
  }
  return available
})
const unavailableSkillIds = computed(() => skillsFailed.value ? [] : (draft.value?.skill_ids || []).filter(id => !enabledSkills.value.some(item => item.skill_id === id)))
const duplicateSkillName = computed(() => {
  if (skillsFailed.value) return ''
  const seen = new Set()
  for (const id of draft.value?.skill_ids || []) {
    const item = enabledSkills.value.find(s => s.skill_id === id)
    if (!item?.name) continue
    if (seen.has(item.name)) return item.name
    seen.add(item.name)
  }
  return ''
})
const mcpToolOptions = computed(() => {
  const serverIdsByName = new Map()
  for (const item of mcpTools.value) {
    const sId = item.server_id || 'mcp'
    const sName = item.server_name || sId
    if (!serverIdsByName.has(sName)) serverIdsByName.set(sName, new Set())
    serverIdsByName.get(sName).add(sId)
  }
  const available = mcpTools.value.map(item => {
    const toolId = item.namespaced_name
    const baseName = item.server_name || item.server_id
    const serverLabel = (serverIdsByName.get(baseName)?.size || 0) > 1 && item.server_id ? `${baseName} (${item.server_id})` : baseName
    const toolLabel = item.title || item.name || toolId
    return {
      value: toolId,
      label: `${serverLabel}: ${toolLabel}${item.name && item.title && item.title !== item.name ? ` (${item.name})` : ''}`,
    }
  })
  for (const id of draft.value?.mcp_tool_ids || []) {
    if (!available.some(item => item.value === id)) {
      available.push({ value: id, label: mcpFailed.value ? id : t('workspace.taskAgentSpace.profile_missing_mcp_tool', { id }) })
    }
  }
  return available
})
const unavailableMcpToolIds = computed(() => mcpFailed.value ? [] : (draft.value?.mcp_tool_ids || []).filter(id => !mcpTools.value.some(item => item.namespaced_name === id)))
const removeUnavailableSkills = () => {
  if (!draft.value) return
  const bad = new Set(unavailableSkillIds.value)
  draft.value.skill_ids = (draft.value.skill_ids || []).filter(id => !bad.has(id))
}
const removeUnavailableMcpTools = () => {
  if (!draft.value) return
  const bad = new Set(unavailableMcpToolIds.value)
  draft.value.mcp_tool_ids = (draft.value.mcp_tool_ids || []).filter(id => !bad.has(id))
}
const defaultDraft = () => ({ agent_id: uuidv4().replaceAll('-', ''), name: '', description: '', instructions: '', max_cycles: 0, allow_file_writes: true, allow_shell: true, shell: 'auto', allow_sub_agents: true, permission_mode: 'auto', knowledge_base_ids: [], workflow_ids: [], skill_ids: [], mcp_tool_ids: [], model_provider: '', model: '', reasoning_effort: 'default' })
let alive = true, generation = 0, skillsGen = 0, mcpGen = 0
const reloadSkillsCatalog = async () => {
  const req = ++skillsGen
  skillsLoading.value = true
  try {
    const res = await taskAgentAPI('skills')
    if (!alive || req !== skillsGen) return
    if (res?.status === 200 && Array.isArray(res.data?.skills)) {
      skills.value = res.data.skills
      skillsFailed.value = false
    } else {
      skillsFailed.value = true
    }
  } catch {
    if (alive && req === skillsGen) skillsFailed.value = true
  } finally {
    if (alive && req === skillsGen) skillsLoading.value = false
  }
}
const reloadMcpToolsCatalog = async () => {
  const req = ++mcpGen
  mcpLoading.value = true
  try {
    const res = await taskAgentAPI('mcp_tools')
    if (!alive || req !== mcpGen) return
    if (res?.status === 200 && Array.isArray(res.data?.tools)) {
      mcpTools.value = res.data.tools
      mcpFailed.value = false
    } else {
      mcpFailed.value = true
    }
  } catch {
    if (alive && req === mcpGen) mcpFailed.value = true
  } finally {
    if (alive && req === mcpGen) mcpLoading.value = false
  }
}
const load = async () => {
  const version = ++generation
  loading.value = true; failed.value = false; missing.value = false; saveError.value = ''; modelFailure.value = null; draft.value = null; baseline.value = ''
  skillsFailed.value = false; mcpFailed.value = false
  const isNew = creating.value, agentId = String(isNew ? route.query.copy || '' : route.params.agentId || '')
  try {
    const [profile, choices, skillsRes, mcpRes] = await Promise.all([
      agentId ? taskAgentAPI('profile', { agent_id: agentId }) : Promise.resolve(null),
      taskAgentAPI('workflows'),
      Promise.resolve().then(() => taskAgentAPI('skills')).catch(() => null),
      Promise.resolve().then(() => taskAgentAPI('mcp_tools')).catch(() => null),
      catalog.ensureLoaded(),
    ])
    if (!alive || version !== generation) return
    if (profile?.status === 404) { missing.value = true; return }
    if ((profile && profile.status !== 200) || choices?.status !== 200) throw new Error()
    const value = isNew ? defaultDraft() : { ...defaultDraft(), allow_shell: false, allow_sub_agents: false }
    if (profile) {
      Object.assign(value, profile.data, {
        knowledge_base_ids: [...(profile.data.knowledge_base_ids || [])],
        workflow_ids: [...(profile.data.workflow_ids || [])],
        skill_ids: [...(profile.data.skill_ids || [])],
        mcp_tool_ids: [...(profile.data.mcp_tool_ids || [])],
      })
      if (isNew) {
        value.agent_id = uuidv4().replaceAll('-', '')
        value.name = t('workspace.taskAgentSpace.profile_copy_name', { name: profile.data.name || t('workspace.taskAgentSpace.general_agent') })
        value.instructions ||= t('workspace.taskAgentSpace.general_description')
        delete value.created_at; delete value.updated_at
      }
    }
    if (!isNew && (value.agent_id === 'general' || agentId === 'general')) { value.agent_id = 'general'; value.name ||= t('workspace.taskAgentSpace.general_agent'); value.description ||= t('workspace.taskAgentSpace.general_description') }
    lastLimitedCycles.value = Number.isInteger(value.max_cycles) && value.max_cycles > 0 ? value.max_cycles : 50
    draft.value = value
    workflows.value = choices.data?.workflows || []
    if (skillsRes?.status === 200 && Array.isArray(skillsRes.data?.skills)) {
      skills.value = skillsRes.data.skills
      skillsFailed.value = false
    } else {
      skills.value = []
      skillsFailed.value = true
    }
    if (mcpRes?.status === 200 && Array.isArray(mcpRes.data?.tools)) {
      mcpTools.value = mcpRes.data.tools
      mcpFailed.value = false
    } else {
      mcpTools.value = []
      mcpFailed.value = true
    }
    baseline.value = JSON.stringify(value)
  } catch { if (alive && version === generation) failed.value = true }
  finally { if (alive && version === generation) loading.value = false }
}
const save = async () => {
  if (saving.value || !draft.value) return
  saveError.value = ''
  modelFailure.value = null
  try { await form.value.validate() } catch (error) { form.value?.scrollToField(error?.errorFields?.[0]?.name || 'name'); return }
  if (!modelReady.value) { saveError.value = t('components.model_selector.model_unavailable'); return }
  if (draft.value.workflow_ids.some(id => !workflows.value.some(item => item.workflow_id === id))) {
    capabilityTab.value = 'workflows'
    saveError.value = t('workspace.taskAgentSpace.profile_workflows_unavailable')
    return
  }
  if ((draft.value.knowledge_base_ids || []).length > 20) {
    capabilityTab.value = 'knowledge'
    saveError.value = t('knowledgeBase.mount_limit', { count: draft.value.knowledge_base_ids.length })
    return
  }
  if ((draft.value.skill_ids || []).length > 20) {
    capabilityTab.value = 'skills'
    saveError.value = t('workspace.taskAgentSpace.profile_skills_limit_exceeded')
    return
  }
  if (skillsFailed.value && (draft.value.skill_ids || []).length > 0) {
    capabilityTab.value = 'skills'
    saveError.value = t('workspace.taskAgentSpace.profile_skills_load_failed')
    return
  }
  if (unavailableSkillIds.value.length) {
    capabilityTab.value = 'skills'
    saveError.value = t('workspace.taskAgentSpace.profile_skills_unavailable')
    return
  }
  if (duplicateSkillName.value) {
    capabilityTab.value = 'skills'
    saveError.value = t('workspace.taskAgentSpace.profile_skills_duplicate_name', { name: duplicateSkillName.value })
    return
  }
  if ((draft.value.mcp_tool_ids || []).length > 64) {
    capabilityTab.value = 'mcp'
    saveError.value = t('workspace.taskAgentSpace.profile_mcp_limit_exceeded')
    return
  }
  if (mcpFailed.value && (draft.value.mcp_tool_ids || []).length > 0) {
    capabilityTab.value = 'mcp'
    saveError.value = t('workspace.taskAgentSpace.profile_mcp_load_failed')
    return
  }
  if (unavailableMcpToolIds.value.length) {
    capabilityTab.value = 'mcp'
    saveError.value = t('workspace.taskAgentSpace.profile_mcp_unavailable')
    return
  }
  const version = generation, payload = JSON.parse(JSON.stringify(draft.value)), isNew = creating.value
  saving.value = true
  try {
    const response = await taskAgentAPI('save_profile', payload)
    if (!alive || generation !== version) return
    if (response.status !== 200) {
      if (response.data?.model_failure) { modelFailure.value = response.data.model_failure; return }
      if (response.data?.integration_error || response.status === 409) {
        if (response.data?.integration_error?.kind === 'skills') capabilityTab.value = 'skills'
        else if (response.data?.integration_error?.kind === 'mcp') capabilityTab.value = 'mcp'
        saveError.value = formatIntegrationError(response, t, 'workspace.taskAgentSpace.save_failed')
        return
      }
      throw new Error()
    }
    draft.value = {
      ...payload,
      ...response.data,
      knowledge_base_ids: [...(response.data.knowledge_base_ids || payload.knowledge_base_ids || [])],
      workflow_ids: [...(response.data.workflow_ids || payload.workflow_ids || [])],
      skill_ids: [...(response.data.skill_ids || payload.skill_ids || [])],
      mcp_tool_ids: [...(response.data.mcp_tool_ids || payload.mcp_tool_ids || [])],
    }
    baseline.value = JSON.stringify(draft.value)
    message.success(t('workspace.taskAgentSpace.profile_saved'))
    if (isNew) await router.replace({ name: 'taskAgentEdit', params: { agentId: payload.agent_id }, query: listQuery.value })
  } catch { if (alive && version === generation) saveError.value = t('workspace.taskAgentSpace.save_failed') }
  finally { if (alive) saving.value = false }
}
const resetModel = () => { draft.value.model_provider = ''; draft.value.model = ''; draft.value.reasoning_effort = 'default'; preference.value = 'custom' }
const beforeUnload = event => { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
const confirmLeave = () => saving.value && dirty.value ? false : !dirty.value || window.confirm(t('workspace.taskAgentSpace.profile_unsaved'))
onBeforeRouteLeave(confirmLeave)
onBeforeRouteUpdate((to, from) => to.params.agentId !== from.params.agentId || to.query.copy !== from.query.copy ? confirmLeave() : true)
watch(identity, load)
onMounted(() => { load(); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => { alive = false; generation++; skillsGen++; mcpGen++; window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <main class="agent-detail-page">
    <header class="agent-detail-header">
      <div class="detail-breadcrumb"><router-link :to="{ name: 'taskAgentAgents', query: listQuery }" :aria-label="t('workspace.taskAgentSpace.profile_back')"><Left /><span>Agent</span></router-link><span class="breadcrumb-separator">/</span><h1>{{ creating ? t('workspace.taskAgentSpace.create_agent') : draft?.name || (isBuiltinGeneral ? t('workspace.taskAgentSpace.general_agent') : t('workspace.taskAgentSpace.edit_agent')) }}</h1><span v-if="isBuiltinGeneral" class="builtin-label"><CheckOne />{{ t('workspace.taskAgentSpace.profile_builtin') }}</span></div>
      <div class="detail-header-actions"><span v-if="dirty" class="unsaved-indicator" role="status">{{ t('workspace.taskAgentSpace.profile_unsaved_label') }}</span><router-link v-if="draft && !creating && !failed" :to="{ name: 'taskAgentWorkbench', query: { agent_id: draft.agent_id } }"><IconButton :disabled="saving" :text="t('workspace.taskAgentSpace.use_agent')"><template #icon><PlayOne /></template></IconButton></router-link><router-link v-if="draft && !creating && !failed" :to="{ name: 'taskAgentCreate', query: { ...listQuery, copy: draft.agent_id } }"><IconButton :disabled="saving" :text="t('workspace.taskAgentSpace.profile_copy_edit')"><template #icon><Copy /></template></IconButton></router-link><IconButton type="primary" :loading="saving" :disabled="loading || !draft || failed || missing" @click="save" :text="t('workspace.taskAgentSpace.save_agent')"><template #icon><Save /></template></IconButton></div>
    </header>
    <div class="agent-detail-content">
      <div v-if="loading" class="detail-loading"><a-spin /></div>
      <a-result v-else-if="missing" status="404" :title="t('workspace.taskAgentSpace.profile_not_found')"><template #extra><router-link :to="{ name: 'taskAgentAgents', query: listQuery }"><a-button>{{ t('workspace.taskAgentSpace.profile_back') }}</a-button></router-link></template></a-result>
      <a-alert v-else-if="failed" type="warning" show-icon :message="t('workspace.taskAgentSpace.load_failed')"><template #action><IconButton @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
      <template v-else-if="draft">
        <TaskAgentModelError v-if="modelFailure" class="detail-save-error" :failure="modelFailure" />
        <a-alert v-if="saveError" class="detail-save-error" type="error" show-icon :message="saveError" role="alert" />
        <a-form ref="form" :model="draft" :rules="rules" layout="vertical" :disabled="saving" class="agent-detail-form" @finish="save">
          <aside class="configuration-sidebar">
            <section class="configuration-section"><h2><User />{{ t('workspace.taskAgentSpace.profile_basic') }}</h2><div class="section-body"><div class="profile-avatar"><Robot :size="32" /><span>{{ draft.name || t('workspace.taskAgentSpace.create_agent') }}</span></div><a-form-item name="name" :label="t('workspace.taskAgentSpace.agent_name')" required><a-input v-model:value="draft.name" :maxlength="80" show-count :aria-label="t('workspace.taskAgentSpace.agent_name')" /></a-form-item><a-form-item name="description" :label="t('workspace.taskAgentSpace.agent_description')"><a-textarea v-model:value="draft.description" :rows="3" :maxlength="500" show-count :aria-label="t('workspace.taskAgentSpace.agent_description')" :placeholder="t('workspace.taskAgentSpace.profile_description_hint')" /></a-form-item></div></section>
            <section class="configuration-section"><h2><Setting />{{ t('workspace.taskAgentSpace.profile_model') }}</h2><div class="section-body"><div class="model-setting"><ModelPicker v-model:model="draft.model" v-model:model-provider="draft.model_provider" v-model:preference="preference" v-model:reasoning-effort="draft.reasoning_effort" :options="modelOptions" :disabled="saving" :ready="!catalog.loadError" /></div><p class="field-help">{{ draft.model ? t('workspace.taskAgentSpace.profile_model_hint') : t('workspace.taskAgentSpace.profile_follow_model_hint') }}</p><a-typography-text v-if="!modelReady" type="danger">{{ t('components.model_selector.model_unavailable') }}</a-typography-text><IconButton v-if="draft.model" class="follow-model-button" :disabled="saving" @click="resetModel" :text="t('workspace.taskAgentSpace.profile_follow_model')"><template #icon><Undo /></template></IconButton><div class="cycle-setting"><div class="cycle-limit-label"><span>{{ t('workspace.taskAgentSpace.max_cycles') }}</span><a-switch v-model:checked="cycleLimitEnabled" size="small" :disabled="saving" :aria-label="t('workspace.taskAgentSpace.enable_cycle_limit')" /></div><a-form-item v-if="cycleLimitEnabled" name="max_cycles"><a-input-number v-model:value="draft.max_cycles" :min="1" :max="4294967295" :precision="0" style="width: 100%" :aria-label="t('workspace.taskAgentSpace.max_cycles')" /></a-form-item><p v-else class="field-help cycle-unlimited">{{ t('workspace.taskAgentSpace.cycles_unlimited_hint') }}</p></div></div></section>
            <section class="configuration-section"><h2><CheckOne />{{ t('workspace.taskAgentSpace.permissions') }}</h2><div class="section-body"><TaskAgentPermissions v-model="draft.permission_mode" :disabled="saving" /><p class="field-help">{{ t('workspace.taskAgentSpace.permission_scope') }}</p></div></section>
          </aside>
          <div class="configuration-main">
            <section class="configuration-section instructions-section"><h2><Code />{{ t('workspace.taskAgentSpace.agent_instructions') }}</h2><div class="section-body"><p class="field-help">{{ t('workspace.taskAgentSpace.agent_instructions_hint') }}</p><a-form-item name="instructions" :required="!isBuiltinGeneral"><a-textarea v-model:value="draft.instructions" :aria-label="t('workspace.taskAgentSpace.agent_instructions')" :placeholder="isBuiltinGeneral ? t('workspace.taskAgentSpace.general_description') : t('workspace.taskAgentSpace.profile_instructions_example')" :rows="13" :maxlength="16000" show-count class="instructions-input" /></a-form-item></div></section>
            <section class="configuration-section capabilities-section"><h2><Tool />{{ t('workspace.taskAgentSpace.profile_capabilities') }}</h2><div class="section-body"><a-tabs v-model:activeKey="capabilityTab"><a-tab-pane key="knowledge" :tab="t('knowledgeBase.title')"><KnowledgeBasePicker v-model="draft.knowledge_base_ids" :disabled="saving" /></a-tab-pane><a-tab-pane key="tools" :tab="t('workspace.taskAgentSpace.profile_builtin_tools')"><div class="tool-setting"><div><strong>{{ t('workspace.taskAgentSpace.allow_shell') }}</strong><p>{{ t('workspace.taskAgentSpace.shell_hint') }}</p></div><a-switch v-model:checked="draft.allow_shell" :aria-label="t('workspace.taskAgentSpace.allow_shell')" /></div><a-form-item v-if="draft.allow_shell" class="shell-setting" :label="t('workspace.taskAgentSpace.shell_type')"><a-select v-model:value="draft.shell" :aria-label="t('workspace.taskAgentSpace.shell_type')" :options="[{ value: 'auto', label: t('workspace.taskAgentSpace.shell_auto') }, { value: 'git-bash', label: 'Git Bash' }, { value: 'bash', label: 'Bash' }, { value: 'pwsh', label: 'PowerShell 7' }, { value: 'powershell', label: 'Windows PowerShell' }]" /></a-form-item><div class="tool-setting"><div><strong>{{ t('workspace.taskAgentSpace.allow_file_writes') }}</strong><p>{{ t('workspace.taskAgentSpace.profile_file_writes_hint') }}</p></div><a-switch v-model:checked="draft.allow_file_writes" :aria-label="t('workspace.taskAgentSpace.allow_file_writes')" /></div><div class="tool-setting"><div><strong>{{ t('workspace.taskAgentSpace.allow_sub_agents') }}</strong><p>{{ t('workspace.taskAgentSpace.sub_agents_hint') }}</p></div><a-switch v-model:checked="draft.allow_sub_agents" :aria-label="t('workspace.taskAgentSpace.allow_sub_agents')" /></div></a-tab-pane><a-tab-pane key="workflows"><template #tab>{{ t('workspace.taskAgentSpace.workflows') }}<span class="workflow-count">{{ draft.workflow_ids.length }}</span></template><p class="field-help">{{ t('workspace.taskAgentSpace.workflows_description') }}</p><a-form-item name="workflow_ids"><a-select v-model:value="draft.workflow_ids" mode="multiple" :aria-label="t('workspace.taskAgentSpace.workflows')" :options="workflowOptions" option-filter-prop="label" allow-clear :placeholder="t('workspace.taskAgentSpace.profile_select_workflows')" /></a-form-item></a-tab-pane><a-tab-pane key="skills"><template #tab>{{ t('workspace.taskAgentSpace.skills_navigation') }}<span class="workflow-count">{{ (draft.skill_ids || []).length }}</span></template><div class="capability-tab-header"><p class="field-help">{{ t('workspace.taskAgentSpace.profile_skills_description') }}</p><div class="capability-tab-links"><IconButton v-if="unavailableSkillIds.length" size="small" danger :disabled="saving" @click="removeUnavailableSkills" :text="t('workspace.taskAgentSpace.profile_remove_unavailable')"><template #icon><Delete /></template></IconButton><router-link :to="{ name: 'taskAgentSkills' }">{{ t('workspace.taskAgentSpace.profile_manage_skills') }}</router-link></div></div><a-alert v-if="skillsFailed" class="capability-load-alert skills-load-alert" type="warning" show-icon :message="t('workspace.taskAgentSpace.profile_skills_load_failed')"><template #action><IconButton size="small" :loading="skillsLoading" :disabled="saving" @click="reloadSkillsCatalog" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert><a-form-item name="skill_ids"><a-select v-model:value="draft.skill_ids" mode="multiple" :aria-label="t('workspace.taskAgentSpace.skills_navigation')" :options="skillOptions" option-filter-prop="label" allow-clear :placeholder="t('workspace.taskAgentSpace.profile_select_skills')" /></a-form-item></a-tab-pane><a-tab-pane key="mcp"><template #tab>{{ t('workspace.taskAgentSpace.mcp_navigation') }}<span class="workflow-count">{{ (draft.mcp_tool_ids || []).length }}</span></template><div class="capability-tab-header"><p class="field-help">{{ t('workspace.taskAgentSpace.profile_mcp_description') }}</p><div class="capability-tab-links"><IconButton v-if="unavailableMcpToolIds.length" size="small" danger :disabled="saving" @click="removeUnavailableMcpTools" :text="t('workspace.taskAgentSpace.profile_remove_unavailable')"><template #icon><Delete /></template></IconButton><router-link :to="{ name: 'taskAgentMCP' }">{{ t('workspace.taskAgentSpace.profile_manage_mcp') }}</router-link></div></div><a-alert v-if="mcpFailed" class="capability-load-alert mcp-load-alert" type="warning" show-icon :message="t('workspace.taskAgentSpace.profile_mcp_load_failed')"><template #action><IconButton size="small" :loading="mcpLoading" :disabled="saving" @click="reloadMcpToolsCatalog" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert><a-form-item name="mcp_tool_ids"><a-select v-model:value="draft.mcp_tool_ids" mode="multiple" :aria-label="t('workspace.taskAgentSpace.mcp_navigation')" :options="mcpToolOptions" option-filter-prop="label" allow-clear :placeholder="t('workspace.taskAgentSpace.profile_select_mcp')" /></a-form-item></a-tab-pane></a-tabs></div></section>
          </div>
        </a-form>
      </template>
    </div>
  </main>
</template>

<style scoped>
.agent-detail-page { display: flex; height: 100%; min-width: 0; flex-direction: column; color: var(--site-text-color); }
.agent-detail-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 64px; gap: 20px; padding: 12px 24px; background: var(--component-background); border-bottom: var(--light-border); }
.detail-breadcrumb { display: flex; align-items: center; gap: 12px; min-width: 0; }
.detail-breadcrumb > a { display: inline-flex; align-items: center; gap: 8px; color: var(--site-secondary-text-color); white-space: nowrap; }
.detail-breadcrumb svg { height: 16px; width: 16px; flex-shrink: 0; }
.breadcrumb-separator { color: var(--site-secondary-text-color); }
h1 { margin: 0; font-size: 16px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.builtin-label { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-primary); white-space: nowrap; }
.detail-header-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.unsaved-indicator { font-size: 12px; color: var(--site-secondary-text-color); }
.agent-detail-content { flex: 1; min-height: 0; padding: 24px; background: var(--gray-background); overflow: auto; }
.agent-detail-form { display: grid; grid-template-columns: minmax(280px, 340px) minmax(0, 1fr); gap: 24px; max-width: 1560px; margin: 0 auto; align-items: start; }
.configuration-sidebar, .configuration-main { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.configuration-section { min-width: 0; background: var(--component-background); border: 1px solid color-mix(in srgb, var(--site-text-color) 7%, transparent); border-radius: 8px; }
h2 { display: flex; align-items: center; gap: 8px; margin: 0; padding: 15px 20px; border-bottom: var(--light-border); font-size: 14px; font-weight: 500; }
h2 svg { width: 16px; height: 16px; color: var(--site-secondary-text-color); }
.section-body { padding: 20px; }
.section-body > :last-child { margin-bottom: 0; }
.profile-avatar { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; min-width: 0; }
.profile-avatar > svg { box-sizing: content-box; width: 32px; height: 32px; padding: 14px; border: var(--light-border); border-radius: 10px; background: color-mix(in srgb, var(--color-primary) 7%, var(--component-background)); color: var(--color-primary); flex-shrink: 0; }
.profile-avatar span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; font-size: 15px; }
.field-help { color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.75; margin: 0 0 12px; overflow-wrap: anywhere; }
.model-setting { border: var(--light-border); border-radius: 6px; padding: 5px 8px; margin-bottom: 12px; }
.model-setting :deep(.model-picker) { width: 100%; }
:deep(.follow-model-button) { margin-bottom: 16px; }
.cycle-setting { margin-top: 20px; }
.cycle-limit-label { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 14px; }
.cycle-unlimited { margin: 0; }
.instructions-section :deep(.ant-input) { min-height: 310px; line-height: 1.8; font-size: 14px; resize: vertical; }
.instructions-section .section-body { padding-bottom: 28px; }
.capabilities-section .section-body { padding-top: 0; }
.capabilities-section :deep(.ant-tabs-nav) { margin-bottom: 0; }
.tool-setting { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 18px 0; border-bottom: var(--light-border); }
.tool-setting:last-child { border-bottom: 0; padding-bottom: 0; }
.tool-setting > div { min-width: 0; }
.tool-setting strong { font-size: 14px; font-weight: 500; }
.tool-setting p { margin: 6px 0 0; color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.7; max-width: 68em; }
.tool-setting :deep(.ant-switch) { flex-shrink: 0; }
.shell-setting { margin: 14px 0; max-width: 300px; }
.workflow-count { margin-left: 6px; padding: 1px 6px; border-radius: 8px; background: var(--gray-background); font-size: 11px; color: var(--site-secondary-text-color); }
.capabilities-section :deep(.ant-tabs-tabpane) > .field-help { margin-top: 18px; }
.capability-tab-header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-top: 18px; margin-bottom: 12px; flex-wrap: wrap; }
.capability-tab-header .field-help { margin: 0; flex: 1; min-width: 220px; }
.capability-tab-links { display: flex; align-items: center; gap: 12px; font-size: 12px; white-space: nowrap; }
.capability-load-alert { margin-bottom: 12px; }
.detail-loading { text-align: center; padding: 100px 20px; }
.detail-save-error { max-width: 1560px; margin: 0 auto 20px; }
@media (max-width: 1100px) { .agent-detail-form { grid-template-columns: minmax(250px, 300px) minmax(0, 1fr); gap: 16px; } .agent-detail-content { padding: 16px; } .section-body { padding: 16px; } .unsaved-indicator { display: none; } }
@media (max-width: 850px) { .agent-detail-form { grid-template-columns: minmax(0, 1fr); } .agent-detail-header { flex-wrap: wrap; padding: 12px 16px; } .detail-header-actions { margin-left: auto; } }
</style>
