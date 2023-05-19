<script setup>
import { defineComponent, ref, reactive, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ControlOutlined, FieldTimeOutlined, TagsOutlined, PayCircleOutlined } from '@ant-design/icons-vue'
import { workflowRunRecordAPI } from "@/api/workflow"

defineComponent({
  name: 'WorkflowRunRecordsDrawer',
})

const { t } = useI18n()
const loading = ref(true)

const props = defineProps({
  workflowId: {
    type: String,
    required: true,
  },
})

const statusColor = {
  NOT_STARTED: 'purple',
  QUEUED: 'orange',
  RUNNING: 'blue',
  FINISHED: 'green',
  FAILED: 'red',
}

const open = ref(false)

const showDrawer = async () => {
  open.value = true
  await workflowRunRecords.load({})
  loading.value = false
}

const onClose = () => {
  open.value = false
}

const emit = defineEmits(['open-record'])
const statusOptions = [
  { text: t('components.workspace.workflowRunRecordsDrawer.status_not_started'), value: 'NOT_STARTED' },
  { text: t('components.workspace.workflowRunRecordsDrawer.status_queued'), value: 'QUEUED' },
  { text: t('components.workspace.workflowRunRecordsDrawer.status_running'), value: 'RUNNING' },
  { text: t('components.workspace.workflowRunRecordsDrawer.status_finished'), value: 'FINISHED' },
  { text: t('components.workspace.workflowRunRecordsDrawer.status_failed'), value: 'FAILED' },
]
const workflowRunRecords = reactive({
  columns: [{
    title: t('components.workspace.workflowRunRecordsDrawer.start_time'),
    key: 'start_time',
    dataIndex: 'start_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '156px',
  }, {
    title: t('components.workspace.workflowRunRecordsDrawer.end_time'),
    key: 'end_time',
    dataIndex: 'end_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '156px',
  }, {
    title: t('components.workspace.workflowRunRecordsDrawer.status'),
    key: 'status',
    dataIndex: 'status',
    filters: statusOptions,
    width: '60px',
  }, {
    title: t('common.action'),
    key: 'action',
    width: '100px',
  }],
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  pagination: computed(() => ({
    total: workflowRunRecords.total,
    current: workflowRunRecords.current,
    pageSize: workflowRunRecords.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    workflowRunRecords.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
      status: filters.status,
    })
  },
  load: async (params) => {
    workflowRunRecords.loading = true
    const res = await workflowRunRecordAPI('list', {
      wid: props.workflowId,
      ...params
    })
    if (res.status == 200) {
      workflowRunRecords.data = res.data.records.map(item => {
        item.start_time = item.start_time ? new Date(item.start_time).toLocaleString() : '-'
        item.end_time = item.end_time ? new Date(item.end_time).toLocaleString() : '-'
        return item
      })
    } else {
      message.error(res.msg)
    }
    workflowRunRecords.total = res.data.total
    workflowRunRecords.pageSize = res.data.page_size
    workflowRunRecords.current = res.data.page
    workflowRunRecords.loading = false
  }
})

const getWorkflowRunRecordDetail = async (rid) => {
  loading.value = true
  const res = await workflowRunRecordAPI('get', {
    rid: rid
  })
  if (res.status == 200) {
    emit('open-record', res.data)
    open.value = false
  } else {
    message.error(res.msg)
  }
  loading.value = false
}
</script>

<template>
  <a-button type="primary" @click="showDrawer">
    {{ t('components.workspace.workflowRunRecordsDrawer.workflows_run_records') }}
  </a-button>
  <a-drawer :title="t('components.workspace.workflowRunRecordsDrawer.my_workflows_run_records')" width="50vw" :open="open"
    @close="onClose">
    <a-spin :spinning="loading">
      <a-row justify="space-between" align="middle">
        <a-col :span="24">
          <a-table :loading="workflowRunRecords.loading" :columns="workflowRunRecords.columns"
            :customRow="workflowRunRecords.customRow" :data-source="workflowRunRecords.data"
            :pagination="workflowRunRecords.pagination" @change="workflowRunRecords.handleTableChange">
            <template #headerCell="{ column }">
              <template v-if="column.key === 'status'">
                <TagsOutlined />
                {{ t('workspace.workflowSpaceMain.tags') }}
              </template>
              <template v-else-if="column.key === 'start_time'">
                <FieldTimeOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.start_time') }}
              </template>
              <template v-else-if="column.key === 'end_time'">
                <FieldTimeOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.end_time') }}
              </template>
              <template v-else-if="column.key === 'action'">
                <ControlOutlined />
                {{ t('common.action') }}
              </template>
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="statusColor[record.status]">
                  {{ t(`components.workspace.workflowRunRecordsDrawer.status_${record.status.toLowerCase()}`) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <div class="action-container">
                  <a-typography-link @click.prevent="getWorkflowRunRecordDetail(record.rid)">
                    {{ t('components.workspace.workflowRunRecordsDrawer.check_record') }}
                  </a-typography-link>
                </div>
              </template>
            </template>
          </a-table>
        </a-col>
      </a-row>
    </a-spin>
  </a-drawer>
</template>