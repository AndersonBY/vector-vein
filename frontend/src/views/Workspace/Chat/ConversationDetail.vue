<script setup>
import { ref, reactive, onBeforeMount, onBeforeUnmount, onMounted, nextTick, watch } from 'vue'
import { Send, Edit, Link, Plus } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { storeToRefs } from 'pinia'
import { useUserChatsStore } from '@/stores/userChats'
import ReconnectingWebSocket from 'reconnecting-websocket'
import ChatMessage from '@/components/workspace/chat/ChatMessage.vue'
import ScrollEndButton from '@/components/ScrollEndButton.vue'
import ShareChat from '@/components/workspace/chat/ShareChat.vue'
import WorkflowsPopoverShow from '@/components/workspace/chat/WorkflowsPopoverShow.vue'
import SettingsPopoverShow from '@/components/workspace/chat/SettingsPopoverShow.vue'
import ModelSelectButton from '@/components/workspace/chat/ModelSelectButton.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import AttachmentsList from '@/components/workspace/chat/AttachmentsList.vue'
import RecordingButton from '@/components/workspace/chat/RecordingButton.vue'
import AudioReplySettingButton from '@/components/workspace/chat/AudioReplySettingButton.vue'
import { navigateToElementBottom } from '@/utils/util'
import { settingAPI } from '@/api/user'
import { conversationAPI, messageAPI } from '@/api/chat'

const { t } = useI18n()
const loading = ref(false)
const route = useRoute()
const router = useRouter()
const conversationId = ref(route.params.conversationId)
const agentId = ref(route.params.agentId)
const selectedWorkflows = reactive({
  workflows: {},
  templates: {},
})

const userChatsStore = useUserChatsStore()
const { unsentChats } = storeToRefs(userChatsStore)

const wsPort = ref(null)

const fetchConversation = async (cid) => {
  const res = await conversationAPI('get', { cid: cid })
  if (res.status != 200) {
    message.error(t('workspace.chatSpace.fetch_conversation_failed'))
    return
  }
  conversation.value = res.data.conversation
  userChatsStore.addConversation(conversation.value)
  messages.value = res.data.messages
  selectedWorkflows.workflows = {}
  selectedWorkflows.templates = {}
  conversation.value.related_workflows.forEach((workflow) => {
    selectedWorkflows.workflows[workflow.wid] = workflow
  })
  conversation.value.related_templates.forEach((workflow) => {
    selectedWorkflows.templates[workflow.tid] = workflow
  })

  loading.value = false
  nextTick(() => {
    navigateToElementBottom(chatBodyElementRef.value)
  })
}

watch(() => route.params.conversationId, async (newVal, oldVal) => {
  conversationId.value = newVal
  if (oldVal == newVal || newVal == undefined) {
    return
  }
  loading.value = true
  if (chatSocket !== null) {
    chatSocket.close()
    chatSocket = null
  }
  await fetchConversation(newVal)
})

const windowWidth = ref(window.innerWidth)
const updateWidth = () => {
  windowWidth.value = window.innerWidth
}

onBeforeMount(async () => {
  if (unsentChats.value.length == 0) {
    loading.value = true
  }
  await fetchConversation(conversationId.value)
  if (unsentChats.value.length > 0) {
    attachments.value = unsentChats.value[0].attachments
    await sendMessage(unsentChats.value[0].content, true)
    userChatsStore.clearUnsentChats()
  }
  nextTick(() => {
    if (chatBodyElementRef.value) {
      chatBodyElementRef.value.addEventListener('scroll', handleScroll)
    }
  })
})

onBeforeUnmount(() => {
  if (chatSocket !== null) {
    chatSocket.close()
    chatSocket = null
  }
  if (chatBodyElementRef.value) {
    chatBodyElementRef.value.removeEventListener('scroll', handleScroll)
  }

  window.removeEventListener('resize', updateWidth)
})

onMounted(() => {
  // Expose for Python usage.
  window.setAttachments = (files) => {
    attachments.value = files
  }

  window.addEventListener('resize', updateWidth)
})

const sending = ref(false)
const conversation = ref({ settings: { agent_audio_reply: false } })
const messages = ref([])
const userInput = ref('')
const attachments = ref([])

const userScrolled = ref(false)

const chatBodyElementRef = ref(null)

const websocketStatus = ref('connecting')
let chatSocket = null
const receiving = ref(false)

