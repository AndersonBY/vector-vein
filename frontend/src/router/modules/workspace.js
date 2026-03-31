export const workflowEditorRoute = {
  path: '/workflow/editor/:workflowId',
  name: 'WorkflowEditor',
  meta: {
    login: true,
  },
  component: () => import('@/views/Workspace/WorkflowEditor.vue'),
}

export const workspaceRootRedirectRoute = {
  path: '',
  redirect: '/workflow',
}

export const workflowSpaceRoute = {
  path: 'workflow',
  name: 'WorkflowSpace',
  meta: {
    title: 'router.workspace.children.workflow_space',
    headerKey: 'workflow',
  },
  component: () => import('@/views/Workspace/WorkflowSpace.vue'),
  children: [
    {
      path: '',
      name: 'WorkflowSpaceMain',
      meta: {
        title: 'router.workspace.children.workflow_main',
      },
      component: () => import('@/views/Workspace/WorkflowSpaceMain.vue'),
    },
    {
      path: 'schedule',
      name: 'WorkflowScheduleManager',
      meta: {
        title: 'router.workspace.children.workflow_schedule_manager',
      },
      component: () => import('@/views/Workspace/WorkflowScheduleManager.vue'),
    },
    {
      path: 'trash',
      name: 'WorkflowTrash',
      meta: {
        title: 'router.workspace.children.workflow_trash',
      },
      component: () => import('@/views/Workspace/WorkflowTrash.vue'),
    },
    {
      path: 'template/:workflowTemplateId',
      name: 'WorkflowTemplate',
      meta: {
        title: 'router.workspace.children.workflow_template',
      },
      component: () => import('@/views/Workspace/WorkflowTemplate.vue'),
    },
    {
      path: ':workflowId',
      name: 'WorkflowUse',
      meta: {
        title: 'router.workspace.children.workflow_use',
      },
      component: () => import('@/views/Workspace/WorkflowSpaceUse.vue'),
    },
  ],
}
