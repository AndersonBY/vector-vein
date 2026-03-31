/**
 * @Author: Bi Ying
 * @Date:   2022-02-05 01:38:00
 * @Last Modified by:   Codex
 * @Last Modified time: 2026-03-30 12:00:00
 */
import { createRouter, createWebHashHistory } from 'vue-router'
import { WorkspaceLayout } from '@/layouts'
import { agentRoutes } from './modules/agent'
import { dataSpaceRoute } from './modules/data'
import { settingsRoute } from './modules/settings'
import {
  workflowEditorRoute,
  workflowSpaceRoute,
  workspaceRootRedirectRoute,
} from './modules/workspace'

const workspaceRoutes = [
  workspaceRootRedirectRoute,
  workflowSpaceRoute,
  dataSpaceRoute,
  ...agentRoutes,
]

const routes = [
  workflowEditorRoute,
  {
    path: '/',
    component: WorkspaceLayout,
    children: workspaceRoutes,
  },
  settingsRoute,
]

const router = createRouter({
  history: createWebHashHistory('/'),
  routes
})

export default router
