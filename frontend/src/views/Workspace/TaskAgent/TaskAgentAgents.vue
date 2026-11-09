<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Add, Robot, Search, Control, ToTop, ToBottom, Star, PlayOne, Edit, Tool, ViewGridCard, ListOne, CheckOne, Close, Refresh } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatTaskTime } from '@/utils/taskAgentPresentation'

const { t, locale } = useI18n()
const route = useRoute(), router = useRouter()
const agents = ref([]), loading = ref(true), failed = ref(false)
const search = ref(String(route.query.search || ''))
const favorites = ref([])
try { const saved = JSON.parse(localStorage.getItem('task-agent-favorite-profiles') || '[]'); if (Array.isArray(saved)) favorites.value = saved.filter(value => typeof value === 'string') } catch { /* Storage is optional. */ }
const tab = computed(() => route.query.tab === 'favorites' ? 'favorites' : 'agents')
const filter = computed(() => ['shell', 'sub_agents', 'workflows', 'skills', 'mcp'].includes(route.query.filter) ? route.query.filter : 'all')
const sort = computed(() => ['name', 'oldest'].includes(route.query.sort) ? route.query.sort : 'recent')
const view = computed(() => route.query.view === 'list' ? 'list' : 'grid')
const page = computed(() => Math.max(1, Number.parseInt(route.query.page, 10) || 1))
const pageSize = 24
const nameOf = agent => agent.name || t('workspace.taskAgentSpace.general_agent')
const descriptionOf = agent => agent.description || (agent.agent_id === 'general' ? t('workspace.taskAgentSpace.general_description') : t('workspace.taskAgentSpace.profile_no_description'))
const isFavorite = agent => favorites.value.includes(agent.agent_id)
const favoriteCount = computed(() => agents.value.filter(isFavorite).length)
const updateQuery = patch => {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key] || (key === 'page' && Number(query[key]) === 1)) delete query[key]
  return router.replace({ name: 'taskAgentAgents', query })
}
const toggleFavorite = agent => {
  favorites.value = isFavorite(agent) ? favorites.value.filter(value => value !== agent.agent_id) : [...favorites.value, agent.agent_id]
  try { localStorage.setItem('task-agent-favorite-profiles', JSON.stringify(favorites.value)) } catch { /* Storage is optional. */ }
}
const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return agents.value.filter(agent => (tab.value !== 'favorites' || isFavorite(agent)) &&
    (!query || `${nameOf(agent)} ${descriptionOf(agent)}`.toLocaleLowerCase().includes(query)) &&
    (filter.value === 'all' || (filter.value === 'shell' && agent.allow_shell) || (filter.value === 'sub_agents' && agent.allow_sub_agents) || (filter.value === 'workflows' && agent.workflow_ids?.length) || (filter.value === 'skills' && agent.skill_ids?.length) || (filter.value === 'mcp' && agent.mcp_tool_ids?.length)))
    .sort((left, right) => sort.value === 'name' ? nameOf(left).localeCompare(nameOf(right), locale.value) :
      ((Date.parse(right.updated_at || '') || 0) - (Date.parse(left.updated_at || '') || 0)) * (sort.value === 'oldest' ? -1 : 1) || nameOf(left).localeCompare(nameOf(right), locale.value))
})
const currentPage = computed(() => Math.min(page.value, Math.max(1, Math.ceil(filtered.value.length / pageSize))))
const visible = computed(() => filtered.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize))
const filters = computed(() => ['all', 'shell', 'sub_agents', 'workflows', 'skills', 'mcp'].map(key => ({ key, label: t('workspace.taskAgentSpace.profile_filter_' + key) })))
let alive = true, generation = 0, searchTimer = null
const load = async () => {
  const version = ++generation
  loading.value = true; failed.value = false
  try {
    const response = await taskAgentAPI('profiles')
    if (!alive || version !== generation) return
    if (response.status !== 200 || !Array.isArray(response.data.agents)) throw new Error()
    agents.value = response.data.agents
  } catch { if (alive && version === generation) failed.value = true }
  finally { if (alive && version === generation) loading.value = false }
}
watch(search, value => {
  clearTimeout(searchTimer)
  if (value === String(route.query.search || '')) return
  searchTimer = setTimeout(() => updateQuery({ search: value.trim() || undefined, page: undefined }), 200)
})
watch(() => route.query.search, value => { clearTimeout(searchTimer); search.value = String(value || '') })
onMounted(load)
onBeforeUnmount(() => { alive = false; clearTimeout(searchTimer) })
</script>

