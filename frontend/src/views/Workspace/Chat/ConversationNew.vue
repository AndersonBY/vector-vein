<script setup>
import { ref, reactive, onBeforeMount, onMounted, nextTick } from 'vue'
import { Send, Link } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from "vue-router"
import { storeToRefs } from 'pinia'
import { useUserChatsStore } from '@/stores/userChats'
import { useUserSettingsStore } from '@/stores/userSettings'
import WorkflowsPopoverShow from '@/components/workspace/chat/WorkflowsPopoverShow.vue'
import SettingsPopoverShow from '@/components/workspace/chat/SettingsPopoverShow.vue'
import ModelSelectButton from '@/components/workspace/chat/ModelSelectButton.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import AttachmentsList from '@/components/workspace/chat/AttachmentsList.vue'
import RecordingButton from '@/components/workspace/chat/RecordingButton.vue'
import AudioReplySettingButton from '@/components/workspace/chat/AudioReplySettingButton.vue'
import { navigateToElementBottom } from '@/utils/util'
import { defaultSettings } from '@/utils/common'
import logoUrl from "@/assets/logo.svg"
import { conversationAPI, agentAPI } from '@/api/chat'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const sending = ref(false)
const agentId = route.params.agentId
const agentData = ref({})

const userChatsStore = useUserChatsStore()
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)

const conversation = reactive({
  aid: agentId,
  cid: '',
  title: t('workspace.chatSpace.new_chat'),
  settings: defaultSettings[language.value],
  model: 'gpt-35-turbo',
  model_provider: 'OpenAI',
  update_time: new Date().getTime(),
})
const messages = ref([])
const userInput = ref('')
const attachments = ref([])
const selectedFlows = reactive({
  workflows: {},
  templates: {},
})

const chatBodyElement = ref(null)

onBeforeMount(async () => {
  const response = await agentAPI('get', { aid: agentId })
  if (response.status == 200) {
    agentData.value = response.data
    conversation.settings = agentData.value.settings
    conversation.model = agentData.value.model
    conversation.model_provider = agentData.value.model_provider
    selectedFlows.workflows = agentData.value.related_workflows
    selectedFlows.templates = agentData.value.related_templates
  } else {
    message.error(response.msg)
  }
  loading.value = false
  nextTick(() => {
    navigateToElementBottom(chatBodyElement.value)
  })
})

onMounted(() => {
  // Expose for Python usage.
  window.setAttachments = (files) => {
    attachments.value = files
  }
})

const conversationId = ref('tmp')
const sendMessage = async () => {
  if (!userInput.value) {
    return
  }
  sending.value = true
  conversation.update_time = new Date().getTime()
  const res = await conversationAPI('create', { conversation })
  conversation.cid = res.data.cid
  if (res.status != 200) {
    message.error(t('workspace.chatSpace.send_message_failed'))
    return
  }
  userChatsStore.addConversation(conversation)
  userChatsStore.addUnsentChat({
    content_type: 'TXT',
    content: userInput.value,
    attachments: attachments.value,
  })

  await router.push({ name: 'conversationDetail', params: { conversationId: res.data.cid } })

  userInput.value = ''
}

const selectSuggestions = (suggestion) => {
  userInput.value = suggestion
  sendMessage()
}

const isDragging = ref(false)
const handleDragEnter = (event) => {
  event.preventDefault()
  isDragging.value = true
}

const handleDragOver = (event) => {
  event.preventDefault()
  isDragging.value = true
}

const handleDragLeave = (event) => {
  event.preventDefault()
  isDragging.value = false
}

const handleDrop = (event) => {
  event.preventDefault()
  isDragging.value = false
  const items = event.dataTransfer.items
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.kind === 'file') {
      const { name } = item.getAsFile()
      window.pywebview.api.get_drop_file_path(name).then(dropFilePath => {
        attachments.value.push(dropFilePath)
        message.success(t('components.workspace.uploaderFieldUse.upload_success', { file: name }))
      })
    }
  }
}
</script>

