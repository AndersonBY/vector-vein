/**
 * @Author: Bi Ying
 * @Date:   2022-02-05 01:38:00
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-13 02:15:54
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
            component: () => import('@/views/Workspace/DataSpace.vue'),
          },
          {
            path: ':databaseId',
            name: 'DatabaseDetail',
            meta: {
              title: 'router.workspace.children.database_detail',
            },
            component: () => import('@/views/Workspace/DatabaseDetail.vue')
          },
          {
            path: ':databaseId/create',
            name: 'DatabaseObjectCreate',
            meta: {
              title: 'router.workspace.children.database_detail',
            },
            component: () => import('@/views/Workspace/DatabaseObjectCreate.vue')
          },
          {
            path: ':databaseId/object/:objectId',
            name: 'DatabaseObjectDetail',
            meta: {
              title: 'router.workspace.children.database_object_detail',
            },
            component: () => import('@/views/Workspace/DatabaseObjectDetail.vue')
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
      },
      {
        path: 'settings',
        name: 'AccountSettings',
        meta: {
          title: 'router.account.children.account_settings'
        },
        component: () => import('@/views/UserAccount/AccountSettings.vue')
      }
    ]
  },
]

const router = createRouter({
  history: createWebHashHistory('/'),
  routes
})

export default router
