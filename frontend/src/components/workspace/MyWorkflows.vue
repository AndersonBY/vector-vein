<script setup>
import { onBeforeMount, defineComponent, ref, reactive, computed, nextTick } from "vue"
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { BranchesOutlined, ControlOutlined, FieldTimeOutlined, PlusOutlined, TagsOutlined, StarOutlined, StarFilled } from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { workflowAPI, workflowTagAPI } from "@/api/workflow"
import ShareWorkflowModal from '@/components/workspace/ShareWorkflowModal.vue'
import NewWorkflowModal from '@/components/workspace/NewWorkflowModal.vue'
import WorkflowRunRecordsDrawer from "@/components/workspace/WorkflowRunRecordsDrawer.vue"
import { getWorkflows } from "@/utils/workflow"

defineComponent({
  name: 'MyWorkflows',
})

const { t } = useI18n()
const loading = ref(true)
const updating = ref(false)
const router = useRouter()
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)
const userWorkflowsStore = useUserWorkflowsStore()
const { userWorkflows, userWorkflowsTotal } = storeToRefs(userWorkflowsStore)
const tags = ref([])

onBeforeMount(async () => {
  const [workflows, tagsResponse] = await Promise.all([
    workflowRecords.load({}),
    workflowTagAPI('list', {}),
  ])
  if (tagsResponse.status == 200) {
    tags.value = tagsResponse.data
  }
  loading.value = false
})

const workflowRecords = reactive({
  columns: [{
    name: t('workspace.workflowSpaceMain.workflow_title'),
    dataIndex: 'title',
    key: 'title',
  }, {
    title: t('workspace.workflowSpaceMain.tags'),
    key: 'tags',
    dataIndex: 'tags',
    filters: computed(() => tags.value.map(tag => ({ text: tag.title, value: tag.tid }))),
    width: '300px',
  }, {
    title: t('workspace.workflowSpaceMain.update_time'),
    key: 'update_time',
    dataIndex: 'update_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '200px',
  }, {
    title: t('common.action'),
    key: 'action',
    width: '300px',
  }],
  data: userWorkflows.value,
  loading: false,
  current: 1,
  pageSize: 10,
  total: userWorkflowsTotal.value,
  pagination: computed(() => ({
    total: workflowRecords.total,
    current: workflowRecords.current,
    pageSize: workflowRecords.pageSize,
  })),
  selectTag: 'all',
  selectTagChange: async () => {
    workflowRecords.loading = true
    await workflowRecords.load({ tags: [workflowRecords.selectTag] })
    workflowRecords.loading = false
  },
  searching: false,
  searchText: '',
  hoverRowWid: null,
  customRow: (record) => {
    return {
      style: { cursor: 'pointer' },
      onClick: (event) => {
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('workflow-title')) {
          router.push(`/workflow/${record.wid}`)
        }
      },
      onMouseenter: (event) => { workflowRecords.hoverRowWid = record.wid },
      onMouseleave: (event) => { workflowRecords.hoverRowWid = null }
    };
  },
  searchWorkflows: async () => {
    workflowRecords.loading = true
    workflowRecords.searching = true
    await workflowRecords.load({ search_text: workflowRecords.searchText })
    workflowRecords.searching = false
    workflowRecords.loading = false
  },
  clearSearch: async () => {
    workflowRecords.loading = true
    workflowRecords.searching = true
    workflowRecords.searchText = ''
    await workflowRecords.load({})
    workflowRecords.searching = false
    workflowRecords.loading = false
  },
  handleTableChange: (page, filters, sorter) => {
    workflowRecords.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
      tags: filters.tags,
    })
  },
  load: async (params) => {
    workflowRecords.loading = true
    const res = await workflowAPI('list', params)
    if (res.status == 200) {
      workflowRecords.data = res.data.workflows.map(item => {
        item.create_time = new Date(item.create_time).toLocaleString()
        item.update_time = new Date(item.update_time).toLocaleString()
        return item
      })
    } else {
      message.error(res.msg)
    }
    workflowRecords.total = res.data.total
    workflowRecords.pageSize = res.data.page_size
    workflowRecords.current = res.data.page
    workflowRecords.loading = false
  }
})

