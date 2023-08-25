<script setup>
import { onBeforeMount, ref, reactive, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { WholeSiteAccelerator, TagOne, Time } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { getUIDesignFromWorkflow } from '@/utils/workflow'
import { workflowAPI, workflowTagAPI } from "@/api/workflow"

const data = defineModel()
const emit = defineEmits(['selected'])

const { t } = useI18n()
const loading = ref(true)
const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
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
  columns: [
    {
      name: t('workspace.workflowSpaceMain.workflow_title'),
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: t('workspace.workflowSpaceMain.tags'),
      key: 'tags',
      dataIndex: 'tags',
      filters: computed(() => tags.value.map(tag => ({ text: tag.title, value: tag.tid }))),
      width: '300px',
    },
    {
      title: t('workspace.workflowSpaceMain.update_time'),
      key: 'update_time',
      dataIndex: 'update_time',
      sorter: true,
      sortDirections: ['descend', 'ascend'],
      width: '200px',
    }
  ],
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
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
          await getWorkflowDetail(record.wid)
          emit('selected', data.value)
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
      search_text: workflowRecords.searchText,
    })
  },
  load: async (params) => {
    workflowRecords.loading = true
    const res = await workflowAPI('list', params)
    if (res.status == 200) {
      workflowRecords.data = res.data.workflows.map(item => {
        item.create_time = new Date(parseInt(item.create_time)).toLocaleString()
        item.update_time = new Date(parseInt(item.update_time)).toLocaleString()
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

const selectedWorkflow = ref({})
const getWorkflowDetail = async (wid) => {
  loading.value = true
  const res = await workflowAPI('get', { wid })

  if (res.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    return
  }
  selectedWorkflow.value = res.data
  selectedWorkflow.value.data.nodes.forEach((node) => {
    if (node.category == "vectorDb") {
      node.data.template.database.options = userDatabases.value.filter((database) => {
        return database.status == 'VALID'
      }).map((item) => {
        return {
          value: item.vid,
          label: item.name,
        }
      })
    }
  })
  const uiDesign = getUIDesignFromWorkflow(selectedWorkflow.value)
  const reactiveUIDesign = reactive(uiDesign)
  data.value = {
    wid: wid,
    title: selectedWorkflow.value.title,
    inputFields: reactiveUIDesign.inputFields,
    outputNodes: reactiveUIDesign.outputNodes,
    workflowInvokeOutputNodes: reactiveUIDesign.workflowInvokeOutputNodes,
  }
  loading.value = false
}
</script>

<template>
  <a-spin :spinning="loading">
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
        </a-row>
      </a-col>

      <a-col :span="24">
        <a-table :loading="workflowRecords.loading" :columns="workflowRecords.columns"
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
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'title'">
              <a-space>
                <a-typography-text class="workflow-title">
                  {{ record.title }}
                </a-typography-text>
              </a-space>
            </template>
            <template v-else-if="column.key === 'tags'">
              <a-space>
                <a-tag :color="tag.color" v-for=" tag  in  record.tags " :key="tag.tid">
                  {{ tag.title }}
                </a-tag>
              </a-space>
            </template>
          </template>
        </a-table>
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