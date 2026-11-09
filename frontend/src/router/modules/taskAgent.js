export const taskAgentSpaceRoute = {
  path: 'task-agent',
  name: 'taskAgentSpace',
  meta: {
    title: 'router.workspace.children.task_agent_space',
    headerKey: 'task-agent',
  },
  redirect: { name: 'taskAgentWorkbench' },
  component: () => import('@/views/Workspace/TaskAgent/TaskAgentSpace.vue'),
  children: [
    {
      path: 'projects/:projectId', name: 'taskAgentProject',
      meta: { title: 'router.workspace.children.task_agent_projects', taskAgentSection: 'projects' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentWorkbench.vue'),
    },
    {
      path: 'agents',
      name: 'taskAgentAgents',
      meta: { title: 'router.workspace.children.task_agent_agents', taskAgentSection: 'agents' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentAgents.vue'),
    },
    {
      path: 'agents/new',
      name: 'taskAgentCreate',
      meta: { title: 'router.workspace.children.task_agent_create', taskAgentSection: 'agents' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentAgentDetail.vue'),
    },
    {
      path: 'agents/:agentId',
      name: 'taskAgentEdit',
      meta: { title: 'router.workspace.children.task_agent_edit', taskAgentSection: 'agents' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentAgentDetail.vue'),
    },
    {
      path: 'skills',
      name: 'taskAgentSkills',
      meta: { title: 'router.workspace.children.task_agent_skills', taskAgentSection: 'skills' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentSkills.vue'),
    },
    {
      path: 'skills/new',
      name: 'taskAgentSkillCreate',
      meta: { title: 'router.workspace.children.task_agent_skill_create', taskAgentSection: 'skills' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentSkillDetail.vue'),
    },
    {
      path: 'skills/:skillId',
      name: 'taskAgentSkillDetail',
      meta: { title: 'router.workspace.children.task_agent_skill_detail', taskAgentSection: 'skills' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentSkillDetail.vue'),
    },
    {
      path: 'mcp',
      name: 'taskAgentMCP',
      meta: { title: 'router.workspace.children.task_agent_mcp', taskAgentSection: 'mcp' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentMCPServers.vue'),
    },
    {
      path: 'workbench',
      name: 'taskAgentWorkbench',
      meta: { title: 'router.workspace.children.task_agent_workbench', taskAgentSection: 'workbench' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentWorkbench.vue'),
    },
    {
      path: 'schedules',
      name: 'taskAgentSchedules',
      meta: { title: 'router.workspace.children.task_agent_schedules', taskAgentSection: 'schedules' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentSchedules.vue'),
    },
    {
      path: 'tasks',
      name: 'taskAgentTasks',
      meta: { title: 'router.workspace.children.task_agent_tasks', taskAgentSection: 'tasks' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentTasks.vue'),
    },
    {
      path: 'task/:taskId',
      name: 'taskAgentDetail',
      meta: { title: 'router.workspace.children.task_agent_detail', taskAgentSection: 'tasks' },
      component: () => import('@/views/Workspace/TaskAgent/TaskAgentDetail.vue'),
    },
  ],
}