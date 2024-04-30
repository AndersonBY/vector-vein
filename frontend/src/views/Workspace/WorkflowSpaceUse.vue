<script setup>
import { onBeforeMount, onBeforeUnmount, ref, reactive } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { Down } from '@icon-park/vue-next'
import VueMarkdown from 'vue-markdown-render'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import ImageCarousel from "@/components/ImageCarousel.vue"
import WorkflowRunRecordsDrawer from "@/components/workspace/WorkflowRunRecordsDrawer.vue"
import AgentInvokeDataEdit from "@/components/workspace/workflowActions/AgentInvokeDataEdit.vue"
import RelatedWorkflowsModal from "@/components/workspace/RelatedWorkflowsModal.vue"
import WorkflowUse from "@/components/workspace/WorkflowUse.vue"
import { formatTime } from "@/utils/util"
import { getUIDesignFromWorkflow } from '@/utils/workflow'
import { workflowAPI, workflowRunRecordAPI } from "@/api/workflow"

const { t } = useI18n()
const loading = ref(true)
const userWorkflowsStore = useUserWorkflowsStore()
const route = useRoute()
const router = useRouter()
const workflowId = route.params.workflowId
const briefModalOpen = ref(false)
const briefModalWidth = ref(window.innerWidth <= 768 ? '90vw' : '60vw')
const inputFields = ref([])
const outputNodes = ref([])
const triggerNodes = ref([])

onBeforeMount(async () => {
  const getWorkflowRequest = workflowAPI('get', { wid: workflowId })
  const workflowResponse = await getWorkflowRequest
  if (workflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    await router.push({ name: 'WorkflowSpaceMain' })
    return
  }
  currentWorkflow.value = workflowResponse.data
  if (currentWorkflow.value.ui_design) {
    inputFields.value = currentWorkflow.value.ui_design.input_fields
    outputNodes.value = currentWorkflow.value.ui_design.output_nodes
    triggerNodes.value = currentWorkflow.value.ui_design.trigger_nodes
  } else {
    const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
    const reactiveUIDesign = reactive(uiDesign)
    inputFields.value = reactiveUIDesign.inputFields
    outputNodes.value = reactiveUIDesign.outputNodes
    triggerNodes.value = reactiveUIDesign.triggerNodes
  }

  savedWorkflow.value = currentWorkflow.value
  loading.value = false

  if (route.query.rid) {
    const recordRequest = workflowRunRecordAPI('get', { rid: route.query.rid })
    const recordResponse = await recordRequest
    try {
      setWorkflowRecord(recordResponse.data)
    } catch (error) {
      console.error(error)
      message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
    }
  }
})

onBeforeUnmount(() => {
  clearInterval(checkStatusTimer.value)
})

const currentWorkflow = ref({})
const savedWorkflow = ref({})
const saveTime = ref(0)

const checkStatusTimer = ref(null)
const workflowUseRef = ref()
const setWorkflowRecord = (record) => {
  workflowUseRef.value.setWorkflowRecord(record)
}

const deleteWorkflow = async () => {
  const response = await workflowAPI('delete', { wid: currentWorkflow.value.wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_success'))
    userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid)
    userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid, true)
    await router.push({ name: 'WorkflowSpaceMain' })
  } else {
    message.error(t('workspace.workflowSpace.delete_failed'))
  }
}

const openEditor = async () => {
  await router.push({ name: 'WorkflowEditor', params: { workflowId: workflowId } })
}
</script>

<template>
  <div class="space-container" v-if="loading">
    <a-skeleton active />
  </div>
  <div class="space-container" v-else>
    <a-flex justify="space-between" align="flex-end">
      <div>
        <a-typography-title>
          {{ currentWorkflow.title }}
        </a-typography-title>
        <a-space>
          <a-typography-text type="secondary">
            {{ t('workspace.workflowSpace.update_time', { time: formatTime(currentWorkflow.update_time) }) }}
          </a-typography-text>
          <a-divider type="vertical" />
          <a-typography-link @click="briefModalOpen = true">
            {{ t('workspace.workflowSpace.brief') }}
            <a-modal :open="briefModalOpen" :title="t('workspace.workflowSpace.brief')" :width="briefModalWidth"
              :footer="null" class="introduction-modal" @cancel="briefModalOpen = false">
              <ImageCarousel :images="currentWorkflow.images" />
              <VueMarkdown v-highlight :source="currentWorkflow.brief"
                class="custom-scrollbar markdown-body custom-hljs" />
            </a-modal>
          </a-typography-link>
          <RelatedWorkflowsModal :workflowId="workflowId" />
          <a-divider type="vertical" />
          <a-tag :color="tag.color" v-for="(tag, index) in currentWorkflow.tags" :key="index">
            {{ tag.title }}
          </a-tag>
        </a-space>
      </div>
      <div>
        <a-space>
          <WorkflowRunRecordsDrawer :workflowId="workflowId" @open-record="setWorkflowRecord" />
          <a-dropdown>
            <template #overlay>
              <a-menu>
                <AgentInvokeDataEdit :workflow-data="savedWorkflow" type="menuItem"
                  :key="`AgentInvokeDataEdit-${saveTime}`" />
                <a-menu-item key="edit" @click="openEditor">
                  {{ t('workspace.workflowSpace.edit') }}
                </a-menu-item>
                <a-popconfirm placement="leftTop" :title="t('workspace.workflowSpace.delete_confirm')"
                  @confirm="deleteWorkflow">
                  <a-menu-item key="delete">
                    <a-typography-text type="danger">
                      {{ t('workspace.workflowSpace.delete') }}
                    </a-typography-text>
                  </a-menu-item>
                </a-popconfirm>
              </a-menu>
            </template>
            <a-button>
              {{ t('workspace.workflowSpace.more_actions') }}
              <Down />
            </a-button>
          </a-dropdown>
        </a-space>
      </div>
    </a-flex>
    <a-divider />
    <WorkflowUse ref="workflowUseRef" :workflow="currentWorkflow" :isTemplate="false" />
  </div>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}

.main-use-container {
  padding-bottom: 60px;
}

.ui-special-item {
  margin-bottom: 24px;
}

.html-iframe {
  border: 2px solid #dedede;
  border-radius: 10px;
  width: 100%;
  min-height: 80vh;
}

.text-output-title {
  color: #005b79;
}
</style>