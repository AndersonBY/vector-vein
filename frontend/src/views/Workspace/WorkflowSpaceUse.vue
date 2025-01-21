<script setup>
import { onBeforeMount, onBeforeUnmount, ref, reactive, h } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { Modal, message, TypographyTitle } from 'ant-design-vue'
import { Down } from '@icon-park/vue-next'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import ImageCarousel from "@/components/ImageCarousel.vue"
import WorkflowRunRecordsDrawer from "@/components/workspace/WorkflowRunRecordsDrawer.vue"
import AgentInvokeDataEdit from "@/components/workspace/workflowActions/AgentInvokeDataEdit.vue"
import RelatedWorkflowsModal from "@/components/workspace/RelatedWorkflowsModal.vue"
import WorkflowUse from "@/components/workspace/WorkflowUse.vue"
import ModelProviderTag from "@/components/workspace/ModelProviderTag.vue"
import TextOutput from "@/components/TextOutput.vue"
import { formatTime } from "@/utils/util"
import { getUIDesignFromWorkflow, extractModels } from '@/utils/workflow'
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
const llmModels = ref(new Set())

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
  llmModels.value = extractModels(currentWorkflow.value)
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
  Modal.confirm({
    title: h(
      TypographyTitle,
      { type: 'danger', level: 3, style: { marginBottom: 0 } },
      () => t('workspace.workflowSpace.delete_confirm')
    ),
    okText: t('common.yes'),
    okType: 'danger',
    cancelText: t('common.no'),
    maskClosable: true,
    async onOk() {
      const response = await workflowAPI('delete', { wid: currentWorkflow.value.wid })
      if (response.status == 200) {
        message.success(t('workspace.workflowSpace.delete_success'))
        userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid)
        userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid, true)
        await router.push({ name: 'WorkflowSpaceMain' })
      } else {
        message.error(t('workspace.workflowSpace.delete_failed'))
      }
    },
    onCancel() {
    },
  })
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
    <a-typography-title>
      {{ currentWorkflow.title }}
    </a-typography-title>
    <a-flex justify="space-between" align="flex-end" wrap="wrap" gap="small">
      <a-flex vertical gap="small">
        <a-flex wrap="wrap" gap="small">
          <a-typography-text type="secondary">
            {{ t('workspace.workflowSpace.update_time', { time: formatTime(currentWorkflow.update_time) }) }}
            <a-tooltip :title="t('workspace.workflowSpace.version_tip')">
              <a-tag :bordered="false">
                v{{ currentWorkflow.version }}
              </a-tag>
            </a-tooltip>
          </a-typography-text>
          <a-divider type="vertical" />
          <a-typography-link @click="briefModalOpen = true">
            {{ t('workspace.workflowSpace.brief') }}
            <a-modal :open="briefModalOpen" :title="t('workspace.workflowSpace.brief')" :width="briefModalWidth"
              :footer="null" class="introduction-modal" @cancel="briefModalOpen = false">
              <ImageCarousel :images="currentWorkflow.images" />
              <TextOutput :text="currentWorkflow.brief" :showCopy="false" />
            </a-modal>
          </a-typography-link>
          <RelatedWorkflowsModal :workflowId="workflowId" />
        </a-flex>
        <a-flex v-if="currentWorkflow.tags.length > 0" gap="small" align="center">
          <a-typography-text type="secondary">
            {{ t('common.tags') }}:
          </a-typography-text>
          <a-tag :color="tag.color" v-for="(tag, index) in currentWorkflow.tags" :key="index">
            {{ tag.title }}
          </a-tag>
        </a-flex>
        <a-flex v-if="llmModels.size > 0" gap="small" align="center">
          <a-typography-text type="secondary">
            {{ t('common.model') }}:
          </a-typography-text>
          <ModelProviderTag :modelProvider="provider" v-for="provider in llmModels" />
        </a-flex>
      </a-flex>
      <a-space>
        <WorkflowRunRecordsDrawer :workflowId="workflowId" @open-record="setWorkflowRecord" />
        <a-dropdown>
          <template #overlay>
            <a-menu>
              <a-menu-item key="edit" @click="openEditor">
                {{ t('workspace.workflowSpace.edit') }}
              </a-menu-item>
              <AgentInvokeDataEdit :workflow-data="savedWorkflow" type="menuItem"
                :key="`AgentInvokeDataEdit-${saveTime}`" />
              <a-divider style="margin: 8px 0;" />
              <a-menu-item key="delete" @click="deleteWorkflow">
                <a-typography-text type="danger">
                  {{ t('workspace.workflowSpace.delete') }}
                </a-typography-text>
              </a-menu-item>
            </a-menu>
          </template>
          <a-button>
            {{ t('workspace.workflowSpace.more_actions') }}
            <Down />
          </a-button>
        </a-dropdown>
      </a-space>
    </a-flex>
    <a-divider />
    <WorkflowUse ref="workflowUseRef" :workflow="currentWorkflow" :isTemplate="false" />
  </div>
</template>

<style scoped>
.space-container {
  height: 100%;
}

.main-use-container {
  padding-bottom: 60px;
}
</style>