<template>
  <main class="agent-catalog">
    <header class="catalog-header"><div class="catalog-title"><h1>Agent</h1><span>{{ t('workspace.taskAgentSpace.profile_total', { count: agents.length }) }}</span></div><router-link :to="{ name: 'taskAgentCreate', query: route.query }"><IconButton type="primary" :text="t('workspace.taskAgentSpace.create_agent')"><template #icon><Add /></template></IconButton></router-link></header>
    <a-tabs class="catalog-tabs" :active-key="tab" @change="value => updateQuery({ tab: value === 'agents' ? undefined : value, page: undefined })">
      <a-tab-pane key="agents"><template #tab>{{ t('workspace.taskAgentSpace.agents') }}<span class="tab-count">{{ agents.length }}</span></template></a-tab-pane>
      <a-tab-pane key="favorites"><template #tab>{{ t('workspace.taskAgentSpace.profile_favorites') }}<span class="tab-count">{{ favoriteCount }}</span></template></a-tab-pane>
    </a-tabs>
    <div class="catalog-toolbar">
      <a-input v-model:value="search" class="catalog-search" allow-clear :aria-label="t('workspace.taskAgentSpace.profile_search')" :placeholder="t('workspace.taskAgentSpace.profile_search')"><template #prefix><Search /></template></a-input>
      <a-dropdown :trigger="['click']"><IconButton :class="{ 'filter-active': filter !== 'all' }" :text="filter === 'all' ? t('workspace.taskAgentSpace.profile_filter') : t('workspace.taskAgentSpace.profile_filter_' + filter)"><template #icon><Control /></template></IconButton><template #overlay><a-menu :selected-keys="[filter]" :items="filters" @click="({ key }) => updateQuery({ filter: key === 'all' ? undefined : key, page: undefined })" /></template></a-dropdown>
      <a-dropdown :trigger="['click']"><IconButton :text="t('workspace.taskAgentSpace.profile_sort_' + sort)"><template #icon><ToTop v-if="sort === 'oldest'" /><ToBottom v-else /></template></IconButton><template #overlay><a-menu :selected-keys="[sort]" @click="({ key }) => updateQuery({ sort: key === 'recent' ? undefined : key, page: undefined })"><a-menu-item v-for="key in ['recent', 'oldest', 'name']" :key="key">{{ t('workspace.taskAgentSpace.profile_sort_' + key) }}</a-menu-item></a-menu></template></a-dropdown>
      <div class="catalog-view" role="group" :aria-label="t('workspace.taskAgentSpace.profile_view')"><IconButton size="small" type="text" :class="{ selected: view === 'grid' }" :aria-label="t('workspace.taskAgentSpace.profile_grid')" :aria-pressed="view === 'grid'" @click="updateQuery({ view: undefined })" :text="t('workspace.taskAgentSpace.profile_grid')"><template #icon><ViewGridCard /></template></IconButton><IconButton size="small" type="text" :class="{ selected: view === 'list' }" :aria-label="t('workspace.taskAgentSpace.profile_list')" :aria-pressed="view === 'list'" @click="updateQuery({ view: 'list' })" :text="t('workspace.taskAgentSpace.profile_list')"><template #icon><ListOne /></template></IconButton></div>
    </div>
    <section class="catalog-content" :aria-busy="loading">
      <a-alert v-if="failed" type="warning" show-icon :message="t('workspace.taskAgentSpace.load_failed')"><template #action><IconButton @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
      <div v-if="loading && !agents.length" class="catalog-loading"><a-spin /></div>
      <template v-else>
        <p class="catalog-summary" aria-live="polite">{{ t('workspace.taskAgentSpace.profile_showing', { count: filtered.length }) }}</p>
        <div v-if="visible.length" class="agent-grid" :class="{ 'list-view': view === 'list' }">
          <article v-for="agent in visible" :key="agent.agent_id" class="agent-card">
            <router-link class="agent-card-link" :to="{ name: 'taskAgentEdit', params: { agentId: agent.agent_id }, query: route.query }" :aria-label="t('workspace.taskAgentSpace.profile_configure_name', { name: nameOf(agent) })">
              <div class="card-top"><div class="agent-avatar"><Robot v-if="agent.agent_id === 'general'" :size="24" /><span v-else>{{ [...nameOf(agent)].slice(0, 2).join('') }}</span></div><div class="card-copy"><div class="card-heading"><h2>{{ nameOf(agent) }}</h2><span v-if="agent.agent_id === 'general'" class="builtin-badge"><CheckOne />{{ t('workspace.taskAgentSpace.profile_builtin') }}</span></div><p class="agent-description">{{ descriptionOf(agent) }}</p></div></div>
              <div class="card-meta"><span><Robot />Agent</span><span v-if="agent.allow_shell"><Tool />Bash</span><span v-if="agent.allow_sub_agents"><Robot />{{ t('workspace.taskAgentSpace.sub_agent') }}</span><span v-if="agent.workflow_ids?.length"><Tool />{{ t('workspace.taskAgentSpace.profile_workflow_count', { count: agent.workflow_ids.length }) }}</span><span v-if="agent.skill_ids?.length"><Tool />{{ t('workspace.taskAgentSpace.profile_skill_count', { count: agent.skill_ids.length }) }}</span><span v-if="agent.mcp_tool_ids?.length"><Tool />{{ t('workspace.taskAgentSpace.profile_mcp_count', { count: agent.mcp_tool_ids.length }) }}</span></div>
              <footer class="card-footer"><span class="model-label" :title="agent.model || t('workspace.taskAgentSpace.profile_follow_model')"><i />{{ agent.model || t('workspace.taskAgentSpace.profile_follow_model') }}</span><time v-if="agent.updated_at" :datetime="agent.updated_at">{{ formatTaskTime(agent.updated_at, locale) }}</time></footer>
            </router-link>
            <div class="card-actions"><IconButton size="small" type="text" :aria-pressed="isFavorite(agent)" :aria-label="t(isFavorite(agent) ? 'workspace.taskAgentSpace.profile_unfavorite' : 'workspace.taskAgentSpace.profile_favorite')" @click="toggleFavorite(agent)" :text="t(isFavorite(agent) ? 'workspace.taskAgentSpace.profile_unfavorite' : 'workspace.taskAgentSpace.profile_favorite')"><template #icon><Star :theme="isFavorite(agent) ? 'filled' : 'outline'" /></template></IconButton><a-tooltip :title="t('workspace.taskAgentSpace.edit_agent')"><router-link :to="{ name: 'taskAgentEdit', params: { agentId: agent.agent_id }, query: route.query }" :aria-label="t('workspace.taskAgentSpace.edit_agent')"><Edit /></router-link></a-tooltip><a-tooltip :title="t('workspace.taskAgentSpace.use_agent')"><router-link :to="{ name: 'taskAgentWorkbench', query: { agent_id: agent.agent_id } }" :aria-label="t('workspace.taskAgentSpace.use_agent')"><PlayOne /></router-link></a-tooltip></div>
          </article>
        </div>
        <a-empty v-else :description="t(tab === 'favorites' && !search && filter === 'all' ? 'workspace.taskAgentSpace.profile_no_favorites' : 'workspace.taskAgentSpace.profile_no_results')" class="catalog-empty"><IconButton v-if="search || filter !== 'all'" @click="search = ''; updateQuery({ search: undefined, filter: undefined, page: undefined })" :text="t('workspace.taskAgentSpace.profile_clear_filters')"><template #icon><Close /></template></IconButton></a-empty>
        <a-pagination v-if="filtered.length > pageSize" class="catalog-pagination" :current="currentPage" :page-size="pageSize" :total="filtered.length" :show-size-changer="false" @change="value => updateQuery({ page: String(value) })" />
      </template>
    </section>
  </main>
