<script setup>
import { onBeforeMount, ref, reactive, computed, nextTick, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import {
  WholeSiteAccelerator,
  TagOne,
  Time,
  Control,
  Plus,
  Star,
  Copy,
  Delete,
  ListOne,
  ViewGridCard,
} from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import WorkflowRunRecordsDrawer from "@/components/workspace/WorkflowRunRecordsDrawer.vue"
import InputSearch from "@/components/InputSearch.vue"
import WorkflowCard from '@/components/workspace/WorkflowCard.vue'
import { formatTime } from '@/utils/util'
import { workflowAPI, workflowTagAPI } from "@/api/workflow"

const { t } = useI18n()
const loading = ref(true)
const router = useRouter()
const userSettingsStore = useUserSettingsStore()
const { language, workflowDisplayPreference } = storeToRefs(userSettingsStore)
const userWorkflowsStore = useUserWorkflowsStore()
const { userWorkflows, userWorkflowsTotal } = storeToRefs(userWorkflowsStore)
const tags = ref([])

onBeforeMount(async () => {
  const searchText = router.currentRoute.value.query.search_text
  let searchTextQuery = {}
  if (searchText) {
    searchTextQuery = { search_text: searchText }
    workflowRecords.searchText = searchText
  }
  const [workflows, tagsResponse] = await Promise.all([
    workflowRecords.load({ page_size: workflowRecords.pageSize, ...searchTextQuery }),
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
    width: '160px',
  }, {
    title: t('common.action'),
    key: 'action',
    width: '160px',
  }],
  data: userWorkflows.value,
  loading: false,
  current: 1,
  pageSize: workflowDisplayPreference.value == 'card' ? 16 : 10,
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
      onClick: async (event) => {
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('workflow-title')) {
          await nextTick(async () => {
            await router.push({ name: 'WorkflowUse', params: { workflowId: record.wid } })
          })
        }
      },
      onMouseenter: (event) => { workflowRecords.hoverRowWid = record.wid },
      onMouseleave: (event) => { workflowRecords.hoverRowWid = null }
    };
  },
  searchWorkflows: async () => {
    workflowRecords.loading = true
    workflowRecords.searching = true
    await workflowRecords.load({ page_size: workflowRecords.pageSize, search_text: workflowRecords.searchText })
    workflowRecords.searching = false
    workflowRecords.loading = false
    await router.push({ query: { ...router.currentRoute.value.query, search_text: workflowRecords.searchText } })
  },
  clearSearch: async () => {
    workflowRecords.loading = true
    workflowRecords.searching = true
    workflowRecords.searchText = ''
    await workflowRecords.load({ page_size: workflowRecords.pageSize })
    workflowRecords.searching = false
    workflowRecords.loading = false
    await router.push({ query: { ...router.currentRoute.value.query, search_text: undefined } })
  },
  handleTableChange: (page, filters, sorter) => {
    workflowRecords.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
      tags: filters.tags,
      search_text: workflowRecords.searchText,
    })
  },
  handleCardViewChange: (page) => {
    workflowRecords.load({
      page_size: workflowRecords.pageSize,
      page: page,
      search_text: workflowRecords.searchText,
    })
  },
  load: async (params) => {
    workflowRecords.loading = true
    const res = await workflowAPI('list', params)
    if (res.status == 200) {
      workflowRecords.data = res.data.workflows.map(item => {
        item.create_time = formatTime(item.create_time)
        item.update_time = formatTime(item.update_time)
        item.key = item.wid
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

watch(() => workflowDisplayPreference.value, (newVal) => {
  if (workflowDisplayPreference.value == 'card') {
    workflowRecords.load({ page_size: 16 })
    workflowRecords.pageSize = 16
  } else {
    workflowRecords.load({ page_size: 10 })
  }
  userSettingsStore.setWorkflowDisplayPreference(workflowDisplayPreference.value)
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
    await userWorkflowsStore.refreshWorkflows()
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
    await userWorkflowsStore.refreshWorkflows()
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

const toggleFastAccess = async (workflow) => {
  if (workflow.is_fast_access) {
    await deleteWorkflowFromFastAccess(workflow.wid)
  } else {
    await addWorkflowToFastAccess(workflow.wid)
  }
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
  await userWorkflowsStore.refreshWorkflows()
  nextTick(async () => {
    await router.push({ name: 'WorkflowEditor', params: { workflowId: workflow.wid } })
  })
}
const clone = async (workflowWid) => {
  loading.value = true
  const record = workflowRecords.data.find(item => item.wid == workflowWid)
  record.loading = true
  const getWorkflowResponse = await workflowAPI('get', { wid: workflowWid })
  if (getWorkflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.clone_failed'))
    return
  }
  const createResponse = await workflowAPI('create', {
    ...getWorkflowResponse.data,
    title: getWorkflowResponse.data.title + ' ' + t('workspace.workflowSpace.clone_workflow'),
  })
  record.loading = false
  if (createResponse.status != 200) {
    message.error(createResponse.data.msg)
    return
  }
  const workflow = createResponse.data
  await userWorkflowsStore.refreshWorkflows()
  nextTick(async () => {
    await router.push({ name: 'WorkflowUse', params: { workflowId: workflow.wid } })
  })
}

const openRecord = async (record) => {
  await router.push({ name: 'WorkflowUse', params: { workflowId: record.wid }, query: { rid: record.rid } })
}
</script>

<template>
  <a-flex vertical gap="middle">
    <a-flex wrap="wrap" align="middle" justify="space-between" gap="small">
      <InputSearch v-model="workflowRecords.searchText" @search="workflowRecords.searchWorkflows"
        @clear-search="workflowRecords.clearSearch" />
      <a-flex justify="flex-end">
        <a-space>
          <a-segmented size="middle" v-model:value="workflowDisplayPreference"
            :options="[{ value: 'card' }, { value: 'list' }]">
            <template #label="{ value }">
              <template v-if="value == 'card'">
                <a-tooltip :title="t('common.card_view')">
                  <ViewGridCard />
                </a-tooltip>
              </template>
              <template v-else>
                <a-tooltip :title="t('common.table_view')">
                  <ListOne />
                </a-tooltip>
              </template>
            </template>
          </a-segmented>
          <a-button type="primary" @click="add">
            <Plus />
            {{ t('workspace.workflowSpaceMain.create_workflow') }}
          </a-button>
          <WorkflowRunRecordsDrawer buttonType="default" openType="simple" :showWorkflowTitle="true"
            @open-record="openRecord" />
        </a-space>
      </a-flex>
    </a-flex>

    <a-row v-if="workflowDisplayPreference == 'card'" :gutter="[16, 16]" style="margin-bottom: 80px;">
      <a-col :xxl="6" :xl="8" :lg="8" :md="12" :sm="24" :xs="24" v-for="record in workflowRecords.data"
        :key="record.pid">
        <router-link :to="{ name: 'WorkflowUse', params: { workflowId: record.wid } }">
          <WorkflowCard :title="record.title" :tags="record.tags" :images="record.images" :brief="record.brief"
            :author="false" :datetime="record.update_time" :forks="false" :extra="true" :loading="record.loading"
            :starred="record.is_fast_access" @star="toggleFastAccess(record)" @clone="clone(record.wid)"
            @delete="deleteWorkflow(record.wid)" />
        </router-link>
      </a-col>
      <a-col :span="24">
        <a-flex justify="flex-end">
          <a-pagination v-model:current="workflowRecords.current" v-model:pageSize="workflowRecords.pageSize"
            :total="workflowRecords.total" show-less-items @change="workflowRecords.handleCardViewChange" />
        </a-flex>
      </a-col>
    </a-row>

    <a-table v-else :loading="loading || workflowRecords.loading" :columns="workflowRecords.columns"
      :customRow="workflowRecords.customRow" :data-source="workflowRecords.data"
      :pagination="workflowRecords.pagination" @change="workflowRecords.handleTableChange">
      <template #headerCell="{ column }">
        <template v-if="column.key === 'title'">
          <WholeSiteAccelerator />
          {{ t('workspace.workflowSpaceMain.workflow_title') }}
        </template>
        <template v-else-if="column.key === 'tags'">
          <TagOne />
          {{ t('workspace.workflowSpaceMain.tags') }}
        </template>
        <template v-else-if="column.key === 'update_time'">
          <Time />
          {{ t('workspace.workflowSpaceMain.update_time') }}
        </template>
        <template v-else-if="column.key === 'action'">
          <Control />
          {{ t('common.action') }}
        </template>
      </template>

      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'title'">
          <a-space>
            <a-typography-text class="workflow-title">
              {{ record.title }}
            </a-typography-text>
            <a-tooltip :title="t('workspace.workflowSpace.add_to_fast_access')" v-if="!record.is_fast_access">
              <a-typography-link @click=addWorkflowToFastAccess(record.wid)>
                <Star v-show="workflowRecords.hoverRowWid == record.wid" />
              </a-typography-link>
            </a-tooltip>
            <a-tooltip :title="t('workspace.workflowSpace.delete_from_fast_access')" v-else>
              <a-typography-link @click=deleteWorkflowFromFastAccess(record.wid)>
                <Star theme="filled" />
              </a-typography-link>
            </a-tooltip>
          </a-space>
        </template>
        <template v-else-if="column.key === 'tags'">
          <a-space>
            <a-tag :color="tag.color" v-for=" tag in record.tags " :key="tag.tid">
              {{ tag.title }}
            </a-tag>
          </a-space>
        </template>
        <template v-else-if="column.key === 'action'">
          <div class="action-container">

            <a-tooltip :title="t('workspace.workflowSpace.clone_workflow')">
              <a-button type="text" @click.prevent="clone(record.wid)">
                <template #icon>
                  <Copy />
                </template>
              </a-button>
            </a-tooltip>

            <a-tooltip :title="t('workspace.workflowSpace.delete')">
              <a-popconfirm :title="t('workspace.workflowSpace.delete_confirm')" @confirm="deleteWorkflow(record.wid)">
                <a-button type="text" danger>
                  <template #icon>
                    <Delete />
                  </template>
                </a-button>
              </a-popconfirm>
            </a-tooltip>
          </div>
        </template>
      </template>

      <template #emptyText>
        <a-typography-paragraph type="secondary">
          {{ t('components.workspace.myWorkflows.no_workflows_1') }}
        </a-typography-paragraph>
        <a-typography-paragraph type="secondary">
          {{ t('components.workspace.myWorkflows.no_workflows_2') }}
          <router-link to="/workflow/?tab=official-workflow-templates">
            {{ t('workspace.workflowSpaceMain.official_workflow_template') }}
          </router-link>
        </a-typography-paragraph>
      </template>
    </a-table>
  </a-flex>
</template>
