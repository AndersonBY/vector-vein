<script setup>
import { ref, reactive, onBeforeMount, onBeforeUnmount, computed, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router"
import { message } from 'ant-design-vue'
import { EditTwo, CloseOne, Share } from '@/icons'
import ModelCapabilities from '@/components/ModelCapabilities.vue'
import ModelPicker from '@/components/ModelPicker.vue'
import AvatarUpload from '@/components/workspace/AvatarUpload.vue'
import QuestionPopover from '@/components/QuestionPopover.vue'
import CopyButton from "@/components/CopyButton.vue"
import WorkflowSelect from '@/components/workspace/agent/WorkflowSelect.vue'
import DynamicLinesInput from "@/components/DynamicLinesInput.vue"
import SimpleFormItem from "@/components/SimpleFormItem.vue"
import TextOutput from "@/components/TextOutput.vue"
import logoUrl from "@/assets/logo.svg"
import { hashObject, formatTime, deepCopy } from "@/utils/util"
import { getChatModelOptions, websiteBase, agentVoiceOptions } from '@/utils/common'
import { hasModelOption } from '@/utils/modelSelection'
import { agentAPI } from '@/api/chat'
import { workflowAPI } from "@/api/workflow"
import { officialSiteAPI } from '@/api/remote'

const { t } = useI18n()
const loading = ref(true)
const loadFailed = ref(false)
const saving = ref(false)
let generation = 0
const route = useRoute()
const router = useRouter()
const agentId = ref(route.params.agentId)
const fromSource = ref(route.query.from)
const agentData = ref({})
const savedAgentData = ref({})
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
const chatModelOptions = computed(() => getChatModelOptions())
const providerOptions = computed(() => chatModelOptions.value.map(item => ({
  value: item.value, label: item.labelText || (typeof item.label === 'string' ? item.label : item.value),
})))
const modelOptions = computed(() => chatModelOptions.value.find(item => item.value === agentData.value.model_provider)?.children || [])
const validModelSelection = computed(() => hasModelOption(providerOptions.value, agentData.value.model_provider) && hasModelOption(modelOptions.value, agentData.value.model))

const flowsFromAgent = agent => ({
  workflows: Object.fromEntries((agent.related_workflows || []).map(workflow => [workflow.wid, workflow])),
  templates: Object.fromEntries((agent.related_templates || []).map(template => [template.tid, template])),
})

const loadAgentData = async (aid) => {
  const version = ++generation
  loading.value = true
  loadFailed.value = false
  saving.value = false
  modifyAgentModal.modifyLoading = false
  modifyAgentModal.open = false
  agentId.value = aid
  try {
    const response = fromSource.value === 'public'
      ? await officialSiteAPI('get_agent', { aid })
      : await agentAPI('get', { aid })
    if (version !== generation) return
    if (response.status !== 200 || !response.data?.aid) throw new Error('Agent load failed')
    agentData.value = response.data
    savedAgentData.value = deepCopy(agentData.value)
    selectedFlows.value = flowsFromAgent(response.data)
    savedSelectedFlows.value = deepCopy(selectedFlows.value)
  } catch {
    if (version === generation) loadFailed.value = true
  } finally {
    if (version === generation) loading.value = false
  }
}

onBeforeMount(async () => {
  await loadAgentData(route.params.agentId)
})
watch(() => [route.params.agentId, route.query.from], () => {
  fromSource.value = route.query.from
  loadAgentData(route.params.agentId)
})
onBeforeUnmount(() => { generation++ })

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
      next(false)
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
    if (!agentData.value.is_owner || saving.value || modifyAgentModal.modifyLoading || loading.value || loadFailed.value) return
    const version = generation
    modifyAgentModal.modifyLoading = true
    try {
      try {
        await modifyFormRef.value.validate()
      } catch {
        return
      }
      if (version !== generation) return
      const submitted = deepCopy(modifyAgentModal.form)
      const response = await agentAPI('update', {
        aid: agentId.value,
        ...submitted,
      })
      if (version !== generation) return
      if (response.status !== 200 || !response.data?.aid) throw new Error('Agent save failed')
      for (const key of ['avatar', 'name', 'description', 'version', 'update_time']) {
        agentData.value[key] = response.data[key]
        savedAgentData.value[key] = response.data[key]
      }
      message.success(t('common.save_success'))
      if (JSON.stringify(modifyAgentModal.form) === JSON.stringify(submitted)) modifyAgentModal.open = false
    } catch {
      if (version === generation) message.error(t('workspace.agentSpace.save_failed'))
    } finally {
      if (version === generation) modifyAgentModal.modifyLoading = false
    }
  },
})
const openModifyAgent = () => {
  if (!agentData.value.is_owner || saving.value || modifyAgentModal.modifyLoading) return
  modifyAgentModal.form = {
    avatar: agentData.value.avatar, name: agentData.value.name, description: agentData.value.description,
  }
  modifyAgentModal.open = true
}

