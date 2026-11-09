<script setup>
import { Add, Edit, Time, Delete } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeMount, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { useUserWorkflowsStore } from '@/stores/userWorkflows'
import { workflowScheduleTriggerAPI } from '@/api/workflow'
import { formatTime } from '@/utils/util'
import ScheduleEditor from '@/components/scheduling/ScheduleEditor.vue'
import { formatSchedule } from '@/utils/schedule'
import WorkspacePageHero from '@/components/workspace/WorkspacePageHero.vue'
import WorkspaceEmptyState from '@/components/workspace/WorkspaceEmptyState.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userWorkflowsStore = useUserWorkflowsStore()
const loading = ref(false)
const saving = ref(false)
const scheduleValid = ref(true)
const localTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'

const schedules = reactive({
  data: [],
  page: 1,
  pageSize: 10,
  total: 0,
})

const scheduleModal = reactive({
  open: false,
  sid: '',
  wid: '',
  cron_expression: '0 9 * * *',
  timezone: localTimezone(),
  recurrence: null,
})

const workflowOptions = computed(() => (userWorkflowsStore.userWorkflows || []).map((workflow) => ({
  label: workflow.title,
  value: workflow.wid,
})))


const loadSchedules = async (page = schedules.page, pageSize = schedules.pageSize) => {
  loading.value = true
  const response = await workflowScheduleTriggerAPI('list', {
    page,
    page_size: pageSize,
    sort_field: 'update_time',
    sort_order: 'descend',
    wid: route.query.wid || undefined,
  })
  if (response.status === 200) {
    schedules.data = (response.data.schedules || []).map((item) => ({
      ...item,
      key: item.sid,
      update_time_display: item.update_time ? formatTime(item.update_time) : '-',
      next_run_display: item.next_run_at ? formatTime(item.next_run_at) : '-',
      last_run_display: item.latest_record?.start_time ? formatTime(item.latest_record.start_time) : '-',
      last_run_status: item.latest_record?.status || 'IDLE',
    }))
    schedules.page = response.data.page
    schedules.pageSize = response.data.page_size
    schedules.total = response.data.total
  } else {
    message.error(response.msg || t('workspace.workflowSpace.schedule_load_failed'))
  }
  loading.value = false
}

onBeforeMount(async () => {
  await userWorkflowsStore.refreshWorkflows()
  await loadSchedules()
  if (route.query.wid && schedules.data.length === 0) {
    scheduleModal.wid = route.query.wid
    scheduleModal.open = true
  }
})

const openCreateModal = () => {
  scheduleModal.open = true
  scheduleModal.sid = ''
  scheduleModal.wid = route.query.wid || ''
  scheduleModal.cron_expression = '0 9 * * *'
  scheduleModal.timezone = localTimezone()
  scheduleModal.recurrence = null
}

const openEditModal = (record) => {
  scheduleModal.open = true
  scheduleModal.sid = record.sid
  scheduleModal.wid = record.workflow?.wid || ''
  scheduleModal.cron_expression = record.cron_expression || '0 9 * * *'
  scheduleModal.timezone = record.data?.timezone || 'Asia/Shanghai'
  scheduleModal.recurrence = record.data?.recurrence ? { ...record.data.recurrence } : null
}

const saveSchedule = async () => {
  if (saving.value || !scheduleValid.value) return
  if (!scheduleModal.wid && !scheduleModal.sid) {
    message.warning(t('workspace.workflowSpace.schedule_workflow_required'))
    return
  }
  saving.value = true
  try {
    const response = await workflowScheduleTriggerAPI('update', {
      sid: scheduleModal.sid || undefined,
      wid: scheduleModal.wid || undefined,
      cron_expression: scheduleModal.cron_expression,
      timezone: scheduleModal.timezone,
      recurrence: scheduleModal.recurrence,
    })
    if (response.status === 200) {
      message.success(t('workspace.workflowSpace.schedule_update_success'))
      scheduleModal.open = false
      await loadSchedules()
    } else {
      message.error(response.msg || t('workspace.workflowSpace.schedule_update_failed'))
    }
  } catch {
    message.error(t('workspace.workflowSpace.schedule_update_failed'))
  } finally {
    saving.value = false
  }
}

const removeSchedule = (record) => {
  Modal.confirm({
    title: t('workspace.workflowSpace.schedule_delete_confirm'),
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      const response = await workflowScheduleTriggerAPI('delete', { sid: record.sid })
      if (response.status === 200) {
        message.success(t('workspace.workflowSpace.schedule_delete_success'))
        await loadSchedules()
      } else {
        message.error(response.msg || t('workspace.workflowSpace.schedule_delete_failed'))
      }
    },
  })
}

