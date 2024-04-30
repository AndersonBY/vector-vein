<script setup>
import { ref, reactive, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  Time,
  Control,
  Tag,
  ListNumbers,
  Login,
  HourglassFull,
} from '@icon-park/vue-next'
import { formatTime } from "@/utils/util"
import WorkflowRecordsStatusTag from "@/components/workspace/WorkflowRecordStatusTag.vue"
import { workflowRunRecordAPI } from "@/api/workflow"

const { t } = useI18n()
const loading = ref(true)

const props = defineProps({
  workflowId: {
    type: String,
    required: false,
    default: '',
  },
  buttonType: {
    type: String,
    required: false,
    default: 'primary',
  },
  showWorkflowTitle: {
    type: Boolean,
    required: false,
    default: false,
  },
  openType: {
    type: String,
    required: false,
    default: 'detail', // detail or simple
  },
})

const drawerWidth = props.showWorkflowTitle ? '80vw' : '70vw'

const open = ref(false)

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
  { text: t('components.workspace.workflowRunRecordsDrawer.status_stopping'), value: 'STOPPING' },
  { text: t('components.workspace.workflowRunRecordsDrawer.status_stopped'), value: 'STOPPED' },
]
const columns = ref([
  {
    title: t('components.workspace.workflowRunRecordsDrawer.start_time'),
    key: 'start_time',
    dataIndex: 'start_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '156px',
  },
  {
    title: t('components.workspace.workflowRunRecordsDrawer.end_time'),
    key: 'end_time',
    dataIndex: 'end_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '156px',
  },
  {
    title: t('components.workspace.workflowRunRecordsDrawer.run_time'),
    key: 'run_time',
    dataIndex: 'run_time',
    width: '100px',
  },
  {
    title: t('components.workspace.workflowRunRecordsDrawer.status'),
    key: 'status',
    dataIndex: 'status',
    filters: statusOptions,
    width: '100px',
  },
  {
    title: t('common.action'),
    key: 'action',
    width: '100px',
  }
])
if (props.showWorkflowTitle) {
  columns.value.splice(0, 0, {
    title: t('components.workspace.workflowRunRecordsDrawer.workflow_title'),
    key: 'workflow_title',
    dataIndex: 'workflow_title',
    ellipsis: true,
  })
}
const workflowRunRecords = reactive({
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  sort_field: 'start_time',
  sort_order: 'descend',
  filters: {
    status: [],
  },
  pagination: computed(() => ({
    total: workflowRunRecords.total,
    current: workflowRunRecords.current,
    pageSize: workflowRunRecords.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    workflowRunRecords.sort_field = sorter.field
    workflowRunRecords.sort_order = sorter.order
    workflowRunRecords.filters.status = filters.status
    workflowRunRecords.filters.shared = filters.shared
    workflowRunRecords.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
      status: filters.status,
      need_workflow: props.showWorkflowTitle,
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
        if (item.start_time && item.end_time) {
          item.run_time = ((parseInt(item.end_time) - parseInt(item.start_time)) / 1000).toFixed(2) + 's'
        } else {
          item.run_time = '-'
        }
        item.start_time = item.start_time ? formatTime(item.start_time) : '-'
        item.end_time = item.end_time ? formatTime(item.end_time) : '-'
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

const showDrawer = async () => {
  open.value = true
  await workflowRunRecords.load({
    page_size: workflowRunRecords.pageSize,
    page: workflowRunRecords.current,
    sort_field: workflowRunRecords.sort_field,
    sort_order: workflowRunRecords.sort_order,
    status: workflowRunRecords.filters.status,
    shared: workflowRunRecords.filters.shared,
    need_workflow: props.showWorkflowTitle,
  })
  loading.value = false
}

const getWorkflowRunRecordDetail = async (rid, workflow) => {
  loading.value = true
  if (props.openType == 'detail') {
    const res = await workflowRunRecordAPI('get', {
      rid: rid
    })
    if (res.status == 200) {
      emit('open-record', res.data)
      open.value = false
    } else {
      message.error(res.msg)
    }
  } else {
    emit('open-record', { rid, wid: workflow.wid })
    open.value = false
  }
  loading.value = false
}
</script>

<template>
  <a-button :type="props.buttonType" @click="showDrawer">
    {{ t('components.workspace.workflowRunRecordsDrawer.workflows_run_records') }}
  </a-button>
  <a-drawer :title="t('components.workspace.workflowRunRecordsDrawer.my_workflows_run_records')" :width="drawerWidth"
    :open="open" @close="onClose">
    <a-spin :spinning="loading">
      <a-row justify="space-between" align="middle">
        <a-col :span="24">
          <a-table :loading="workflowRunRecords.loading" :columns="columns" :customRow="workflowRunRecords.customRow"
            :data-source="workflowRunRecords.data" :pagination="workflowRunRecords.pagination"
            @change="workflowRunRecords.handleTableChange">
            <template #headerCell="{ column }">
              <template v-if="column.key === 'workflow_title'">
                <ListNumbers />
                {{ t('components.workspace.workflowRunRecordsDrawer.workflow_title') }}
              </template>
              <template v-else-if="column.key === 'start_time'">
                <Time />
                {{ t('components.workspace.workflowRunRecordsDrawer.start_time') }}
              </template>
              <template v-else-if="column.key === 'end_time'">
                <Time />
                {{ t('components.workspace.workflowRunRecordsDrawer.end_time') }}
              </template>
              <template v-else-if="column.key === 'run_time'">
                <a-tooltip :title="t('components.workspace.workflowRunRecordsDrawer.run_time')">
                  <HourglassFull />
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tooltip :title="t('components.workspace.workflowRunRecordsDrawer.status')">
                  <Tag />
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'action'">
                <Control />
                {{ t('common.action') }}
              </template>
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'workflow_title'">
                {{ record.workflow.title }}
              </template>
              <template v-else-if="column.key === 'status'">
                <WorkflowRecordsStatusTag :status="record.status" />
              </template>
              <template v-else-if="column.key === 'action'">
                <a-flex gap="small" align="center" justify="center">
                  <a-tooltip :title="t('components.workspace.workflowRunRecordsDrawer.check_record')">
                    <a-button type="text" @click.prevent="getWorkflowRunRecordDetail(record.rid, record.workflow)">
                      <template #icon>
                        <Login />
                      </template>
                    </a-button>
                  </a-tooltip>
                </a-flex>
              </template>
            </template>
          </a-table>
        </a-col>
      </a-row>
    </a-spin>
  </a-drawer>
</template>