const save = async () => {
  if (!agentData.value.is_owner || saving.value || modifyAgentModal.modifyLoading || loading.value || loadFailed.value) return
  if (!validModelSelection.value) {
    message.error(t('workspace.agentSpace.invalid_model_selection'))
    return
  }
  const version = generation
  const submitted = deepCopy(agentData.value)
  const submittedFlows = deepCopy(selectedFlows.value)
  saving.value = true
  const workflowIds = Object.keys(submittedFlows.workflows)
  try {
    const response = await agentAPI('update', {
      ...submitted,
      aid: agentId.value,
      related_workflows: workflowIds,
      related_templates: Object.keys(submittedFlows.templates),
    })
    if (version !== generation) return
    if (response.status !== 200 || !response.data?.aid) throw new Error('Agent save failed')
    savedAgentData.value = deepCopy(response.data)
    savedSelectedFlows.value = deepCopy(flowsFromAgent(response.data))
    if (JSON.stringify(agentData.value) === JSON.stringify(submitted) && JSON.stringify(selectedFlows.value) === JSON.stringify(submittedFlows)) {
      agentData.value = deepCopy(savedAgentData.value)
      selectedFlows.value = deepCopy(savedSelectedFlows.value)
    }
    let successMessageContent = t('common.save_success')
    if ((response.data.shared || response.data.is_public) && workflowIds.length > 0) {
      successMessageContent += ' ' + t('workspace.agentSpace.workflows_converted_to_templates')
    }

    message.success(successMessageContent)
  } catch {
    if (version === generation) message.error(t('workspace.agentSpace.save_failed'))
  } finally {
    if (version === generation) saving.value = false
  }
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
    duplicateModalOpen.value = false
    fromSource.value = 'private'
    await loadAgentData(createResponse.data.aid)
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
  if (saving.value || modifyAgentModal.modifyLoading) return
  router.push({ name: 'conversationNew', params: { agentId: agentId.value } })
}
</script>

<template>
  <div class="main-container" style="justify-content: center;" v-if="loading">
    <a-spin />
  </div>
  <div class="main-container" v-else-if="!loadFailed">
    <div class="header">
      <a-flex gap="small">
        <img :src="agentData?.avatar ? `${agentData.avatar}` : logoUrl" alt="avatar" class="avatar" />
        <a-flex vertical justify-content="space-between" gap="small">
          <a-space align="end">
            <a-typography-title style="margin-bottom: 0;" :level="2">
              {{ agentData.name }}
            </a-typography-title>
            <a-tooltip :title="t('workspace.agentSpace.modify_agent')">
              <a-button type="text" @click="openModifyAgent" :disabled="saving || modifyAgentModal.modifyLoading" v-if="agentData.is_owner">
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
              :confirm-loading="modifyAgentModal.modifyLoading" v-model:open="modifyAgentModal.open"
              :cancel-button-props="{ disabled: modifyAgentModal.modifyLoading }"
              :closable="!modifyAgentModal.modifyLoading" :mask-closable="!modifyAgentModal.modifyLoading" :keyboard="!modifyAgentModal.modifyLoading">
              <a-flex justify="center" style="margin: 24px 0;">
                <AvatarUpload v-model="modifyAgentModal.form.avatar" />
              </a-flex>
              <a-form ref="modifyFormRef" :model="modifyAgentModal.form" layout="vertical">
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
        <a-button v-if="fromSource != 'public'" @click="navigateToChat" :disabled="saving || modifyAgentModal.modifyLoading">
          {{ t('workspace.agentSpace.chat_with_agent') }}
        </a-button>
        <a-button v-if="agentData.is_owner" type="primary" @click="save" :loading="saving"
          :disabled="!validModelSelection || modifyAgentModal.modifyLoading">
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
            <div class="model-selection-header">
              <a-typography-title :level="4" class="model-selection-title">
                {{ t('workspace.agentSpace.model_select') }}
                <QuestionPopover :content="[t('workspace.agentSpace.model_select_tip')]" />
              </a-typography-title>
              <ModelPicker class="model-selection-picker" v-model:model="agentData.model" v-model:model-provider="agentData.model_provider"
                v-model:preference="agentData.settings.model_preference" v-model:reasoning-effort="agentData.settings.reasoning_effort"
                :options="chatModelOptions" :disabled="!agentData.is_owner" />
            </div>
            <ModelCapabilities :provider="agentData.model_provider" :model="agentData.model" />
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
  <a-result v-else status="error" :title="t('workspace.agentSpace.load_failed')">
    <template #extra>
      <a-button @click="loadAgentData(agentId)">{{ t('workspace.agentSpace.retry') }}</a-button>
    </template>
  </a-result>
</template>

<style scoped>
.model-selection-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; }
.model-selection-title { margin: 0; flex-shrink: 0; }
.model-selection-picker { min-width: 0; max-width: 60%; }

.main-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
