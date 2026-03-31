<script setup>
import { onBeforeMount, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { workflowAPI } from '@/api/workflow'
import { useUserWorkflowsStore } from '@/stores/userWorkflows'
import { formatTime } from '@/utils/util'
import WorkspacePageHero from '@/components/workspace/WorkspacePageHero.vue'
import WorkspaceEmptyState from '@/components/workspace/WorkspaceEmptyState.vue'

const { t } = useI18n()
const userWorkflowsStore = useUserWorkflowsStore()

const trash = reactive({
  data: [],
  loading: false,
  page: 1,
  pageSize: 10,
  total: 0,
})

const loadTrash = async (page = trash.page, pageSize = trash.pageSize) => {
  trash.loading = true
  const response = await workflowAPI('trash_list', { page, page_size: pageSize })
  if (response.status === 200) {
    trash.data = (response.data.workflows || []).map((workflow) => ({
      ...workflow,
      key: workflow.wid,
      update_time_display: workflow.update_time ? formatTime(workflow.update_time) : '-',
    }))
    trash.page = response.data.page
    trash.pageSize = response.data.page_size
    trash.total = response.data.total
  } else {
    message.error(response.msg || t('workspace.workflowSpace.trash_load_failed'))
  }
  trash.loading = false
}

onBeforeMount(async () => {
  await loadTrash()
})

const restoreWorkflow = async (wid) => {
  const response = await workflowAPI('trash_restore', { wid })
  if (response.status === 200) {
    message.success(t('workspace.workflowSpace.restore_success'))
    await Promise.all([loadTrash(), userWorkflowsStore.refreshWorkflows()])
  } else {
    message.error(response.msg || t('workspace.workflowSpace.restore_failed'))
  }
}

const purgeWorkflow = (wid) => {
  Modal.confirm({
    title: t('workspace.workflowSpace.purge_confirm'),
    okType: 'danger',
    async onOk() {
      const response = await workflowAPI('trash_purge', { wid })
      if (response.status === 200) {
        message.success(t('workspace.workflowSpace.purge_success'))
        await loadTrash()
      } else {
        message.error(response.msg || t('workspace.workflowSpace.purge_failed'))
      }
    },
  })
}

const onTableChange = async (pagination) => {
  await loadTrash(pagination.current, pagination.pageSize)
}
</script>

<template>
  <a-flex vertical gap="large">
    <WorkspacePageHero
      :title="t('workspace.workflowSpace.trash')"
      :description="t('workspace.workflowSpace.trash_description')"
      :stats="[{ label: t('workspace.workflowSpace.trash_count'), value: trash.total, tip: t('workspace.workflowSpace.trash_count_tip') }]" />

    <a-card>
      <WorkspaceEmptyState v-if="!trash.loading && trash.data.length === 0"
        :title="t('workspace.workflowSpace.trash_empty')"
        :description="t('workspace.workflowSpace.trash_empty_description')" />

      <a-table v-else :data-source="trash.data" :loading="trash.loading"
        :pagination="{ total: trash.total, current: trash.page, pageSize: trash.pageSize }"
        @change="onTableChange">
        <a-table-column key="title" :title="t('common.title')" data-index="title" />
        <a-table-column key="update_time_display" :title="t('workspace.workflowSpace.deleted_at')" data-index="update_time_display" />
        <a-table-column key="action" :title="t('common.action')" width="220">
          <template #default="{ record }">
            <a-space>
              <a-button size="small" type="primary" @click="restoreWorkflow(record.wid)">
                {{ t('workspace.workflowSpace.restore') }}
              </a-button>
              <a-button size="small" danger @click="purgeWorkflow(record.wid)">
                {{ t('workspace.workflowSpace.delete_permanently') }}
              </a-button>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
    </a-card>
  </a-flex>
</template>
