<script setup>
import { onBeforeMount, ref, reactive, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import WorkflowCard from '@/components/workspace/WorkflowCard.vue'
import InputSearch from "@/components/InputSearch.vue"
import { formatTime } from '@/utils/util'
import { officialSiteAPI } from '@/api/remote'

const { t } = useI18n()
const router = useRouter()
const tags = ref([])
const tagsOptions = computed(() => {
  let options = [{
    label: t('common.all_tags'),
    value: 'all',
  }]
  options = options.concat(tags.value.map(tag => {
    return {
      label: tag.title,
      value: tag.tid,
    }
  }))
  return options
})

onBeforeMount(async () => {
  const searchText = router.currentRoute.value.query.search_text
  let searchTextQuery = {}
  if (searchText) {
    searchTextQuery = { search_text: searchText }
    workflowTemplates.searchText = searchText
  }
  const [templates, tagsResponse] = await Promise.all([
    workflowTemplates.load({ ...searchTextQuery }),
    officialSiteAPI('list_tags', {}),
  ])
  if (tagsResponse.status == 200) {
    tags.value = tagsResponse.data
  }
})

const workflowTemplates = reactive({
  data: [],
  loading: true,
  current: 1,
  pageSize: 24,
  total: 0,
  sorter: {
    field: 'official_order',
    order: 'descend',
  },
  selectTag: 'all',
  selectTagChange: async () => {
    workflowTemplates.loading = true
    await workflowTemplates.load({
      tags: [workflowTemplates.selectTag],
    })
    workflowTemplates.loading = false
  },
  handlePaginationChange: (page, pageSize) => {
    workflowTemplates.load({
      page_size: pageSize,
      page: page,
    })
  },
  searching: false,
  searchText: '',
  searchWorkflows: async () => {
    workflowTemplates.searching = true
    await workflowTemplates.load({ search_text: workflowTemplates.searchText })
    workflowTemplates.searching = false
    await router.push({ query: { ...router.currentRoute.value.query, search_text: workflowTemplates.searchText } })
  },
  clearSearch: async () => {
    workflowTemplates.searching = true
    workflowTemplates.searchText = ''
    await workflowTemplates.load({})
    workflowTemplates.searching = false
    await router.push({ query: { ...router.currentRoute.value.query, search_text: undefined } })
  },
  load: async (params) => {
    workflowTemplates.loading = true
    const res = await officialSiteAPI('list_templates', {
      is_official: true,
      client: 'PC',
      page_size: workflowTemplates.pageSize,
      page: workflowTemplates.current,
      sort_field: workflowTemplates.sorter.field,
      sort_order: workflowTemplates.sorter.order,
      tags: [workflowTemplates.selectTag],
      ...params
    })
    if (res.status == 200) {
      workflowTemplates.data = res.data.templates.map(item => {
        item.create_time = formatTime(item.create_time)
        item.update_time = formatTime(item.update_time)
        return item
      })
    } else {
      message.error(res.msg)
    }
    workflowTemplates.total = res.data.total
    workflowTemplates.pageSize = res.data.page_size
    workflowTemplates.current = res.data.page
    workflowTemplates.loading = false
  }
})

const navigateToTemplate = async (tid) => {
  await router.push({ name: 'WorkflowTemplate', params: { workflowTemplateId: tid } })
}
</script>

<template>
  <a-flex vertical gap="middle">

    <a-flex justify="space-between">
      <InputSearch v-model="workflowTemplates.searchText" @search="workflowTemplates.searchWorkflows"
        @clear-search="workflowTemplates.clearSearch" />
      <a-select v-model:value="workflowTemplates.selectTag" style="width: 200px" :options="tagsOptions"
        @change="workflowTemplates.selectTagChange"></a-select>
    </a-flex>

    <a-spin :spinning="workflowTemplates.loading">
      <a-row :gutter="[16, 16]">
        <a-col :xl="6" :lg="8" :md="8" :sm="12" :xs="24" v-for="(template, index) in workflowTemplates.data"
          :key="template.tid" @click="navigateToTemplate(template.tid)">
          <WorkflowCard :id="template.tid" :title="template.title" :tags="template.tags" :images="template.images"
            :brief="template.brief" :author="template.user" :forks="false" />
        </a-col>
        <a-col :span="24">
          <a-flex justify="flex-end">
            <a-pagination v-model:current="workflowTemplates.current" v-model:pageSize="workflowTemplates.pageSize"
              :total="workflowTemplates.total" :hideOnSinglePage="true" show-less-items
              @change="workflowTemplates.handlePaginationChange" />
          </a-flex>
        </a-col>
      </a-row>
    </a-spin>

  </a-flex>
  <a-divider />
</template>

<style>
.template-card {
  height: 335px;
}

.template-card .template-card-title-container {
  margin-top: 10px;
  margin-bottom: 10px;
}

.template-card .ant-card-body {
  height: 250px;
}

.template-card .ant-card-body .markdown-body {
  height: 100%;
  overflow-y: scroll;
}
</style>


<style scoped>
.card-image {
  width: 100%;
  height: 202px;
  object-fit: cover;
}
</style>