</template>

<style scoped>
.agent-catalog { height: 100%; display: flex; flex-direction: column; min-width: 0; color: var(--site-text-color); }
.catalog-header { min-height: 52px; padding: 6px 24px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: var(--light-border); background: var(--component-background); }
.catalog-title { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
h1 { margin: 0; font-size: 18px; font-weight: 600; }
.catalog-title > span, .catalog-summary { font-size: 12px; color: var(--site-secondary-text-color); font-variant-numeric: tabular-nums; }
.catalog-tabs { flex-shrink: 0; padding: 0 24px; background: var(--component-background); }
.catalog-tabs :deep(.ant-tabs-nav) { margin: 0; min-height: 46px; }
.catalog-tabs :deep(.ant-tabs-content-holder) { display: none; }
.tab-count { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 8px; background: var(--gray-background); color: var(--site-secondary-text-color); font-size: 11px; line-height: 18px; }
.catalog-toolbar { display: flex; align-items: center; gap: 8px; min-height: 56px; padding: 10px 24px; background: var(--component-background); border-bottom: var(--light-border); flex-shrink: 0; }
.catalog-search { width: 320px; max-width: 40%; }
.catalog-toolbar :deep(.ant-btn) { color: var(--site-secondary-text-color); }
.catalog-toolbar :deep(.filter-active) { color: var(--color-primary); }
.catalog-view { display: flex; gap: 2px; margin-left: auto; border: var(--light-border); padding: 2px; border-radius: 6px; }
.catalog-view :deep(.ant-btn) { width: 28px; height: 26px; padding: 0; }
.catalog-view :deep(.selected) { background: var(--gray-background); color: var(--site-text-color); }
.catalog-content { background: var(--gray-background); flex: 1; min-height: 0; overflow: auto; padding: 12px 24px 24px; }
.catalog-summary { margin: 0 0 8px; }
.agent-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.agent-card { position: relative; min-width: 0; border: 1px solid color-mix(in srgb, var(--site-text-color) 7%, transparent); border-radius: 8px; background: var(--component-background); content-visibility: auto; contain-intrinsic-size: auto 164px; }
.agent-card-link { color: inherit; display: flex; height: 100%; min-height: 164px; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: inherit; }
.card-top { display: flex; align-items: flex-start; gap: 11px; min-width: 0; }
.agent-avatar { width: 40px; height: 40px; flex: 0 0 40px; display: flex; align-items: center; justify-content: center; background: color-mix(in srgb, var(--color-primary) 8%, var(--component-background)); border: var(--light-border); color: color-mix(in srgb, var(--color-primary) 72%, var(--site-text-color)); border-radius: 7px; font-size: 13px; font-weight: 500; }
.card-copy { min-width: 0; flex: 1; }
.card-heading { display: flex; align-items: center; gap: 6px; padding-right: 8px; }
h2 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; font-weight: 600; line-height: 1.5; }
.builtin-badge { display: inline-flex; align-items: center; gap: 3px; white-space: nowrap; font-size: 11px; color: var(--color-primary); }
.builtin-badge :deep(svg) { width: 12px; height: 12px; }
.agent-description { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; overflow-wrap: anywhere; margin: 3px 0 0; color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.7; }
.card-meta { display: flex; flex-wrap: wrap; gap: 10px; color: var(--site-secondary-text-color); font-size: 11px; line-height: 1.5; }
.card-meta span { display: inline-flex; align-items: center; gap: 4px; }
.card-meta :deep(svg) { width: 12px; height: 12px; }
.card-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: auto; min-width: 0; font-size: 11px; color: var(--site-secondary-text-color); }
.model-label { display: inline-flex; min-width: 0; max-width: 72%; align-items: center; gap: 5px; padding: 2px 7px; border-radius: 4px; background: var(--gray-background); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.model-label i { height: 6px; width: 6px; border-radius: 1px; background: var(--color-primary); flex-shrink: 0; }
time { white-space: nowrap; font-variant-numeric: tabular-nums; }
.card-actions { position: absolute; top: 10px; right: 10px; display: flex; align-items: center; gap: 2px; padding: 2px; border-radius: 5px; background: var(--component-background); opacity: 0; pointer-events: none; }
.card-actions :deep(.ant-btn), .card-actions > :deep(a), .card-actions :deep(a) { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; padding: 0; color: var(--site-secondary-text-color); border-radius: 4px; }
.card-actions :deep(svg) { width: 14px; height: 14px; }
.agent-card:focus-within .card-actions { opacity: 1; pointer-events: auto; }
.agent-card-link:focus-visible, .card-actions a:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.catalog-loading, .catalog-empty { padding: 80px 16px; text-align: center; }
.catalog-pagination { margin-top: 24px; text-align: right; }
.list-view { grid-template-columns: minmax(0, 1fr); }
.list-view .agent-card { contain-intrinsic-size: auto 96px; }
.list-view .agent-card-link { min-height: 96px; display: grid; grid-template-columns: minmax(240px, 1.6fr) minmax(150px, 1fr) minmax(160px, 1fr); align-items: center; gap: 20px; }
.list-view .card-footer { flex-wrap: wrap; justify-content: flex-end; padding-right: 90px; }
@media (hover: hover) and (pointer: fine) { .agent-card:hover { border-color: color-mix(in srgb, var(--site-text-color) 22%, transparent); } .agent-card:hover .card-actions { opacity: 1; pointer-events: auto; } .card-actions :deep(a:hover) { background: var(--gray-background); color: var(--site-text-color); } }
@media (hover: none) { .card-actions { opacity: 1; pointer-events: auto; } }
@media (max-width: 1250px) { .agent-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .list-view { grid-template-columns: minmax(0, 1fr); } .list-view .agent-card-link { grid-template-columns: minmax(0, 1fr) minmax(140px, .8fr); } .list-view .card-meta { display: none; } }
@media (max-width: 850px) { .catalog-header, .catalog-toolbar { padding-left: 16px; padding-right: 16px; } .catalog-tabs { padding: 0 16px; } .catalog-content { padding-left: 16px; padding-right: 16px; } .agent-grid { grid-template-columns: minmax(0, 1fr); } .catalog-toolbar { flex-wrap: wrap; } .catalog-search { max-width: none; flex: 1; min-width: 180px; } .list-view .agent-card-link { display: flex; align-items: stretch; } .list-view .card-footer { padding-right: 0; } }
</style>
