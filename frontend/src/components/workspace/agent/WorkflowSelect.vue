<script setup>
import { onBeforeMount, ref, reactive, computed, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { WholeSiteAccelerator, TagOne, Time, FullSelection } from '@icon-park/vue-next'
import AuthorComponent from "@/components/AuthorComponent.vue"
import InputSearch from "@/components/InputSearch.vue"
import TextOutput from "@/components/TextOutput.vue"
import { formatTime } from '@/utils/util'
import { workflowAPI, workflowTemplateAPI, workflowTagAPI } from "@/api/workflow"

const props = defineProps({
  showUser: {
    type: Boolean,
    required: false,
    default: false,
  },
})
const selectedFlows = defineModel()

const updateSelectedRowKeysFromSelectedFlows = () => {
  const workflowIds = Object.keys(selectedFlows.value.workflows)
  const templateIds = Object.keys(selectedFlows.value.templates)
  rowSelection.selectedRowKeys = [...workflowIds, ...templateIds]
}

watch(() => Object.keys(selectedFlows.value.workflows).length, () => {
  updateSelectedRowKeysFromSelectedFlows()
})
watch(() => Object.keys(selectedFlows.value.templates).length, () => {
  updateSelectedRowKeysFromSelectedFlows()
})

const selectType = ref('private')
const workflowOrTemplate = ref('workflow')
const workflowOrTemplateAPI = computed(() => {
  return workflowOrTemplate.value == 'workflow' ? workflowAPI : workflowTemplateAPI
})
const queryKey = computed(() => {
  return workflowOrTemplate.value == 'workflow' ? 'wid' : 'tid'
})
const pluralKey = computed(() => {
  return workflowOrTemplate.value == 'workflow' ? 'workflows' : 'templates'
})

const { t } = useI18n()
const loading = ref(true)
const tags = ref([])

onBeforeMount(async () => {
  const [workflowsResponse, tagsResponse] = await Promise.all([
    workflows.load({}),
    workflowTagAPI('list', {}),
  ])
  if (tagsResponse.status == 200) {
    tags.value = tagsResponse.data
  }
  updateSelectedRowKeysFromSelectedFlows()
  loading.value = false
})

const columns = [
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
    width: '150px',
  },
  {
    title: t('workspace.workflowSpaceMain.update_time'),
    key: 'update_time',
    dataIndex: 'update_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '160px',
  },
]
if (props.showUser) {
  columns.splice(1, 0, {
    title: t('common.vectorvein_user'),
    key: 'user',
    dataIndex: 'user',
    width: '200px',
  })
}

const workflows = reactive({
  columns: columns,
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  pagination: computed(() => ({
    total: workflows.total,
    current: workflows.current,
    pageSize: workflows.pageSize,
  })),
  selectTag: 'all',
  selectTagChange: async () => {
    workflows.loading = true
    await workflows.load({ tags: [workflows.selectTag] })
    workflows.loading = false
  },
  searching: false,
  searchText: '',
  searchWorkflows: async () => {
    workflows.loading = true
    workflows.searching = true
    await workflows.load({ search_text: workflows.searchText })
    workflows.searching = false
    workflows.loading = false
  },
  clearSearch: async () => {
    workflows.loading = true
    workflows.searching = true
    workflows.searchText = ''
    await workflows.load({})
    workflows.searching = false
    workflows.loading = false
  },
  handleTableChange: (page, filters, sorter) => {
    workflows.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
      tags: filters.tags,
      search_text: workflows.searchText,
    })
  },
  load: async (params) => {
    workflows.loading = true
    const res = await workflowOrTemplateAPI.value('list', {
      ...params,
      owner_type: selectType.value,
    })
    if (res.status == 200) {
      workflows.data = res.data[pluralKey.value].map(item => {
        item.key = item[queryKey.value]
        item.create_time = formatTime(item.create_time)
        item.update_time = formatTime(item.update_time)
        return item
      })
    } else {
      message.error(res.msg)
    }
    workflows.total = res.data.total
    workflows.pageSize = res.data.page_size
    workflows.current = res.data.page
    workflows.loading = false
  },
})

const rowSelection = reactive({
  preserveSelectedRowKeys: true,
  selectedRowKeys: [],
  onSelect: (record, selected, selectedRows, nativeEvent) => {
    if (selected) {
      if (!rowSelection.selectedRowKeys.includes(record[queryKey.value])) {
        // rowSelection.selectedRowKeys.push(record[queryKey.value])
        selectedFlows.value[pluralKey.value][record[queryKey.value]] = record
      }
    } else {
      // rowSelection.selectedRowKeys = rowSelection.selectedRowKeys.filter(item => item != record[queryKey.value])
      delete selectedFlows.value[pluralKey.value][record[queryKey.value]]
    }
  },
  onChange: (selectedRowKeys, selectedRows) => {
    rowSelection.selectedRowKeys = selectedRowKeys
  },
})
</script>

<template>
  <a-spin :spinning="loading">
    <a-flex vertical gap="small">
      <a-flex wrap="wrap" justify="space-between" gap="small" align="flex-end">
        <div>
          <InputSearch v-model="workflows.searchText" @search="workflows.searchWorkflows"
            @clear-search="workflows.clearSearch" />
        </div>
        <a-space direction="vertical">
          <a-radio-group v-model:value="workflowOrTemplate" button-style="solid" @change="workflows.load()">
            <a-radio-button value="workflow">
              {{ t('common.workflow') }}
            </a-radio-button>
          </a-radio-group>
          <a-radio-group v-model:value="selectType" button-style="solid" @change="workflows.load()"
            v-if="workflowOrTemplate == 'template'">
            <a-radio-button value="private">
              {{ t('common.my') }}
            </a-radio-button>
            <a-radio-button value="official">
              {{ t('common.official') }}
            </a-radio-button>
            <a-radio-button value="community">
              {{ t('common.community') }}
            </a-radio-button>
          </a-radio-group>
        </a-space>
      </a-flex>

      <a-table :loading="workflows.loading" :columns="workflows.columns" :data-source="workflows.data"
        :pagination="workflows.pagination" @change="workflows.handleTableChange" :row-selection="rowSelection">
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
            <FullSelection />
            {{ t('common.action') }}
          </template>
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <a-popover>
              <template #content>
                <TextOutput :text="record.brief" :showCopy="false" />
              </template>
              <a-typography-text class="workflow-title">
                {{ record.title }}
              </a-typography-text>
            </a-popover>
          </template>
          <template v-else-if="column.key === 'user'">
            <AuthorComponent :author="record.user" fontColor="#000" />
          </template>
          <template v-else-if="column.key === 'tags'">
            <a-space wrap>
              <a-tag :color="tag.color" v-for=" tag in record.tags " :key="tag.tid">
                {{ tag.title }}
              </a-tag>
            </a-space>
          </template>
        </template>

        <template #emptyText>
          <a-typography-paragraph type="secondary">
            {{ t('components.workspace.myWorkflows.no_workflows_1') }}
          </a-typography-paragraph>
          <a-typography-paragraph type="secondary">
            {{ t('components.workspace.myWorkflows.no_workflows_2') }}
            <a-typography-link href="/workspace/workflow/?tab=official-workflow-templates">
              {{ t('workspace.workflowSpaceMain.official_workflow_template') }}
            </a-typography-link>
          </a-typography-paragraph>
        </template>
      </a-table>
    </a-flex>
  </a-spin>
</template>