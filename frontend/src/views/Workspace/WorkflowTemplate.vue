<script setup>
import { onBeforeMount, defineComponent, ref } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { message } from 'ant-design-vue'
import VueMarkdown from 'vue-markdown-render'
import { officialSiteAPI } from '@/api/remote'
import { workflowAPI } from '@/api/workflow'

defineComponent({
  name: 'WorkflowTemplate',
})

const { t } = useI18n()
const loading = ref(true)
const updating = ref(false)
const route = useRoute()
const router = useRouter()
const userWorkflowsStore = useUserWorkflowsStore()
const workflowTemplateId = route.params.workflowTemplateId
const templateData = ref({})

onBeforeMount(async () => {
  const response = await officialSiteAPI('get_template', { tid: workflowTemplateId })
  if (response.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    router.push({ name: 'Workspace' })
    return
  }
  templateData.value = response.data
  loading.value = false
})

const addTemplateToUserWorkflows = async () => {
  const response = await workflowAPI('create', templateData.value)
  if (response.status == 200) {
    message.success(t('workspace.workflowTemplate.add_success'))
  } else {
    message.error(t('workspace.workflowTemplate.add_failed'))
    return
  }
  const workflow = templateData.value
  userWorkflowsStore.addUserWorkflow(workflow)
  userWorkflowsStore.setUserWorkflowsTotal(userWorkflowsStore.userWorkflowsTotal + 1)
  router.push({ name: 'WorkflowUse', params: { workflowId: response.data.wid } })
}
</script>

<template>
  <div class="space-container" v-if="loading">
    <a-skeleton active />
  </div>
  <a-spin :spinning="updating" class="space-container" v-else>
    <a-breadcrumb>
      <a-breadcrumb-item>
        <router-link to="/workflow?tab=official-workflow-templates">
          {{ t('workspace.workflowSpaceMain.official_workflow_template') }}
        </router-link>
      </a-breadcrumb-item>
      <a-breadcrumb-item>{{ templateData.title }}</a-breadcrumb-item>
    </a-breadcrumb>
    <a-row justify="space-around">
      <a-col :lg="12" :md="12" :sm="24" :xs="24">
        <a-typography-title>
          {{ `${t('workspace.workflowTemplate.template')}: ${templateData.title}` }}
        </a-typography-title>
        <div style="margin-bottom: 10px;">
          <a-space>
            <a-typography-text type="secondary">
              {{ t('common.update_time_format', {
                time: new
                  Date(templateData.update_time).toLocaleString()
              }) }}
            </a-typography-text>
            <a-divider type="vertical" />
            <a-tag :color="tag.color" v-for="(tag, index) in templateData.tags" :key="index">
              {{ tag.title }}
            </a-tag>
          </a-space>
        </div>
        <div style="margin-bottom: 10px;">
          <a-space>
            <a-typography-text type="secondary">
              {{ t('workspace.workflowTemplate.author', {
                author: 'VectorVein'
              }) }}
            </a-typography-text>
            <a-divider type="vertical" />
            <a-typography-text type="secondary" v-if="templateData.used_count > 10">
              {{ t('workspace.workflowTemplate.used_count', {
                count: templateData.used_count
              }) }}
            </a-typography-text>
          </a-space>
        </div>
        <a-space>
          <a-button type="primary" @click="addTemplateToUserWorkflows">
            {{ t('workspace.workflowTemplate.add_to_my_workflows') }}
          </a-button>
        </a-space>
      </a-col>
    </a-row>

    <a-divider />

    <a-row justify="space-around">
      <a-col :lg="12" :md="12" :sm="24" :xs="24" v-if="templateData.images.length > 0">
        <a-carousel autoplay arrows dots-class="slick-dots slick-thumb">
          <template #customPaging="props">
            <a>
              <img :src="templateData.images[props.i]" />
            </a>
          </template>
          <div v-for="(image, index) in templateData.images" :key="index">
            <img :src="image" />
          </div>
        </a-carousel>
      </a-col>
      <a-col :lg="12" :md="12" :sm="24" :xs="24">
        <VueMarkdown v-highlight :source="templateData.brief" class="custom-scrollbar markdown-body custom-hljs" />
      </a-col>
    </a-row>
  </a-spin>
</template>

<style scoped>
:deep(.slick-dots) {
  position: relative;
  height: auto;
}

:deep(.slick-slide img) {
  border: 5px solid #fff;
  display: block;
  margin: auto;
  max-width: 80%;
  max-height: 60vh;
}

:deep(.slick-arrow) {
  display: none !important;
}

:deep(.slick-thumb) {
  bottom: 0px;
}

:deep(.slick-thumb li) {
  width: 60px;
  height: 45px;
}

:deep(.slick-thumb li img) {
  width: 100%;
  height: 100%;
  filter: grayscale(100%);
  display: block;
}

:deep .slick-thumb li.slick-active img {
  filter: grayscale(0%);
}
</style>