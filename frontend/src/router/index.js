/**
 * @Author: Bi Ying
 * @Date:   2022-02-05 01:38:00
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-29 23:53:18
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
        },
        children: [
          {
            path: '',
            name: 'DataSpace',
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
    ]
  },
  {
    path: '/account',
    name: 'account',
    component: WorkspaceLayout,
    meta: {
      login: true
    },
    children: [
      {
        path: 'info',
        name: 'AccountInfo',
        meta: {
          title: 'router.account.children.account_info'
        },
        component: () => import('@/views/UserAccount/AccountInfo.vue')
      }
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
