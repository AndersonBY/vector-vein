<script setup>
import { onBeforeMount, defineComponent, ref, reactive, computed, nextTick } from "vue"
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import VueMarkdown from 'vue-markdown-render'
import { officialSiteAPI } from '@/api/remote'

defineComponent({
  name: 'WorkflowTemplatesMarket',
})

const { t } = useI18n()
const loading = ref(true)
const router = useRouter()
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)
const tags = ref([])

onBeforeMount(async () => {
  loading.value = false
  const [templates, tagsResponse] = await Promise.all([
    workflowTemplates.load({ is_official: true }),
    officialSiteAPI('list_tags', {}),
  ])
  if (tagsResponse.status == 200) {
    tags.value = tagsResponse.data
  }
  loading.value = false
})

const workflowTemplates = reactive({
  data: [],
  loading: true,
  current: 1,
  pageSize: 100,
  total: 0,
  pagination: computed(() => ({
    total: workflowTemplates.total,
    current: workflowTemplates.current,
    pageSize: workflowTemplates.pageSize,
  })),
  selectTag: 'all',
  selectTagChange: async () => {
    workflowTemplates.loading = true
    await workflowTemplates.load({
      tags: [workflowTemplates.selectTag],
      is_official: true,
    })
    workflowTemplates.loading = false
  },
  hoverRowWid: null,
  handleTableChange: (page, filters, sorter) => {
    workflowTemplates.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
      tags: filters.tags,
    })
  },
  load: async (params) => {
    workflowTemplates.loading = true
    const res = await officialSiteAPI('list_templates', {
      client: 'PC',
      ...params
    })
    if (res.status == 200) {
      workflowTemplates.data = res.data.templates.map(item => {
        item.create_time = new Date(item.create_time).toLocaleString()
        item.update_time = new Date(item.update_time).toLocaleString()
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
</script>

<template>
  <div v-if="loading">
    <a-skeleton active />
  </div>
  <a-row align="middle" :gutter="[16, 16]" v-else>
    <a-col :span="24">
      <a-row type="flex" align="middle" justify="space-between">
        <a-col flex="auto">
          <a-typography-title :title="3">
            {{ t('workspace.workflowSpaceMain.official_workflow_template') }}
          </a-typography-title>
        </a-col>
      </a-row>
    </a-col>

    <a-col :span="24">
      <a-space>
        <a-typography-text>
          {{ t('workspace.workflowTemplate.workflow_template_tags') }}
        </a-typography-text>
        <a-radio-group v-model:value="workflowTemplates.selectTag" button-style="solid"
          @change="workflowTemplates.selectTagChange">
          <a-radio-button value="all">
            {{ t('common.all') }}
          </a-radio-button>
          <template v-for="tag in tags" :key="tag.tid">
            <a-radio-button :value="tag.tid" v-if="language == tag.language">
              {{ tag.title }}
            </a-radio-button>
          </template>
        </a-radio-group>
      </a-space>
    </a-col>

    <a-divider />

    <a-col :span="24">
      <a-spin :spinning="workflowTemplates.loading">
        <a-row :gutter="[16, 16]">
          <a-col :lg="6" :md="8" :sm="12" :xs="24" v-for="template in workflowTemplates.data" :key="template.tid"
            @click="router.push(`/workflow/template/${template.tid}`)">
            <a-card class="template-card" hoverable>
              <template #title>
                <div class="template-card-title-container">
                  <a-typography-title :level="4">
                    {{ template.title }}
                  </a-typography-title>
                  <a-tag v-for="(tag, index) in template.tags" :key="index" :color="tag.color">
                    {{ tag.title }}
                  </a-tag>
                </div>
              </template>
              <a-carousel autoplay arrows v-if="template.images.length > 0">
                <div v-for="(image, index) in template.images" :key="index">
                  <img :src="image" class="card-image" />
                </div>
              </a-carousel>
              <VueMarkdown v-highlight :source="template.brief" class="custom-scrollbar markdown-body custom-hljs"
                v-else />
            </a-card>
          </a-col>
        </a-row>
      </a-spin>
    </a-col>

  </a-row>
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