<template>
  <div class="main-container" @dragenter="handleDragEnter" @drop="handleDrop" @dragover="handleDragOver">
    <div v-show="isDragging" class="drag-overlay" @dragleave="handleDragLeave">
      {{ t('workspace.chatSpace.drop_to_upload') }}
    </div>
    <div class="chat-header">
      <a-typography-title :level="2" class="black-text" style="margin-bottom: 0;">
        {{ t('workspace.chatSpace.new_chat') }}
      </a-typography-title>
    </div>
    <a-spin v-if="loading" :spinning="loading" class="chat-body-loading" />
    <div v-else ref="chatBodyElement" class="chat-body custom-scrollbar">
      <div class="chat-body-logo-container" v-if="messages.length == 0">
        <a-avatar :src="agentData?.avatar ? `${agentData.avatar}` : logoUrl" :size="64">
        </a-avatar>
        <a-typography-title :level="2" class="black-text opening-dialog" style="text-align: center;">
          {{ agentData.settings?.opening_dialog?.text || t('workspace.chatSpace.how_can_i_help_you_today') }}
        </a-typography-title>
      </div>
      <a-flex justify="center">
        <div class="opening-questions" v-if="messages.length == 0">
          <div class="opening-question" v-for="question in agentData.settings?.opening_dialog?.questions || []"
            @click="selectSuggestions(question)">
            <a-typography-paragraph :ellipsis="{ rows: 2 }" :content="question" style="margin-bottom: 0;" />
            <Send />
          </div>
        </div>
      </a-flex>
    </div>
    <div class="chat-footer-input">
      <div class="chat-input-actions">
        <SettingsPopoverShow v-if="!loading" :key="conversationId" :settings="conversation.settings" />
        <WorkflowsPopoverShow v-if="!loading" :key="conversationId" :selectedFlows="selectedFlows" />
        <ModelSelectButton :key="conversationId" :cid="conversationId" v-model:model="conversation.model"
          v-model:modelProvider="conversation.model_provider" />
        <AudioReplySettingButton :key="conversationId" v-model:audioReply="conversation.settings.agent_audio_reply"
          v-model:audioVoice="conversation.settings.agent_audio_voice" />
      </div>
      <div class="chat-input-area">
        <a-textarea v-model:value="userInput" :placeholder="t('workspace.chatSpace.textarea_tip')"
          :auto-size="{ minRows: 2, maxRows: 10 }" style="padding-right: 7rem;" @keyup.ctrl.enter="sendMessage" />
        <RecordingButton class="chat-recording-btn" :transcribe="true" v-model:text="userInput"
          @finished="sendMessage" />
        <a-tooltip :title="t('workspace.chatSpace.upload_attachments')">
          <UploaderFieldUse class="chat-attachment-btn" v-model="attachments" supportFileTypes="*.*" :acceptPaste="true"
            :multiple="true" :showUploadList="false" :singleButton="true"
            :singleButtonProps="{ type: 'text', loading: sending }">
            <template #icon>
              <Link />
            </template>
          </UploaderFieldUse>
        </a-tooltip>
        <a-tooltip :title="t('workspace.chatSpace.send_message')">
          <a-button type="primary" class="chat-send-btn" :loading="sending" :disabled="userInput.length == 0"
            @click="sendMessage">
            <template #icon>
              <Send />
            </template>
          </a-button>
        </a-tooltip>
      </div>
      <AttachmentsList v-model="attachments" />
    </div>
  </div>
</template>

<style scoped>
.main-container {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-container .drag-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.473);
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 24px;
  color: #fff;
  z-index: 100;
}

.main-container .chat-header {
  padding: 14px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, .1);
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
}

.main-container .chat-body .chat-body-logo-container {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.main-container .chat-body .chat-body-logo-container .chat-body-logo {
  width: 72px;
  height: 72px;
  border-radius: 9999px;
  box-shadow: 0 0 transparent, 0 0 transparent, inset 0 0 0 1px rgba(0, 0, 0, .1);
  display: flex;
  justify-content: center;
  align-items: center;
}

.main-container .chat-body .chat-body-logo-container .chat-body-logo img {
  width: 60%;
  height: 60%;
}

.main-container .chat-body .chat-body-logo-container .opening-dialog {
  max-width: 600px;
}

.opening-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-start;
  max-width: 768px;
}

.opening-question {
  background-color: #fff;
  border-radius: 10px;
  border: 1px solid #33333322;
  padding: 20px;
  margin-bottom: 10px;
  flex-basis: calc(50% - 10px);
  box-sizing: border-box;
  height: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 4px;
}

.opening-question:only-child {
  flex-basis: 100%;
}

.opening-question:hover {
  background-color: rgb(247, 247, 248);
}

/* 动画效果 */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.main-container .chat-body {
  flex: 1 1;
  overflow: auto;
  overflow-x: hidden;
  padding: 20px 20px 40px;
  position: relative;
  overscroll-behavior: none;
  background-color: #fff;
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.main-container .chat-body-loading {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #fff;
}

.main-container .chat-footer-input {
  position: relative;
  width: 100%;
  padding: 10px 20px 20px;
  box-sizing: border-box;
  border-top: 1px solid rgba(0, 0, 0, .1);
  display: flex;
  flex-direction: column;
  gap: 10px;
  background-color: #fff;
  border-bottom-right-radius: 20px;
}

.main-container .chat-footer-input .chat-input-area {
  position: relative;
}

.main-container .chat-footer-input .chat-input-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 5px;
}

.main-container .chat-send-btn {
  position: absolute;
  right: 0.75rem;
  bottom: 0.75rem;
}

.main-container .chat-attachment-btn {
  position: absolute;
  right: 3.25rem;
  bottom: 0.75rem;
}

.main-container .chat-recording-btn {
  position: absolute;
  right: 5.25rem;
  bottom: 0.75rem;
}
</style>