const aiMessage = reactive({
  loading: true,
  mid: 'tmp',
  status: 'P',
  author_type: 'A',
  content_type: 'TXT',
  create_time: new Date().getTime(),
  workflow_invoke_step: '',
  metadata: { selected_workflow: {}, record_id: '' },
  content: { text: '', reasoning_content: '', tool: {}, selected_workflow: {} },
})
const clearAiMessage = () => {
  aiMessage.loading = true
  aiMessage.mid = 'tmp'
  aiMessage.status = 'P'
  aiMessage.content_type = 'TXT'
  aiMessage.workflow_invoke_step = ''
  aiMessage.create_time = new Date().getTime()
  aiMessage.metadata = { selected_workflow: {}, record_id: '' }
  aiMessage.content = { text: '', reasoning_content: '', tool: {}, selected_workflow: {} }
}

const sendWebsocketMsg = async (msg) => {
  if (chatSocket === null) {
    if (wsPort.value === null) {
      const res = await settingAPI('get_port', { port_name: 'chat_ws_port' })
      wsPort.value = res.data.port
    }
    chatSocket = new ReconnectingWebSocket(
      `ws://localhost:${wsPort.value}/ws/chat/${conversationId.value}/`,
      null,
      { maxReconnectAttempts: 5 }
    )
  } else {
    chatSocket.send(JSON.stringify(msg))
  }
  chatSocket.onmessage = async (e) => {
    const data = JSON.parse(e.data)
    if (!data.end) {
      receiving.value = true
      aiMessage.loading = false
      aiMessage.status = 'G'
      if (data.workflow_invoke_step === 'generating_params') {
        aiMessage.workflow_invoke_step = 'generating_params'
        aiMessage.content_type = 'WKF'
        aiMessage.content.text += data.content ?? ''
        if (!userScrolled.value) {
          nextTick(() => {
            navigateToElementBottom(chatBodyElementRef.value)
          })
        }
      } else if (data.workflow_invoke_step === 'wait_for_invoke') {
        aiMessage.workflow_invoke_step = 'wait_for_invoke'
        aiMessage.content_type = 'WKF'
        aiMessage.content.text += data.content ?? ''
        aiMessage.metadata.selected_workflow = data.selected_workflow
        if (!userScrolled.value) {
          nextTick(() => {
            navigateToElementBottom(chatBodyElementRef.value)
          })
        }
      } else if (data.tool_calls?.length > 0) {
        aiMessage.content_type = 'WKF'
        aiMessage.content.tool = data.tool_calls[0].function.name
        aiMessage.content.text += data.content ?? ''
      } else if (data.content === null && data.reasoning_content === null) {
        return
      } else {
        aiMessage.workflow_invoke_step = ''
        aiMessage.content_type = 'TXT'
        aiMessage.content.reasoning_content += data.reasoning_content ?? ''
        aiMessage.content.text += data.content ?? ''
      }
    } else {
      // 收到 end 字段，表示这一轮对话结束
      receiving.value = false
      if (data.title !== null) {
        conversation.value.title = data.title
        userChatsStore.updateConversation(conversationId.value, 'title', data.title)
      }
      await messageAPI('done_notice', { mid: aiMessage.mid })
      aiMessage.content.text = data.content ?? ''
      aiMessage.content.reasoning_content = data.reasoning_content ?? ''
      aiMessage.status = aiMessage.content_type == 'WKF' ? 'W' : 'S'
      if (aiMessage.content_type == 'WKF') {
        aiMessage.workflow_invoke_step = 'wait_for_invoke'
      }

      const lastGroup = messages.value[messages.value.length - 1]
      lastGroup[lastGroup.length - 1] = JSON.parse(JSON.stringify(aiMessage))
      clearAiMessage()
    }
    if (!userScrolled.value) {
      navigateToElementBottom(chatBodyElementRef.value)
    }
  }
  chatSocket.onopen = () => {
    websocketStatus.value = 'success'
    chatSocket.send(JSON.stringify(msg))
    console.log('chat websocket connected')
  }
  chatSocket.onerror = () => {
    websocketStatus.value = 'error'
    console.log('chat websocket error')
  }
}

