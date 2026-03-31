export const agentChatRoute = {
  path: 'agent/:agentId/chat',
  name: 'chatSpace',
  meta: {
    title: 'router.workspace.children.chat_space',
    headerKey: 'agent',
  },
  component: () => import('@/views/Workspace/Chat/ChatSpace.vue'),
  children: [
    {
      path: '',
      name: 'conversationNew',
      meta: {
        title: 'router.workspace.children.conversation_detail',
      },
      component: () => import('@/views/Workspace/Chat/ConversationNew.vue'),
    },
    {
      path: ':conversationId',
      name: 'conversationDetail',
      meta: {
        title: 'router.workspace.children.conversation_detail',
      },
      component: () => import('@/views/Workspace/Chat/ConversationDetail.vue'),
    },
  ],
}

export const agentSpaceRoute = {
  path: 'agent',
  name: 'agentSpace',
  meta: {
    title: 'router.workspace.children.agent_space',
    headerKey: 'agent',
  },
  redirect: { name: 'myAgents' },
  component: () => import('@/views/Workspace/Agent/AgentSpace.vue'),
  children: [
    {
      path: 'my-agents',
      name: 'myAgents',
      meta: {
        title: 'router.workspace.children.my_agents',
      },
      component: () => import('@/views/Workspace/Agent/MyAgents.vue'),
    },
    {
      path: 'public-agents',
      name: 'publicAgents',
      meta: {
        title: 'router.workspace.children.public_agents',
      },
      component: () => import('@/views/Workspace/Agent/PublicAgents.vue'),
    },
    {
      path: ':agentId',
      name: 'agentDetail',
      meta: {
        title: 'router.workspace.children.agent_detail',
      },
      component: () => import('@/views/Workspace/Agent/AgentDetail.vue'),
    },
  ],
}

export const agentRoutes = [agentChatRoute, agentSpaceRoute]
