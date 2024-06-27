/**
 * @Author: Bi Ying
 * @Date:   2022-02-05 01:38:00
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-25 13:12:45
 */
import { createRouter, createWebHashHistory } from 'vue-router'
import { WorkspaceLayout } from '@/layouts'


const routes = [
  {
    path: '/workflow/editor/:workflowId',
    name: 'WorkflowEditor',
    meta: {
      login: true
    },
    component: () => import('@/views/Workspace/WorkflowEditor.vue')
  },
  {
    path: '/',
    component: WorkspaceLayout,
    children: [
      {
        path: '',
        redirect: '/workflow',
      },
      {
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
            component: () => import('@/views/Workspace/WorkflowSpaceMain.vue')
          },
          {
            path: 'template/:workflowTemplateId',
            name: 'WorkflowTemplate',
            meta: {
              title: 'router.workspace.children.workflow_template',
            },
            component: () => import('@/views/Workspace/WorkflowTemplate.vue')
          },
          {
            path: ':workflowId',
            name: 'WorkflowUse',
            meta: {
              title: 'router.workspace.children.workflow_use',
            },
            component: () => import('@/views/Workspace/WorkflowSpaceUse.vue')
          },
        ]
      },
      {
        path: 'data',
        name: 'DataSpace',
        meta: {
          title: 'router.workspace.children.data_space',
          headerKey: 'data',
        },
        children: [
          {
            path: '',
            name: 'DataSpaceMain',
            meta: {
              title: 'router.workspace.children.data_space',
            },
            component: () => import('@/views/Workspace/Database/DataSpace.vue'),
          },
          {
            path: 'vector-db/:databaseId',
            name: 'VectorDatabaseDetail',
            meta: {
              title: 'router.workspace.children.database_detail',
            },
            component: () => import('@/views/Workspace/Database/VectorDatabaseDetail.vue')
          },
          {
            path: 'vector-db/:databaseId/create',
            name: 'VectorDatabaseObjectCreate',
            meta: {
              title: 'router.workspace.children.database_object_create',
            },
            component: () => import('@/views/Workspace/Database/VectorDatabaseObjectCreate.vue')
          },
          {
            path: 'vector-db/:databaseId/object/:objectId',
            name: 'VectorDatabaseObjectDetail',
            meta: {
              title: 'router.workspace.children.database_object_detail',
            },
            component: () => import('@/views/Workspace/Database/VectorDatabaseObjectDetail.vue')
          },
          {
            path: 'relational-db/:databaseId',
            name: 'RelationalDatabaseDetail',
            meta: {
              title: 'router.workspace.children.database_detail',
            },
            component: () => import('@/views/Workspace/Database/RelationalDatabaseDetail.vue')
          },
          {
            path: 'relational-db/:databaseId/create',
            name: 'RelationalDatabaseTableCreate',
            meta: {
              title: 'router.workspace.children.database_table_create',
            },
            component: () => import('@/views/Workspace/Database/RelationalDatabaseTableCreate.vue')
          },
          {
            path: 'relational-db/:databaseId/table/:tableId',
            name: 'RelationalDatabaseTableDetail',
            meta: {
              title: 'router.workspace.children.database_object_detail',
            },
            component: () => import('@/views/Workspace/Database/RelationalDatabaseTableDetail.vue')
          },
        ]
      },
      {
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
            component: () => import('@/views/Workspace/Chat/ConversationNew.vue')
          },
          {
            path: ':conversationId',
            name: 'conversationDetail',
            meta: {
              title: 'router.workspace.children.conversation_detail',
            },
            component: () => import('@/views/Workspace/Chat/ConversationDetail.vue')
          },
        ]
      },
      {
        path: 'agent',
        name: 'agentSpace',
        meta: {
          title: 'router.workspace.children.agent_space',
          headerKey: 'agent',
        },
        component: () => import('@/views/Workspace/Agent/AgentSpace.vue'),
        children: [
          {
            path: 'my-agents',
            name: 'myAgents',
            meta: {
              title: 'router.workspace.children.my_agents',
            },
            component: () => import('@/views/Workspace/Agent/MyAgents.vue')
          },
          {
            path: 'public-agents',
            name: 'publicAgents',
            meta: {
              title: 'router.workspace.children.public_agents',
            },
            component: () => import('@/views/Workspace/Agent/PublicAgents.vue')
          },
          {
            path: ':agentId',
            name: 'agentDetail',
            meta: {
              title: 'router.workspace.children.agent_detail',
            },
            component: () => import('@/views/Workspace/Agent/AgentDetail.vue'),
          },
        ]
      },
    ]
  },
  {
    path: '/settings',
    component: WorkspaceLayout,
    meta: {
      login: true
    },
    children: [
      {
        path: '',
        name: 'settings',
        meta: {
          title: 'router.account.settings'
        },
        component: () => import('@/views/Settings.vue')
      }
    ]
  },
]

const router = createRouter({
  history: createWebHashHistory('/'),
  routes
})

export default router
