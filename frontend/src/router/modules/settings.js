import { WorkspaceLayout } from '@/layouts'

export const settingsRoute = {
  path: '/settings',
  component: WorkspaceLayout,
  meta: {
    login: true,
  },
  children: [
    {
      path: '',
      name: 'settings',
      meta: {
        title: 'router.account.settings',
      },
      component: () => import('@/views/Settings.vue'),
    },
  ],
}
