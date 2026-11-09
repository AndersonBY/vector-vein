<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, provide, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Home, ListOne, Calendar, Robot, BookOpen, Connection, ExpandLeft, ExpandRight } from '@/icons'
import TaskAgentProjectNavigation from './TaskAgentProjectNavigation.vue'

const collapsed = ref(false)
try { collapsed.value = localStorage.getItem('task-agent-sidebar-collapsed') === 'true' } catch { /* Storage is optional. */ }
const toggleSidebar = () => { collapsed.value = !collapsed.value; try { localStorage.setItem('task-agent-sidebar-collapsed', String(collapsed.value)) } catch { /* Storage is optional. */ } }
const route = useRoute()
const { t } = useI18n()
const activeSection = computed(() => route.meta.taskAgentSection || 'workbench')
const projectContext = ref(''), projectNavigation = ref(null)
const projectDeletion = ref(null)
const workbenchComposerDraft = ref(null)
provide('taskAgentWorkbenchDraft', workbenchComposerDraft)
provide('taskAgentProjectContext', projectContext)
provide('taskAgentProjectDeletion', projectDeletion)
provide('refreshTaskAgentProjects', () => projectNavigation.value?.refresh())
</script>

<template>
  <div class="task-agent-space" :class="{ 'sidebar-collapsed': collapsed }">
    <aside class="task-agent-sidebar">
      <nav class="task-agent-navigation" :aria-label="t('workspace.taskAgentSpace.navigation')">
        <router-link
          :to="{ name: 'taskAgentWorkbench' }"
          class="task-agent-nav-item"
          :aria-label="t('workspace.taskAgentSpace.workbench')" :title="t('workspace.taskAgentSpace.workbench')"
          :class="{ active: activeSection === 'workbench' }">
          <Home />
          <span>{{ t('workspace.taskAgentSpace.workbench') }}</span>
        </router-link>
        <router-link
          :to="{ name: 'taskAgentTasks' }"
          class="task-agent-nav-item"
          :aria-label="t('workspace.taskAgentSpace.tasks')" :title="t('workspace.taskAgentSpace.tasks')"
          :class="{ active: activeSection === 'tasks' }">
          <ListOne />
          <span>{{ t('workspace.taskAgentSpace.tasks') }}</span>
        </router-link>
        <router-link :to="{ name: 'taskAgentSchedules' }" class="task-agent-nav-item" :aria-label="t('workspace.taskAgentSpace.scheduling.title')" :title="t('workspace.taskAgentSpace.scheduling.title')" :class="{ active: activeSection === 'schedules' }"><Calendar /><span>{{ t('workspace.taskAgentSpace.scheduling.title') }}</span></router-link>
        <router-link :to="{ name: 'taskAgentAgents' }" class="task-agent-nav-item" :aria-label="t('workspace.taskAgentSpace.profile_navigation')" :title="t('workspace.taskAgentSpace.profile_navigation')" :class="{ active: activeSection === 'agents' }"><Robot /><span>{{ t('workspace.taskAgentSpace.profile_navigation') }}</span></router-link>
        <router-link :to="{ name: 'taskAgentSkills' }" class="task-agent-nav-item" :aria-label="t('workspace.taskAgentSpace.skills_navigation')" :title="t('workspace.taskAgentSpace.skills_navigation')" :class="{ active: activeSection === 'skills' }"><BookOpen /><span>{{ t('workspace.taskAgentSpace.skills_navigation') }}</span></router-link>
        <router-link :to="{ name: 'taskAgentMCP' }" class="task-agent-nav-item" :aria-label="t('workspace.taskAgentSpace.mcp_navigation')" :title="t('workspace.taskAgentSpace.mcp_navigation')" :class="{ active: activeSection === 'mcp' }"><Connection /><span>{{ t('workspace.taskAgentSpace.mcp_navigation') }}</span></router-link>
      </nav>
      <TaskAgentProjectNavigation ref="projectNavigation" class="sidebar-projects" :active-project-id="String(route.params.projectId || route.query.project_id || projectContext || '')" @deleted="projectDeletion = $event" />
      <div class="sidebar-collapse-action"><IconButton class="sidebar-collapse" :aria-label="t(collapsed ? 'workspace.taskAgentSpace.expand_sidebar' : 'workspace.taskAgentSpace.collapse_sidebar')" :aria-pressed="collapsed" @click="toggleSidebar" size="small" :text="t(collapsed ? 'workspace.taskAgentSpace.expand_sidebar' : 'workspace.taskAgentSpace.collapse_sidebar')"><template #icon><ExpandRight v-if="collapsed" /><ExpandLeft v-else /></template></IconButton></div>
    </aside>
    <div class="task-agent-content">
      <router-view />
    </div>
  </div>
</template>

<style scoped>
.task-agent-space {
  display: flex;
  height: calc(100dvh - 64px);
  min-height: 0;
  overflow: hidden;
  color: var(--site-text-color);
  background: var(--component-background);
}
.task-agent-sidebar {
  display: flex; flex-direction: column;
  width: 220px;
  flex: 0 0 220px;
  border-right: var(--light-border);
  background: var(--gray-background);
}
.task-agent-navigation {
  flex-shrink: 0;
  display: flex;
  padding: 8px;
  flex-direction: column;
  gap: 3px;
}
.task-agent-nav-item {
  display: flex;
  height: 38px;
  padding: 0 10px;
  align-items: center;
  gap: 10px;
  border-radius: 6px;
  color: var(--site-text-color);
  font-size: 14px;
  text-decoration: none;
  transition: background-color 140ms ease, color 140ms ease;
}
.task-agent-nav-item:hover {
  background: color-mix(in srgb, var(--site-text-color) 7%, transparent);
}
.task-agent-nav-item.active {
  color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 12%, transparent);
}
.task-agent-content {
  min-width: 0;
  flex: 1;
  overflow-y: auto;
}
.sidebar-collapse-action { margin: auto 12px 14px; }
:deep(.sidebar-collapse) { display: grid; place-items: center; margin: 0; border: 0; border-radius: 5px; background: transparent; color: var(--site-secondary-text-color); cursor: pointer; }
:deep(.sidebar-collapse):focus-visible { outline: 2px solid var(--color-primary); }
.sidebar-collapsed .task-agent-sidebar { width: 56px; flex-basis: 56px; }
.sidebar-collapsed .task-agent-nav-item { justify-content: center; padding-inline: 0; }
.sidebar-collapsed .task-agent-nav-item span { display: none; }
.sidebar-collapsed .sidebar-projects { display: none; }
@media (max-width: 760px) {
  .task-agent-sidebar {
  display: flex; flex-direction: column;
    width: 60px;
    flex-basis: 60px;
  }
  .task-agent-nav-item {
    justify-content: center;
  }
  .task-agent-nav-item span {
    display: none;
  }
  .sidebar-projects { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .task-agent-nav-item { transition: none; }
}
</style>
