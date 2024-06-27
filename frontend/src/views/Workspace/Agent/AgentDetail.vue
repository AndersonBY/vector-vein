<script setup>
import { ref, reactive, onBeforeMount, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router"
import { message } from 'ant-design-vue'
import { EditTwo, CloseOne, Share } from '@icon-park/vue-next'
import AvatarUpload from '@/components/workspace/AvatarUpload.vue'
import QuestionPopover from '@/components/QuestionPopover.vue'
import CopyButton from "@/components/CopyButton.vue"
import WorkflowSelect from '@/components/workspace/agent/WorkflowSelect.vue'
import DynamicLinesInput from "@/components/DynamicLinesInput.vue"
import SimpleFormItem from "@/components/SimpleFormItem.vue"
import TextOutput from "@/components/TextOutput.vue"
import logoUrl from "@/assets/logo.svg"
import { hashObject, formatTime, deepCopy } from "@/utils/util"
import { chatModelOptions, websiteBase, agentVoiceOptions } from '@/utils/common'
import { agentAPI } from '@/api/chat'
import { workflowAPI } from "@/api/workflow"
import { officialSiteAPI } from '@/api/remote'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const agentId = ref(route.params.agentId)
const fromSource = ref(route.query.from)
const agentData = ref({})
const savedAgentData = ref({})
const modelSelection = ref([])
const selectedFlows = ref({
  workflows: {},
  templates: {},
})
const savedSelectedFlows = ref({
  workflows: {},
  templates: {},
})
const updateTime = computed(() => {
  return formatTime(agentData.value.update_time)
})

onBeforeMount(async () => {
  agentId.value = route.params.agentId
  let response
  if (fromSource.value == 'public') {
    response = await officialSiteAPI('get_agent', { aid: agentId.value })
  } else {
    response = await agentAPI('get', { aid: agentId.value })
  }
  if (response.status == 200) {
    agentData.value = response.data
    modelSelection.value = [agentData.value.model_provider, agentData.value.model]
    modifyAgentModal.form.avatar = agentData.value.avatar
    modifyAgentModal.form.name = agentData.value.name
    modifyAgentModal.form.description = agentData.value.description
    savedAgentData.value = deepCopy(agentData.value)

    selectedFlows.value.workflows = response.data.related_workflows.reduce((obj, workflow) => {
      obj[workflow.wid] = workflow
      return obj
    }, {})
    selectedFlows.value.templates = response.data.related_templates.reduce((obj, template) => {
      obj[template.tid] = template
      return obj
    }, {})
    savedSelectedFlows.value = deepCopy(selectedFlows.value)
  } else {
    message.error(response.msg)
  }
  loading.value = false
})

onBeforeRouteLeave((to, from, next) => {
  if (!agentData.value.is_owner) {
    next()
    return
  }
  if (hashObject(agentData.value) != hashObject(savedAgentData.value) || hashObject(selectedFlows.value) != hashObject(savedSelectedFlows.value)) {
    const result = window.confirm(t('common.confirm_leave'))
    if (result) {
      next()
    } else {
      return
    }
  } else {
    next()
  }
})

const modifyFormRef = ref()
const modifyAgentModal = reactive({
  open: false,
  modifyLoading: false,
  form: {
    avatar: '',
    name: '',
    description: '',
  },
  ok: async () => {
    modifyAgentModal.modifyLoading = true
    try {
      modifyFormRef.value.validate()
      const response = await agentAPI('update', {
        aid: agentId.value,
        avatar: modifyAgentModal.form.avatar,
        name: modifyAgentModal.form.name,
        description: modifyAgentModal.form.description,
      })
      modifyAgentModal.modifyLoading = false
      if (response.status == 200) {
        agentData.value = response.data
        savedAgentData.value = deepCopy(agentData.value)
        message.success(t('common.save_success'))
        modifyAgentModal.open = false
      } else {
        message.error(response.msg)
      }
    } catch (error) {
      console.error(error)
      return
    }
    modifyAgentModal.open = false
  },
})

const saving = ref(false)
const save = async () => {
  saving.value = true
  const workflowIds = Object.keys(selectedFlows.value.workflows)
  const templateIds = Object.keys(selectedFlows.value.templates)
  const response = await agentAPI('update', {
    aid: agentId.value,
    ...agentData.value,
    related_workflows: workflowIds,
    related_templates: templateIds,
  })
  if (response.status == 200) {
    agentData.value = response.data
    savedAgentData.value = deepCopy(agentData.value)

    selectedFlows.value.workflows = response.data.related_workflows.reduce((obj, workflow) => {
      obj[workflow.wid] = workflow
      return obj
    }, {})
    selectedFlows.value.templates = response.data.related_templates.reduce((obj, template) => {
      obj[template.tid] = template
      return obj
    }, {})
    savedSelectedFlows.value = deepCopy(selectedFlows.value)

    let successMessageContent = t('common.save_success')
    if ((agentData.value.shared || agentData.value.is_public) && workflowIds.length > 0) {
      successMessageContent += ' ' + t('workspace.agentSpace.workflows_converted_to_templates')
    }

    message.success(successMessageContent)
  } else {
    message.error(response.msg)
  }
  saving.value = false
}

const duplicating = ref(false)
const duplicateModalOpen = ref(false)
const addTemplatesWhenDuplicate = ref(true)
const duplicate = async () => {
  duplicating.value = true
  const response = await officialSiteAPI('duplicate_agent', { aid: agentId.value, add_templates: addTemplatesWhenDuplicate.value })
  if (response.status == 200) {
    let workflows = []
    if (addTemplatesWhenDuplicate.value) {
      for (const workflow of response.data.related_templates) {
        const workflowCreateResp = await workflowAPI('create', workflow)
        workflows.push(workflowCreateResp.data.wid)
      }
    }
    const payload = {
      ...response.data,
      related_workflows: workflows,
    }
    const createResponse = await agentAPI('create', payload)
    message.success(t('workspace.agentSpace.duplicate_agent_success'))
    await router.push({ name: 'agentDetail', params: { agentId: createResponse.data.aid } })
    window.location.reload()
  } else {
    message.error(response.msg)
  }
  duplicating.value = false
}

const openWorkflowPage = (wid) => {
  router.push({ name: 'WorkflowUse', params: { workflowId: wid } })
}
const removeWorkflow = (workflow) => {
  delete selectedFlows.value.workflows[workflow.wid]
}

const openTemplatePage = (tid) => {
  router.push({ name: 'WorkflowTemplate', params: { workflowTemplateId: tid } })
}
const removeTemplate = (template) => {
  delete selectedFlows.value.templates[template.tid]
}

const navigateToChat = () => {
  router.push({ name: 'conversationNew', params: { agentId: agentId.value } })
}

const modelChanged = async () => {
  agentData.value.model = modelSelection.value[1]
  agentData.value.model_provider = modelSelection.value[0]
}
</script>

<template>
  <div class="main-container" style="justify-content: center;" v-if="loading">
    <a-spin />
  </div>
  <div class="main-container" v-else>
    <div class="header">
      <a-flex gap="small">
        <img :src="agentData?.avatar ? `${agentData.avatar}` : logoUrl" alt="avatar" class="avatar" />
        <a-flex vertical justify-content="space-between" gap="small">
          <a-space align="end">
            <a-typography-title class="black-text" style="margin-bottom: 0;" :level="2">
              {{ agentData.name }}
            </a-typography-title>
            <a-tooltip :title="t('workspace.agentSpace.modify_agent')">
              <a-button type="text" @click="modifyAgentModal.open = true" v-if="agentData.is_owner">
                <template #icon>
                  <EditTwo />
                </template>
              </a-button>
            </a-tooltip>
            <CopyButton type="text" :copyText="`${websiteBase}/workspace/agent/${agentData.aid}`"
              :tipText="t('workspace.agentSpace.copy_agent_share_link')" v-if="agentData.shared">
              <template #icon>
                <Share />
              </template>
            </CopyButton>
            <a-modal :title="t('workspace.agentSpace.modify_agent')" @ok="modifyAgentModal.ok"
              :confirm-loading="modifyAgentModal.createLoading" v-model:open="modifyAgentModal.open">
              <a-flex justify="center" style="margin: 24px 0;">
                <AvatarUpload v-model="modifyAgentModal.form.avatar" />
              </a-flex>
              <a-form ref="modifyFormRef" :model="agentData" layout="vertical">
                <a-form-item :label="t('workspace.agentSpace.agent_name')" name="name"
                  :rules="[{ required: true, message: t('workspace.agentSpace.agent_name_required') }]">
                  <a-input v-model:value="modifyAgentModal.form.name"
                    :placeholder="t('workspace.agentSpace.agent_name_placeholder')" />
                </a-form-item>
                <a-form-item :label="t('workspace.agentSpace.agent_description')" name="description">
                  <a-textarea :autoSize="{ minRows: 3, maxRows: 10 }" v-model:value="modifyAgentModal.form.description"
                    :placeholder="t('workspace.agentSpace.agent_description_placeholder')" />
                </a-form-item>
              </a-form>
            </a-modal>
          </a-space>
          <a-flex gap="small" align="flex-end">
            <a-typography-text type="secondary">
              {{ t('common.update_time_format', { 'time': updateTime }) }}
            </a-typography-text>
          </a-flex>
        </a-flex>
      </a-flex>
      <a-space>
        <a-button v-if="fromSource != 'public'" @click="navigateToChat">
          {{ t('workspace.agentSpace.chat_with_agent') }}
        </a-button>
        <a-button v-if="agentData.is_owner" type="primary" @click="save" :loading="saving">
          {{ t('common.save') }}
        </a-button>
        <a-tooltip v-else :title="t('workspace.agentSpace.duplicate_as_mine')">
          <a-button type="primary" @click="duplicateModalOpen = true">
            {{ t('common.duplicate') }}
          </a-button>
        </a-tooltip>
        <a-modal :title="t('workspace.agentSpace.duplicate_as_mine')" @ok="duplicate" :confirm-loading="duplicating"
          v-model:open="duplicateModalOpen">
          <SimpleFormItem :title="t('workspace.agentSpace.add_templates')"
            :description="t('workspace.agentSpace.add_templates_to_your_workflows')" type="checkbox"
            v-model="addTemplatesWhenDuplicate" />
        </a-modal>
      </a-space>
    </div>
    <div class="body">
      <a-row :gutter="[16, 16]" justify="center">
        <a-col :xs="24" :md="agentData.is_owner ? 8 : 16">
          <div class="system-prompt">
            <a-typography-title :level="4">
              {{ t('workspace.agentSpace.model_select') }}
              <QuestionPopover :content="[t('workspace.agentSpace.model_select_tip')]" />
            </a-typography-title>
            <a-cascader style="width: 100%;" :disabled="!agentData.is_owner" v-model:value="modelSelection"
              :options="chatModelOptions" @change="modelChanged" />
          </div>
          <a-divider />
          <div class="system-prompt">
            <a-typography-title :level="4">
              {{ t('workspace.agentSpace.system_prompt') }}
              <QuestionPopover :content="[t('workspace.agentSpace.system_prompt_tip')]" />
            </a-typography-title>
            <a-textarea v-model:value="agentData.settings.system_prompt" :auto-size="{ minRows: 10, maxRows: 20 }"
              v-if="agentData.is_owner" />
            <TextOutput v-else :text="agentData.settings.system_prompt" renderMarkdown />
          </div>
          <a-divider />
          <div class="opening-dialog">
            <a-typography-title :level="4">
              {{ t('workspace.agentSpace.opening_dialog') }}
            </a-typography-title>
            <a-textarea v-model:value="agentData.settings.opening_dialog.text" :auto-size="{ minRows: 2, maxRows: 5 }"
              v-if="agentData.is_owner" />
            <a-typography-paragraph :content="agentData.settings.opening_dialog.text" v-else />
            <a-typography-title :level="4" style="margin-top: 10px;">
              {{ t('workspace.agentSpace.opening_question_suggestions') }}
              <QuestionPopover :content="[t('workspace.agentSpace.opening_question_suggestions_tip')]" />
            </a-typography-title>
            <DynamicLinesInput v-model="agentData.settings.opening_dialog.questions" v-if="agentData.is_owner" />
            <template v-else>
              <a-typography-paragraph :content="question"
                v-for="question in agentData.settings.opening_dialog.questions" />
            </template>
          </div>
          <a-divider />
          <SimpleFormItem type="checkbox" :title="t('workspace.chatSpace.auto_run_workflow')"
            :description="t('workspace.chatSpace.auto_run_workflow_description')"
            v-model="agentData.settings.auto_run_workflow" :disabled="!agentData.is_owner" />
          <a-divider />
          <SimpleFormItem type="checkbox" :title="t('workspace.chatSpace.native_multimodal')"
            :description="t('workspace.chatSpace.native_multimodal_description')"
            v-model="agentData.settings.native_multimodal" :disabled="!agentData.is_owner" />
          <a-divider />
          <SimpleFormItem type="checkbox" :title="t('workspace.chatSpace.agent_audio_reply')"
            :description="t('workspace.chatSpace.agent_audio_reply_description')"
            v-model="agentData.settings.agent_audio_reply" :disabled="!agentData.is_owner" />
          <a-divider />
          <SimpleFormItem v-show="agentData.settings.agent_audio_reply" type="cascader" layout="vertical"
            :title="t('workspace.chatSpace.agent_audio_voice')" v-model="agentData.settings.agent_audio_voice"
            :options="agentVoiceOptions" :disabled="!agentData.is_owner" />
          <a-divider />
        </a-col>
        <a-col :xs="24" :md="16" v-if="agentData.is_owner">
          <div>
            <a-typography-title :level="4">
              {{ t('workspace.chatSpace.selected_workflows') }}
            </a-typography-title>
            <a-typography-paragraph type="secondary">
              {{ t('common.workflow') }}
            </a-typography-paragraph>
            <a-button type="text" block v-for="workflow in selectedFlows.workflows"
              @click="openWorkflowPage(workflow.wid)">
              <a-flex justify="space-between">
                <a-space>
                  <a-typography-text :ellipsis="true" :content="workflow.title" />
                  <Share />
                </a-space>
                <a-tooltip :title="t('workspace.agentSpace.remove_workflow')" v-if="agentData.is_owner">
                  <a-button type="text" size="small" @click.stop="removeWorkflow(workflow)">
                    <template #icon>
                      <CloseOne />
                    </template>
                  </a-button>
                </a-tooltip>
              </a-flex>
            </a-button>

            <a-typography-paragraph type="secondary" style="margin-top: 10px;">
              {{ t('common.workflow_template') }}
            </a-typography-paragraph>
            <a-button type="text" block v-for="template in selectedFlows.templates "
              @click="openTemplatePage(template.tid)">
              <a-flex justify="space-between">
                <a-space>
                  <a-typography-text :ellipsis="true" :content="template.title" />
                  <Share />
                </a-space>
                <a-tooltip :title="t('workspace.agentSpace.remove_workflow')" v-if="agentData.is_owner">
                  <a-button type="text" size="small" @click.stop="removeTemplate(template)">
                    <template #icon>
                      <CloseOne />
                    </template>
                  </a-button>
                </a-tooltip>
              </a-flex>
            </a-button>
          </div>
          <a-divider />
          <a-typography-title :level="4">
            {{ t('workspace.agentSpace.workflow_selection') }}
          </a-typography-title>
          <WorkflowSelect v-model="selectedFlows" />
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<style scoped>
.main-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 64px);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 24px;
  border-bottom: 1px solid #ebedf0;
}

/* 小尺寸时 .header变为纵向 */
@media screen and (max-width: 767px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
  }
}

.avatar {
  width: 70px;
  height: 70px;
  border-radius: 8px;
  margin-right: 10px;
  object-fit: cover;
}

.body {
  padding: 24px;
  height: 100%;
}

.share-public-button.button-status-false {
  background-color: #2db7f5;
  color: #fff;
}

.share-public-button.button-status-false:hover {
  background-color: #88d9ff;
  color: #fff;
}

.share-public-button.button-status-true {
  background-color: #87d068;
  color: #fff;
}

.share-public-button.button-status-true:hover {
  background-color: #a5ce93;
  color: #fff;
}
</style>

<style>
.system-prompt .markdown-body {
  background: rgba(196, 196, 196, 0.25);
  padding: 16px;
  border-radius: 8px;
}
</style>