const sendMessage = async (content, needTitle = false) => {
  if (!content) {
    return
  }
  let parentMid = null
  if (messages.value.length > 0) {
    const lastValidMessage = messages.value.findLast(message => message[0].mid !== 'tmp')
    if (lastValidMessage) {
      parentMid = lastValidMessage[0].mid
    }
  }
  const userMessage = {
    loading: false,
    mid: 'tmp',
    status: 'S',
    author_type: 'U',
    content_type: 'TXT',
    create_time: new Date().getTime(),
    metadata: {},
    content: { text: content },
    attachments: attachments.value,
  }
  messages.value.push([userMessage])
  if (!userScrolled.value) {
    nextTick(() => {
      navigateToElementBottom(chatBodyElementRef.value)
    })
  }
  const res = await messageAPI('send', {
    need_title: needTitle,
    parent_mid: parentMid,
    cid: conversationId.value,
    content: content,
    content_type: 'TXT',
    attachments: attachments.value,
  })
  if (res.status != 200) {
    message.error({ description: t('workspace.chatSpace.send_message_failed') })
    return
  }
  const userMessageMid = res.data.user_message_mid
  userMessage.mid = userMessageMid
  attachments.value = []

  aiMessage.loading = true
  aiMessage.mid = res.data.ai_message_mid
  aiMessage.create_time = new Date().getTime()

  messages.value.push([aiMessage])
  nextTick(() => {
    navigateToElementBottom(chatBodyElementRef.value)
  })

  sendWebsocketMsg({ ...res.data, user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })
  userInput.value = ''
}

const onAppendAnswer = async (mid) => {
  const res = await messageAPI('append_answer', {
    cid: conversationId.value,
    mid: mid,
  })
  if (res.status != 200) {
    return
  }
  aiMessage.mid = res.data.ai_message_mid
  aiMessage.create_time = new Date().getTime()

  messages.value.push([aiMessage])
  if (!userScrolled.value) {
    nextTick(() => {
      navigateToElementBottom(chatBodyElementRef.value)
    })
  }

  sendWebsocketMsg({ ...res.data, user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })
}

const editable = reactive({
  onEnd: async () => {
    const response = await conversationAPI('update', {
      'cid': conversationId.value,
      'title': conversation.value.title,
    })
    if (response.status == 200) {
      message.success(t('common.save_success'))
      userChatsStore.updateConversation(conversationId.value, 'title', conversation.value.title)
    } else {
      message.error(response.msg)
    }
  },
})

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

const handleScroll = () => {
  const element = chatBodyElementRef.value
  if (element) {
    const { scrollTop, scrollHeight, clientHeight } = element
    // 如果用户向上滚动超过100px,我们认为用户正在查看历史消息
    userScrolled.value = scrollHeight - scrollTop - clientHeight > 100
  }
}

const messagePagination = reactive(new Map())

const regenerate = async (mid, groupIndex) => {
  const res = await messageAPI('regenerate', { mid: mid, cid: conversationId.value })
  if (res.status !== 200) {
    message.error(t('workspace.chatSpace.regenerate_failed'))
    return
  }

  aiMessage.loading = true
  aiMessage.mid = res.data.ai_message_mid
  aiMessage.create_time = new Date().getTime()

  const parentGroup = messages.value[groupIndex]

  messages.value[groupIndex] = [...parentGroup, aiMessage]

  messagePagination.set(groupIndex, parentGroup.length)

  sendWebsocketMsg({ ...res.data, user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })
}

const switchMessagePage = (groupIndex, direction) => {
  const group = messages.value[groupIndex]
  const currentPage = messagePagination.get(groupIndex) ?? (group.length - 1) // 默认显示最后一项
  const newPage = direction === 'prev' ? currentPage - 1 : currentPage + 1
  messagePagination.set(groupIndex, newPage)
}

const deleteMessage = async (mid, groupIndex) => {
  const res = await messageAPI('delete', { mid: mid, cid: conversationId.value })
  if (res.status !== 200) {
    message.error(t('workspace.chatSpace.delete_message_failed'))
    return
  }

  // 获取指定组
  const group = messages.value[groupIndex]
  // 从组内删除指定消息
  const messageIndex = group.findIndex(msg => msg.mid === mid)
  if (messageIndex !== -1) {
    group.splice(messageIndex, 1)
    // 如果组变空了，删除整个组
    if (group.length === 0) {
      messages.value.splice(groupIndex, 1)
    }
  }

  // 重置相关的分页状态
  messagePagination.clear()

  message.success(t('workspace.chatSpace.delete_message_success'))
}
</script>