const openWorkflow = (record) => {
  if (!record.workflow?.wid) {
    return
  }
  router.push({ name: 'WorkflowUse', params: { workflowId: record.workflow.wid } })
}

const openLatestRecord = (record) => {
  if (!record.workflow?.wid || !record.latest_record?.rid) {
    message.info(t('workspace.workflowSpace.schedule_no_run_record'))
    return
  }
  router.push({
    name: 'WorkflowUse',
    params: { workflowId: record.workflow.wid },
    query: { rid: record.latest_record.rid },
  })
}

const onTableChange = async (pagination) => {
  await loadSchedules(pagination.current, pagination.pageSize)
}
</script>

<template>
  <a-flex vertical gap="large" class="schedule-manager-page">
    <WorkspacePageHero
      :title="t('workspace.workflowSpace.schedule_manager')"
      :description="t('workspace.workflowSpace.schedule_manager_description')">
      <template #actions>
        <IconButton :text="t('workspace.workflowSpace.schedule_create')" type="primary" @click="openCreateModal">
          <template #icon><Add /></template>
        </IconButton>
      </template>
    </WorkspacePageHero>

    <a-card>
      <WorkspaceEmptyState v-if="!loading && schedules.data.length === 0"
        :title="t('workspace.workflowSpace.schedule_empty')"
        :description="t('workspace.workflowSpace.schedule_empty_description')">
        <a-button type="primary" @click="openCreateModal">
          {{ t('workspace.workflowSpace.schedule_create') }}
        </a-button>
      </WorkspaceEmptyState>

      <a-table v-else :data-source="schedules.data" :loading="loading"
        :pagination="{ total: schedules.total, current: schedules.page, pageSize: schedules.pageSize }"
        @change="onTableChange">
        <a-table-column key="workflow" :title="t('common.workflow')">
          <template #default="{ record }">
            <a-button type="link" @click="openWorkflow(record)">
              {{ record.workflow?.title || '-' }}
            </a-button>
          </template>
        </a-table-column>
        <a-table-column key="cron_expression" :title="t('workspace.workflowSpace.schedule_pattern')">
          <template #default="{ record }">
            <span>{{ formatSchedule(record.cron_expression, record.data?.recurrence, t) }}</span>
            <div class="schedule-timezone">{{ record.data?.timezone || 'Asia/Shanghai' }}</div>
          </template>
        </a-table-column>
        <a-table-column key="next_run_display" :title="t('workspace.workflowSpace.schedule_next_run')" data-index="next_run_display" />
        <a-table-column key="last_run_display" :title="t('workspace.workflowSpace.schedule_last_run')" data-index="last_run_display" />
        <a-table-column key="last_run_status" :title="t('workspace.workflowSpace.schedule_last_run_status')" data-index="last_run_status" />
        <a-table-column key="update_time_display" :title="t('common.update_time')" data-index="update_time_display" />
        <a-table-column key="action" :title="t('common.action')" width="132">
          <template #default="{ record }">
            <a-space>
              <IconButton :text="t('common.edit')" size="small" @click="openEditModal(record)">
                <template #icon><Edit /></template>
              </IconButton>
              <IconButton :text="t('workspace.workflowSpace.schedule_latest_run')" size="small" @click="openLatestRecord(record)">
                <template #icon><Time /></template>
              </IconButton>
              <IconButton :text="t('common.delete')" size="small" danger @click="removeSchedule(record)">
                <template #icon><Delete /></template>
              </IconButton>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-modal v-model:open="scheduleModal.open" :title="t(scheduleModal.sid ? 'workspace.workflowSpace.schedule_edit' : 'workspace.workflowSpace.schedule_create')"
      :ok-text="t('common.save')" :cancel-text="t('common.cancel')"
      :confirm-loading="saving" :ok-button-props="{ disabled: !scheduleValid || saving }" :cancel-button-props="{ disabled: saving }"
      :closable="!saving" :mask-closable="!saving" :keyboard="!saving" @ok="saveSchedule">
      <a-form layout="vertical">
        <a-form-item :label="t('common.workflow')" required>
          <a-select v-model:value="scheduleModal.wid" :options="workflowOptions" :disabled="saving || !!scheduleModal.sid" />
        </a-form-item>
        <a-form-item :label="t('workspace.workflowSpace.schedule_pattern')" required>
          <ScheduleEditor v-if="scheduleModal.open" v-model="scheduleModal.cron_expression" v-model:timezone="scheduleModal.timezone"
            v-model:recurrence="scheduleModal.recurrence" :disabled="saving" @validity-change="scheduleValid = $event" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-flex>
</template>

<style scoped>
.schedule-manager-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.schedule-timezone { margin-top: 4px; color: var(--site-secondary-text-color); font-size: 12px; }
</style>
