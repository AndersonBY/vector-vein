export const dataSpaceRoute = {
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
      path: 'knowledge-base/:kbId',
      name: 'KnowledgeBaseDetail',
      meta: { title: 'knowledgeBase.title' },
      component: () => import('@/views/Workspace/Database/KnowledgeBaseDetail.vue'),
    },
    {
      path: 'relational-db/:databaseId',
      name: 'RelationalDatabaseDetail',
      meta: {
        title: 'router.workspace.children.database_detail',
      },
      component: () => import('@/views/Workspace/Database/RelationalDatabaseDetail.vue'),
    },
    {
      path: 'relational-db/:databaseId/create',
      name: 'RelationalDatabaseTableCreate',
      meta: {
        title: 'router.workspace.children.database_table_create',
      },
      component: () => import('@/views/Workspace/Database/RelationalDatabaseTableCreate.vue'),
    },
    {
      path: 'relational-db/:databaseId/table/:tableId',
      name: 'RelationalDatabaseTableDetail',
      meta: {
        title: 'router.workspace.children.database_object_detail',
      },
      component: () => import('@/views/Workspace/Database/RelationalDatabaseTableDetail.vue'),
    },
  ],
}