<template>
  <div class="main-container" @dragenter="handleDragEnter" @drop="handleDrop" @dragover="handleDragOver">
    <div v-show="isDragging" class="drag-overlay" @dragleave="handleDragLeave">
      {{ t('workspace.chatSpace.drop_to_upload') }}
    </div>
    <div class="chat-header">
      <a-flex align="flex-end" gap="small" class="title">
        <a-typography-title :level="2" style="margin-bottom: 0;" :editable="editable"
          v-model:content="conversation.title">
          <template #editableIcon>
            <Edit class="title-edit-button" />
          </template>
        </a-typography-title>
      </a-flex>
      <ShareChat :key="conversation.cid" disabled :conversation="conversation" type="icon-button" />
    </div>
    <div ref="chatBodyElementRef" class="chat-body custom-scrollbar">
      <a-spin :spinning="loading">
        <template v-for="(chatMessageGroup, groupIndex) in messages" :key="groupIndex">
          <div class="message-group">
            <ChatMessage
              v-for="currentMessage in [chatMessageGroup[messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)]]"
              :key="currentMessage.mid" :loading="currentMessage.loading" :cid="conversationId"
              :mid="currentMessage.mid" v-model:status="currentMessage.status" :authorType="currentMessage.author_type"
              :contentType="currentMessage.content_type" :createTime="currentMessage.create_time"
              :metadata="currentMessage.metadata" :content="currentMessage.content"
              :workflowInvokeStep="currentMessage.workflow_invoke_step" :attachments="currentMessage?.attachments"
              :agent="{ name: conversation.agent.name, avatar: conversation.agent.avatar }"
              @append-answer="onAppendAnswer" @regenerate="regenerate(currentMessage.mid, groupIndex)"
              @delete="deleteMessage(currentMessage.mid, groupIndex)" />

            <!-- 分页控件 -->
            <div v-if="chatMessageGroup.length > 1" class="message-pagination">
              <a-button type="text" size="small"
                :disabled="(messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)) === 0"
                @click="switchMessagePage(groupIndex, 'prev')">
                &lt;
              </a-button>
              <span class="page-indicator">
                {{ (messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)) + 1 }} / {{
                  chatMessageGroup.length }}
              </span>
              <a-button type="text" size="small"
                :disabled="(messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)) === chatMessageGroup.length - 1"
                @click="switchMessagePage(groupIndex, 'next')">
                &gt;
              </a-button>
            </div>
          </div>
        </template>
      </a-spin>
      <ScrollEndButton :target="chatBodyElementRef" direction="bottom" bottom="0" left="calc(50% - 16px)" />
    </div>
    <div class="chat-footer-input">
      <div class="chat-input-actions">
        <template v-if="!loading">
          <a-tooltip v-if="windowWidth < 768" :title="t('workspace.chatSpace.new_chat')">
            <a-button size="small" type="text" shape="round"
              @click="router.push({ name: 'conversationNew', params: { agentId } })">
              <template #icon>
                <Plus />
              </template>
            </a-button>
          </a-tooltip>
          <SettingsPopoverShow :key="conversationId" :settings="conversation.settings" />
          <WorkflowsPopoverShow :key="conversationId" :selectedFlows="selectedWorkflows" />
          <ModelSelectButton :key="conversationId" :cid="conversationId" v-model:model="conversation.model"
            v-model:modelProvider="conversation.model_provider" />
          <AudioReplySettingButton :key="conversationId" v-model:audioReply="conversation.settings.agent_audio_reply"
            v-model:audioVoice="conversation.settings.agent_audio_voice" />
        </template>
      </div>
      <div class="chat-input-area">
        <a-textarea v-model:value="userInput" :placeholder="t('workspace.chatSpace.textarea_tip')"
          :auto-size="{ minRows: 2, maxRows: 10 }" style="padding-right: 7rem;"
          @keyup.ctrl.enter="sendMessage(userInput)" />
        <RecordingButton class="chat-recording-btn" :transcribe="true" v-model:text="userInput"
          @finished="sendMessage" />
        <a-tooltip :title="t('workspace.chatSpace.upload_attachments')">
          <UploaderFieldUse class="chat-attachment-btn" v-model="attachments" supportFileTypes="*.*" :acceptPaste="true"
            :multiple="true" :showUploadList="false" :singleButton="true"
            :singleButtonProps="{ type: 'text', loading: sending, disabled: receiving }">
            <template #icon>
              <Link />
            </template>
          </UploaderFieldUse>
        </a-tooltip>
        <a-tooltip :title="t('workspace.chatSpace.send_message')">
          <a-button type="primary" class="chat-send-btn" :loading="sending"
            :disabled="userInput.length == 0 || receiving" @click="sendMessage(userInput)">
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
  border-bottom: var(--border-color);
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--component-background);
}

.main-container .chat-header .title-edit-button {
  opacity: 0;
}

.main-container .chat-header:hover .title-edit-button {
  opacity: 1;
  transition: opacity .3s;
}

.main-container .chat-body {
  flex: 1 1;
  overflow: auto;
  overflow-x: hidden;
  padding: 20px 20px 40px;
  position: relative;
  overscroll-behavior: none;
  background-color: var(--component-background);
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.main-container .chat-footer-input {
  position: relative;
  width: 100%;
  padding: 10px 20px 20px;
  box-sizing: border-box;
  border-top: var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 10px;
  background-color: var(--component-background);
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