const deleteWorkflow = async (wid) => {
  const response = await workflowAPI('delete', { wid: wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_success'))
    userWorkflowsStore.deleteUserWorkflow(wid)
    workflowRecords.load({})
  } else {
    message.error(t('workspace.workflowSpace.delete_failed'))
  }
}

const addWorkflowToFastAccess = async (wid) => {
  const response = await workflowAPI('add_to_fast_access', { wid: wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.add_to_fast_access_success'))
    getWorkflows(userWorkflowsStore, true)
    workflowRecords.data = workflowRecords.data.map(item => {
      if (item.wid == wid) {
        item.is_fast_access = true
      }
      return item
    })
  } else {
    message.error(t('workspace.workflowSpace.add_to_fast_access_failed'))
  }
}
const deleteWorkflowFromFastAccess = async (wid) => {
  const response = await workflowAPI('delete_from_fast_access', { wid: wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_from_fast_access_success'))
    getWorkflows(userWorkflowsStore, true)
    workflowRecords.data = workflowRecords.data.map(item => {
      if (item.wid == wid) {
        item.is_fast_access = false
      }
      return item
    })
  } else {
    message.error(t('workspace.workflowSpace.delete_from_fast_access_failed'))
  }
}

const shareWorkflowModalRef = ref()
const openShareWorkflowModal = (wid) => {
  const workflow = userWorkflows.value.find(item => item.wid == wid)
  shareWorkflowModalRef.value.showModal(workflow)
}

const newWorkflowModal = ref()
const openNewWorkflowModal = () => {
  newWorkflowModal.value.showModal()
}
const add = async (template) => {
  loading.value = true
  const response = await workflowAPI('create', {
    title: t('workspace.workflowSpace.new_workflow'),
    language: language.value,
  })
  if (response.status != 200) {
    message.error(response.msg)
    return
  }
  const workflow = response.data
  getWorkflows(userWorkflowsStore, true)
  nextTick(async () => {
    await router.push(`/workflow/editor/${workflow.wid}`)
  })
}

const clone = async (workflowWid) => {
  loading.value = true
  const getWorkflowResponse = await workflowAPI('get', { wid: workflowWid })
  if (getWorkflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.clone_failed'))
    return
  }
  const createResponse = await workflowAPI('create', {
    ...getWorkflowResponse.data,
    title: getWorkflowResponse.data.title + ' ' + t('workspace.workflowSpace.clone_workflow'),
  })
  if (createResponse.status != 200) {
    message.error(createResponse.data.msg)
    return
  }
  const workflow = createResponse.data
  getWorkflows(userWorkflowsStore, true)
  nextTick(async () => {
    await router.push(`/workflow/${workflow.wid}`)
  })
}

const openRecord = async (record) => {
  await router.push(`/workflow/${record.wid}?rid=${record.rid}`)
}
</script>

<template>
  <div class="space-container" v-if="loading">
    <a-skeleton active />
  </div>
  <a-spin :spinning="updating" class="space-container" v-else>
    <a-row justify="space-between" align="middle" :gutter="[16, 16]">
      <a-col :span="24">
        <a-row type="flex" align="middle" justify="space-between">
          <a-col flex="auto">
            <a-space>
              <a-input-search v-model:value="workflowRecords.searchText"
                :placeholder="t('workspace.workflowSpaceMain.input_search_text')" enter-button
                @search="workflowRecords.searchWorkflows" class="search-input">
              </a-input-search>
              <a-button @click="workflowRecords.clearSearch">
                {{ t('workspace.workflowSpaceMain.reset_search') }}
              </a-button>
            </a-space>
          </a-col>
          <a-col flex="auto" style="display: flex; justify-content: end;">
            <a-space>
              <a-button type="primary" @click="add">
                <PlusOutlined />
                {{ t('workspace.workflowSpaceMain.create_workflow') }}
              </a-button>
              <NewWorkflowModal ref="newWorkflowModal" @create="add" />
              <WorkflowRunRecordsDrawer buttonType="default" openType="simple" :showWorkflowTitle="true"
                @open-record="openRecord" />
            </a-space>
          </a-col>
        </a-row>
      </a-col>

      <a-divider></a-divider>

      <a-col :span="24">
        <a-table :loading="workflowRecords.loading" :columns="workflowRecords.columns"
          :customRow="workflowRecords.customRow" :data-source="workflowRecords.data"
          :pagination="workflowRecords.pagination" @change="workflowRecords.handleTableChange">
          <template #headerCell="{ column }">
            <template v-if="column.key === 'title'">
              <BranchesOutlined />
              {{ t('workspace.workflowSpaceMain.workflow_title') }}
            </template>
            <template v-else-if="column.key === 'tags'">
              <TagsOutlined />
              {{ t('workspace.workflowSpaceMain.tags') }}
            </template>
            <template v-else-if="column.key === 'update_time'">
              <FieldTimeOutlined />
              {{ t('workspace.workflowSpaceMain.update_time') }}
            </template>
            <template v-else-if="column.key === 'action'">
              <ControlOutlined />
              {{ t('common.action') }}
            </template>
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'title'">
              <a-space>
                <a-typography-text class="workflow-title">
                  {{ record.title }}
                </a-typography-text>
                <a-tooltip :title="t('workspace.workflowSpace.add_to_fast_access')" v-if="!record.is_fast_access">
                  <a-typography-link @click=addWorkflowToFastAccess(record.wid)>
                    <StarOutlined v-show="workflowRecords.hoverRowWid == record.wid" />
                  </a-typography-link>
                </a-tooltip>
                <a-tooltip :title="t('workspace.workflowSpace.delete_from_fast_access')" v-else>
                  <a-typography-link @click=deleteWorkflowFromFastAccess(record.wid)>
                    <StarFilled />
                  </a-typography-link>
                </a-tooltip>
              </a-space>
            </template>
            <template v-else-if="column.key === 'tags'">
              <a-space>
                <a-tag :color="tag.color" v-for="tag in record.tags" :key="tag.tid">
                  {{ tag.title }}
                </a-tag>
              </a-space>
            </template>
            <template v-else-if="column.key === 'action'">
              <div class="action-container">
                <!-- <a-typography-link @click.prevent="openShareWorkflowModal(record.wid)">
                  {{ t('workspace.workflowSpace.share_workflow') }}
                </a-typography-link>
                <a-divider type="vertical" /> -->
                <a-typography-link @click.prevent="clone(record.wid)">
                  {{ t('workspace.workflowSpace.clone_workflow') }}
                </a-typography-link>
                <a-divider type="vertical" />
                <a-popconfirm :title="t('workspace.workflowSpace.delete_confirm')" @confirm="deleteWorkflow(record.wid)">
                  <a-typography-link type="danger">
                    {{ t('workspace.workflowSpace.delete') }}
                  </a-typography-link>
                </a-popconfirm>
              </div>
            </template>
          </template>
        </a-table>
        <ShareWorkflowModal ref="shareWorkflowModalRef" />
      </a-col>
    </a-row>
  </a-spin>
</template>

<style scoped>
.search-input {
  min-width: 300px;
  max-width: 500px;
}
</style>