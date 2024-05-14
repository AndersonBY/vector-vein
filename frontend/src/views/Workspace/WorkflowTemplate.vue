<script setup>
import { onBeforeMount, ref } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { message } from 'ant-design-vue'
import { BranchTwo, DoubleRight, DoubleLeft } from '@icon-park/vue-next'
import VueMarkdown from 'vue-markdown-render'
import AuthorComponent from "@/components/AuthorComponent.vue"
import ImageCarousel from "@/components/ImageCarousel.vue"
import WorkflowUse from "@/components/workspace/WorkflowUse.vue"
import RelatedWorkflowsModal from "@/components/workspace/RelatedWorkflowsModal.vue"
import { officialSiteAPI } from '@/api/remote'
import { workflowAPI } from '@/api/workflow'

const { t } = useI18n()
const loading = ref(true)
const updating = ref(false)
const addingTemplate = ref(false)
const route = useRoute()
const router = useRouter()
const userWorkflowsStore = useUserWorkflowsStore()
const workflowTemplateId = route.params.workflowTemplateId
const templateData = ref({})
const collapsed = ref(false)
const showMask = ref(true)

onBeforeMount(async () => {
  const response = await officialSiteAPI('get_template', { tid: workflowTemplateId })
  if (response.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    router.push({ name: 'WorkflowSpaceMain' })
    return
  }
  templateData.value = response.data
  loading.value = false
})

const addTemplateToUserWorkflows = async () => {
  addingTemplate.value = true
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
  addingTemplate.value = false
  await router.push({ name: 'WorkflowUse', params: { workflowId: response.data.wid } })
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
    <a-row :gutter="[16, 8]" style="margin-top: 30px; padding: 0 10px 30px;">
      <a-col :xl="collapsed ? 24 : 16" :lg="collapsed ? 24 : 16" :md="24" :xs="24" style="height: 100%;">
        <a-button type="primary" shape="circle" class="collapse-button" @click="collapsed = !collapsed">
          <template #icon>
            <DoubleRight v-if="!collapsed" />
            <DoubleLeft v-else />
          </template>
        </a-button>
        <div class="workflow-use-mask" v-if="showMask">
          <a-button type="primary" @click="showMask = false">
            {{ t('workspace.workflowTemplate.test_run_template') }}
          </a-button>
          <a-typography-text class="hint">
            {{ t('workspace.workflowTemplate.test_run_template_hint1') }}
          </a-typography-text>
        </div>
        <WorkflowUse :workflow="templateData" :isTemplate="true" />
      </a-col>

      <a-col :xl="collapsed ? 24 : 8" :lg="collapsed ? 24 : 8" :md="24" :xs="24"
        style="display: flex; flex-direction: column; gap: 16px;">
        <a-card>
          <template #title>
            <a-space direction="vertical" style="width: 100%; margin-top: 8px; margin-bottom: 8px;">
              <a-typography-title class="template-title" :level="1" :ellipsis="{ rows: 2 }"
                :content="templateData.title">
              </a-typography-title>

              <div style="display: flex; justify-content: space-between; align-items: center;">
                <AuthorComponent :author="templateData.user" :time="parseInt(templateData.update_time)"
                  fontColor="#232323" />
                <RelatedWorkflowsModal :workflowId="workflowTemplateId" :isTemplate="true" />
              </div>
            </a-space>
          </template>
          <a-space direction="vertical" style="width: 100%; margin-top: 8px; margin-bottom: 8px;">
            <a-button type="primary" size="large" block @click="addTemplateToUserWorkflows" :loading="addingTemplate"
              style="margin-bottom: 10px;">
              {{ t('workspace.workflowTemplate.add_to_my_workflows') }}
              <a-divider type="vertical" style="border-inline-start-color: rgb(255, 255, 255);" />
              <BranchTwo />{{ templateData.used_count }}
            </a-button>

            <a-button v-if="templateData.is_owner" type="primary" @click="openEditor" block>
              {{ t('workspace.workflowTemplate.edit_template') }}
            </a-button>

            <ImageCarousel v-if="templateData.images?.length > 0" :images="templateData.images" />

            <VueMarkdown style="width: 100%" v-highlight :source="templateData.brief" :options="{ html: true }"
              class="custom-scrollbar markdown-body custom-hljs" />
          </a-space>
        </a-card>
      </a-col>

    </a-row>
  </a-spin>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}

.workflow-use-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: center;
  align-items: center;
}

.workflow-use-mask .hint {
  color: #ffffffbd;
}

.collapse-button {
  position: absolute;
  top: 60px;
  right: -40px;
  z-index: 10;
  transform: translate(-50%, 0);
  box-shadow: 0 0 #0000, 0 0 #0000, 0 4px 6px -1px rgba(0, 0, 0, .2), 0 2px 4px -2px rgba(0, 0, 0, .3);
}

.template-title {
  white-space: wrap;
}
</style>