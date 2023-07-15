<script setup>
import { defineComponent, ref, reactive, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ControlOutlined, FieldTimeOutlined, FlagOutlined, PayCircleOutlined, NumberOutlined } from '@ant-design/icons-vue'
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
const columns = ref([{
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
}])
if (props.showWorkflowTitle) {
  columns.value.splice(0, 0, {
    title: t('components.workspace.workflowRunRecordsDrawer.workflow_title'),
    key: 'workflow_title',
    dataIndex: 'workflow_title',
    width: '100px',
  })
}
const workflowRunRecords = reactive({
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
                <NumberOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.workflow_title') }}
              </template>
              <template v-else-if="column.key === 'start_time'">
                <FieldTimeOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.start_time') }}
              </template>
              <template v-else-if="column.key === 'end_time'">
                <FieldTimeOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.end_time') }}
              </template>
              <template v-else-if="column.key === 'status'">
                <FlagOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.status') }}
              </template>
              <template v-else-if="column.key === 'used_credits'">
                <PayCircleOutlined />
                {{ t('components.workspace.workflowRunRecordsDrawer.used_credits') }}
              </template>
              <template v-else-if="column.key === 'action'">
                <ControlOutlined />
                {{ t('common.action') }}
              </template>
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'workflow_title'">
                {{ record.workflow.title }}
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="statusColor[record.status]">
                  {{ t(`components.workspace.workflowRunRecordsDrawer.status_${record.status.toLowerCase()}`) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <div class="action-container">
                  <a-typography-link @click.prevent="getWorkflowRunRecordDetail(record.rid, record.workflow)">
                    <template v-if="record.status === 'FAILED'">
                      {{ t('components.workspace.workflowRunRecordsDrawer.check_record_and_error_task') }}
                    </template>
                    <template v-else>
                      {{ t('components.workspace.workflowRunRecordsDrawer.check_record') }}
                    </template>
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