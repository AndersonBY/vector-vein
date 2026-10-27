<script setup>
import { computed, ref, reactive, onBeforeMount, onBeforeUnmount, onMounted, nextTick, watch } from 'vue'
import { Send, Edit, Link, Plus, HandleSquare } from '@/icons'
import { message, theme } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { useUserChatsStore } from '@/stores/userChats'
import { useChatDraft } from '@/utils/useChatDraft'
import { createChatConnection, replaceChatMessage, terminalChatMessage } from '@/utils/chatConnection'
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
const { token } = theme.useToken()
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
const { userInput, attachments, draftOwner } = useChatDraft(agentId, conversationId)

const wsPort = ref(null)
const routeMid = () => typeof route.query.mid === 'string' ? route.query.mid : Array.isArray(route.query.mid) ? route.query.mid[0] || '' : ''
const clearSearchTarget = async () => {
  if (!routeMid()) return
  const query = { ...route.query }
  delete query.mid
  await router.replace({ query })
}
const focusedMessageMid = ref('')
let fetchVersion = 0
const forking = ref(false)
const forkingMid = ref('')
let forkVersion = 0

const applyConversation = data => {
  conversation.value = data.conversation
  userChatsStore.addConversation(conversation.value)
  messages.value = data.messages
  messagePagination.clear()
  const selectedPath = new Set(data.selected_message_path || [])
  messages.value.forEach((group, index) => {
    const selected = group.findIndex(item => selectedPath.has(item.mid))
    if (selected >= 0) messagePagination.set(index, selected)
  })
  focusedMessageMid.value = data.focused_message_mid || ''
  selectedWorkflows.workflows = {}
  selectedWorkflows.templates = {}
  conversation.value.related_workflows.forEach(workflow => { selectedWorkflows.workflows[workflow.wid] = workflow })
  conversation.value.related_templates.forEach(workflow => { selectedWorkflows.templates[workflow.tid] = workflow })
}

const fetchConversation = async (cid, mid = routeMid()) => {
  const version = ++fetchVersion
  focusedMessageMid.value = ''
  try {
    const res = await conversationAPI('get', { cid, ...(mid ? { mid } : {}) })
    if (disposed || version !== fetchVersion || cid !== conversationId.value) return false
    if (res.status !== 200) throw new Error('fetch failed')
    applyConversation(res.data)
    focusedMessageMid.value = res.data.focused_message_mid === mid ? mid : ''
    await nextTick()
    if (!disposed && version === fetchVersion) scrollToFocus()
    return true
  } catch {
    if (!disposed && version === fetchVersion && cid === conversationId.value) message.error(t('workspace.chatSpace.fetch_conversation_failed'))
    return false
  } finally {
    if (!disposed && version === fetchVersion && cid === conversationId.value) loading.value = false
  }
}

watch([() => route.params.conversationId, () => route.query.mid], async ([cid], [oldCid]) => {
  if (!cid) return
  if (cid !== oldCid) {
    forkVersion++
    forking.value = false
    cancelAttempt()
    conversationId.value = cid
    loading.value = true
    messages.value = []
    focusedMessageMid.value = ''
    if (await fetchConversation(cid)) await sendPendingChat(cid)
    return
  }
  const mid = routeMid()
  if (!mid) {
    focusedMessageMid.value = ''
    fetchVersion++
    if (loading.value) await fetchConversation(cid, '')
    return
  }
  // A search within this chat must not cancel an active reply.
  if (sending.value || receiving.value) {
    const groupIndex = messages.value.findIndex(group => group.some(item => item.mid === mid))
    const group = messages.value[groupIndex]
    if (group?.[messagePagination.get(groupIndex) ?? (group.length - 1)]?.mid === mid) {
      focusedMessageMid.value = mid
      await nextTick()
      scrollToFocus()
    }
    return
  }
  loading.value = true
  await fetchConversation(cid, mid)
})

const windowWidth = ref(window.innerWidth)
const updateWidth = () => {
  windowWidth.value = window.innerWidth
}

onBeforeMount(async () => {
  loading.value = true
  const fetched = await fetchConversation(conversationId.value)
  if (disposed || !fetched) return
  await sendPendingChat(conversationId.value)
  nextTick(() => {
    if (chatBodyElementRef.value) {
      chatBodyElementRef.value.addEventListener('scroll', handleScroll)
    }
  })
})

onBeforeUnmount(() => {
  disposed = true
  forkVersion++
  fetchVersion++
  cancelAttempt()
  if (chatBodyElementRef.value) {
    chatBodyElementRef.value.removeEventListener('scroll', handleScroll)
  }

  window.removeEventListener('resize', updateWidth)
})

onMounted(() => {
  window.addEventListener('resize', updateWidth)
})

const sending = ref(false)
const editingMid = ref('')
const conversation = ref({ settings: { agent_audio_reply: false } })
const messages = ref([])
const sendPendingChat = async cid => {
  const pending = userChatsStore.unsentChats.find(item => item.cid === cid && item.aid === agentId.value)
  if (!pending) return
  userChatsStore.clearUnsentChats(cid)
  // Recover the target draft before sending the one-time new-chat handoff.
  try {
    await userChatsStore.loadDraft(agentId.value, cid)
  } catch {
    message.error(t('workspace.chatSpace.draft_save_failed'))
    return
  }
  if (disposed || cid !== conversationId.value) return
  await sendMessage(pending.content, true, pending.attachments)
}
const canFork = computed(() => !!conversation.value.cid && conversation.value.cid === conversationId.value && !loading.value && !sending.value &&
  !receiving.value && !forking.value)

const forkConversation = async mid => {
  if (!canFork.value || disposed) return
  const selected = messages.value.flat().find(item => item.mid === mid)
  if (!selected || selected.author_type !== 'A' || ['P', 'G', 'R'].includes(selected.status)) return
  forking.value = true
  forkingMid.value = mid
  const version = ++forkVersion
  const cid = conversationId.value
  const current = () => !disposed && version === forkVersion && cid === conversationId.value
  try {
    const res = await conversationAPI('fork', {
      source_cid: cid,
      source_mid: mid,
      title: t('workspace.chatSpace.fork_title', { title: conversation.value.title }).slice(0, 512),
    })
    if (!current()) return
    if (res.status !== 200 || !res.data?.cid) {
      message.error(t(`workspace.chatSpace.${res.code === 'CONVERSATION_BUSY' ? 'fork_busy' : 'fork_failed'}`))
      return
    }
    await userChatsStore.saveDraft(agentId.value, res.data.cid, userInput.value, [...attachments.value])
    if (!current()) return
    await router.push({ name: 'conversationDetail', params: { agentId: agentId.value, conversationId: res.data.cid } })
  } catch {
    if (current()) message.error(t('workspace.chatSpace.fork_failed'))
  } finally {
    if (current()) forking.value = false
  }
}

const userScrolled = ref(false)

const chatBodyElementRef = ref(null)
const scrollToFocus = () => {
  const body = chatBodyElementRef.value
  if (!body) return
  const target = focusedMessageMid.value && Array.from(body.querySelectorAll('[data-message-mid]'))
    .find(element => element.dataset.messageMid === focusedMessageMid.value)
  if (target) {
    userScrolled.value = true
    body.scrollTo({ top: body.scrollTop + target.getBoundingClientRect().top - body.getBoundingClientRect().top -
      (body.clientHeight - target.offsetHeight) / 2 })
  } else navigateToElementBottom(body)
}

let chatConnection = null
let connectionSetupTimer = null
let attemptEpoch = 0
let disposed = false
let stopCurrentAttempt = null
const cancelAttempt = () => {
  const pending = aiMessage.mid !== 'tmp' && receiving.value
    ? { mid: aiMessage.mid, cid: conversationId.value, code: 'CHAT_CONNECTION_CLOSED',
        content: { text: aiMessage.content.text, reasoning_content: aiMessage.content.reasoning_content } } : null
  const stopRequested = stopping.value || aiMessage.status === 'C'
  attemptEpoch += 1
  chatConnection?.cancel()
  chatConnection = null
  clearTimeout(connectionSetupTimer)
  receiving.value = false
  sending.value = false
  editingMid.value = ''
  stopping.value = false
  stopCurrentAttempt = null
  if (pending) void messageAPI(stopRequested ? 'stop' : 'fail_notice', pending).catch(() => {})
  clearAiMessage()
}
const receiving = ref(false)
const stopping = ref(false)
const stopGeneration = () => {
  if (!receiving.value || stopping.value || disposed) return
  stopping.value = true
  if (chatConnection) chatConnection.requestStop()
  else void stopCurrentAttempt?.()
}
watch([sending, receiving], async ([isSending, isReceiving]) => {
  const mid = routeMid()
  if (!isSending && !isReceiving && !loading.value && mid) {
    loading.value = true
    await fetchConversation(conversationId.value, mid)
  }
})

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

const currentAttempt = epoch => !disposed && epoch === attemptEpoch
const applySnapshot = (epoch, mid, snapshot, allowAutoRun = true) => {
  if (!currentAttempt(epoch) || snapshot?.mid !== mid) return
  const current = messages.value.flat().find(message => message.mid === mid)
  if (!current || !['S', 'W', 'F', 'C'].includes(current.status)) return
  replaceChatMessage(messages.value, mid, { ...snapshot, loading: false,
    workflow_invoke_step: snapshot.status === 'W' && allowAutoRun ? 'wait_for_invoke' : '' })
}
const sendWebsocketMsg = async (msg, epoch, cid) => {
  const mid = msg.ai_message_mid
  let ended = false
  stopCurrentAttempt = async () => {
    if (!currentAttempt(epoch) || !receiving.value) return
    ended = true
    clearTimeout(connectionSetupTimer)
    chatConnection?.cancel()
    chatConnection = null
    Object.assign(aiMessage, terminalChatMessage(aiMessage, { status: 'C' }))
    try {
      const response = await messageAPI('stop', { mid, cid,
        content: { text: aiMessage.content.text, reasoning_content: aiMessage.content.reasoning_content } })
      if (!currentAttempt(epoch)) return
      if (response.status !== 200) throw new Error('stop save failed')
      applySnapshot(epoch, mid, response.data, false)
      receiving.value = false
      sending.value = false
      stopping.value = false
      stopCurrentAttempt = null
      clearAiMessage()
    } catch {
      if (currentAttempt(epoch)) {
        stopping.value = false
        message.error(t('workspace.chatSpace.stop_save_failed'))
      }
    }
  }
  const finish = async (data, failureCode) => {
    if (!currentAttempt(epoch) || ended) return
    ended = true
    clearTimeout(connectionSetupTimer)
    chatConnection?.cancel()
    chatConnection = null
    const partial = { text: aiMessage.content.text, reasoning_content: aiMessage.content.reasoning_content }
    const allowAutoRun = !stopping.value
    const snapshot = terminalChatMessage(aiMessage, data)
    if (!allowAutoRun) snapshot.workflow_invoke_step = ''
    replaceChatMessage(messages.value, mid, snapshot)
    receiving.value = false
    sending.value = false
    stopping.value = false
    stopCurrentAttempt = null
    clearAiMessage()
    if (typeof data.title === 'string' && data.title) {
      conversation.value.title = data.title
      userChatsStore.updateConversation(cid, 'title', data.title)
    }
    try {
      const response = await messageAPI(failureCode ? 'fail_notice' : 'done_notice', failureCode
        ? { mid, cid, code: failureCode, content: partial } : { mid })
      if (response.status === 200) applySnapshot(epoch, mid, response.data, allowAutoRun)
    } catch { /* Keep the terminal local result when persistence is unavailable. */ }
  }
  const fail = code => {
    if (!currentAttempt(epoch)) return
    if (stopping.value) return stopCurrentAttempt?.()
    return finish({ status: 'F', error: { code,
      message: t(`workspace.chatSpace.${code.toLowerCase()}`) } }, code)
  }
  try {
    if (wsPort.value === null) {
      connectionSetupTimer = setTimeout(() => { void fail('CHAT_TIMEOUT') }, 15000)
      const res = await settingAPI('get_port', { port_name: 'chat_ws_port' })
      if (!currentAttempt(epoch) || ended) return
      clearTimeout(connectionSetupTimer)
      if (res.status !== 200 || !res.data?.port) throw new Error('port unavailable')
      wsPort.value = res.data.port
    }
    if (!currentAttempt(epoch) || ended) return
    chatConnection = createChatConnection({
      url: `ws://localhost:${wsPort.value}/ws/chat/${cid}/`, payload: msg,
      onFailure: fail,
      onData: data => {
        if (!currentAttempt(epoch) || ended || (data.mid && data.mid !== mid)) return
        if (data.end) { void finish(data); return }
        aiMessage.loading = false
        aiMessage.status = 'G'
        if (data.workflow_invoke_step) {
          aiMessage.workflow_invoke_step = data.workflow_invoke_step
          aiMessage.content_type = 'WKF'
          if (data.selected_workflow) aiMessage.metadata.selected_workflow = data.selected_workflow
        } else if (data.tool_calls?.length > 0) {
          aiMessage.content_type = 'WKF'
          aiMessage.content.tool = data.tool_calls[0].function.name
        } else {
          aiMessage.workflow_invoke_step = ''
          aiMessage.content_type = 'TXT'
        }
        aiMessage.content.text += data.content ?? ''
        aiMessage.content.reasoning_content += data.reasoning_content ?? ''
        if (!userScrolled.value) nextTick(() => navigateToElementBottom(chatBodyElementRef.value))
      },
    })
  } catch { await fail('CHAT_CONNECTION_FAILED') }
}

const trimHistoryAfter = groupIndex => {
  messages.value.splice(groupIndex + 1)
  for (const index of messagePagination.keys()) if (index > groupIndex) messagePagination.delete(index)
}

const beginAssistant = (data, epoch, cid, groupIndex) => {
  clearAiMessage()
  aiMessage.mid = data.ai_message_mid
  receiving.value = true
  if (groupIndex === undefined) messages.value.push([aiMessage])
  else {
    trimHistoryAfter(groupIndex)
    const parentGroup = messages.value[groupIndex]
    messages.value[groupIndex] = [...parentGroup, aiMessage]
    messagePagination.set(groupIndex, parentGroup.length)
  }
  nextTick(() => navigateToElementBottom(chatBodyElementRef.value))
  void sendWebsocketMsg({ ...data, user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }, epoch, cid)
}

const sendMessage = async (content, needTitle = false, submittedFiles = attachments.value) => {
  if (!content?.trim() || loading.value || sending.value || receiving.value || forking.value || disposed) return false
  sending.value = true
  const epoch = ++attemptEpoch
  const cid = conversationId.value
  const files = [...submittedFiles]
  const aid = agentId.value
  const groupIndex = messages.value.findLastIndex(group => group.some(item => item.mid !== 'tmp'))
  const parentMid = messages.value[groupIndex]?.[messagePagination.get(groupIndex) ?? (messages.value[groupIndex].length - 1)]?.mid ?? null
  try {
    const res = await messageAPI('send', { need_title: needTitle, parent_mid: parentMid,
      cid, content, content_type: 'TXT', attachments: files })
    if (res.status === 200 && res.data?.ai_message_mid) {
      void userChatsStore.clearSubmittedDraft(aid, cid, content, files)
        .catch(() => message.error(t('workspace.chatSpace.draft_save_failed')))
    }
    if (!currentAttempt(epoch)) {
      if (res.status === 200) {
        void messageAPI('fail_notice', { cid, mid: res.data.ai_message_mid,
          code: 'CHAT_CONNECTION_CLOSED', content: { text: '', reasoning_content: '' } }).catch(() => {})
      }
      return false
    }
    if (res.status !== 200 || !res.data?.ai_message_mid) throw new Error('send failed')
    messages.value.push([{ loading: false, mid: res.data.user_message_mid, status: 'S', author_type: 'U',
      content_type: 'TXT', create_time: Date.now(), metadata: {}, content: { text: content }, attachments: files }])
    beginAssistant(res.data, epoch, cid)
    void clearSearchTarget().catch(() => {})
    return true
  } catch {
    if (currentAttempt(epoch)) message.error(t('workspace.chatSpace.send_message_failed'))
    return false
  } finally {
    if (currentAttempt(epoch)) sending.value = false
  }
}

const requestAssistant = async (action, mid, groupIndex, editedContent) => {
  if (loading.value || sending.value || receiving.value || forking.value || disposed) return
  const group = messages.value[groupIndex]
  const original = group?.[messagePagination.get(groupIndex) ?? (group.length - 1)]
  if (action === 'edit' && (!editedContent?.trim() || original?.mid !== mid || original.author_type !== 'U' ||
      original.content_type !== 'TXT' || original.status !== 'S')) return
  sending.value = true
  if (action === 'edit') editingMid.value = mid
  const epoch = ++attemptEpoch
  const cid = conversationId.value
  try {
    const res = await messageAPI(action, { cid, mid, ...(action === 'edit' ? { content: editedContent } : {}) })
    if (!currentAttempt(epoch)) {
      if (res.status === 200) void messageAPI('fail_notice', { cid, mid: res.data.ai_message_mid,
        code: 'CHAT_CONNECTION_CLOSED', content: { text: '', reasoning_content: '' } }).catch(() => {})
      return
    }
    if (res.status !== 200 || !res.data?.ai_message_mid || (action === 'edit' && !res.data.user_message_mid)) throw new Error('request failed')
    if (action === 'append_answer') {
      const parentIndex = messages.value.findIndex(group => group.some(item => item.mid === mid))
      if (parentIndex >= 0) trimHistoryAfter(parentIndex)
    }
    if (action === 'edit') {
      trimHistoryAfter(groupIndex)
      messages.value[groupIndex] = [...group, { ...original, mid: res.data.user_message_mid,
        content: { text: editedContent }, create_time: Date.now(), metadata: {} }]
      messagePagination.set(groupIndex, group.length)
      beginAssistant(res.data, epoch, cid)
    } else beginAssistant(res.data, epoch, cid, groupIndex)
    void clearSearchTarget().catch(() => {})
  } catch {
    if (currentAttempt(epoch)) message.error(t(`workspace.chatSpace.${action === 'edit' ? 'edit_message_failed' : 'regenerate_failed'}`))
  } finally {
    if (currentAttempt(epoch)) { sending.value = false; editingMid.value = '' }
  }
}
const onAppendAnswer = mid => requestAssistant('append_answer', mid)

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
    if (stopping.value) chatConnection.requestStop()

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
  const owner = draftOwner.value
  event.preventDefault()
  isDragging.value = false
  const items = event.dataTransfer.items
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.kind === 'file') {
      const { name } = item.getAsFile()
      window.pywebview.api.get_drop_file_path(name).then(dropFilePath => {
        if (disposed || owner !== draftOwner.value) return
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

const regenerate = (mid, groupIndex) => requestAssistant('regenerate', mid, groupIndex)
const editMessage = (mid, groupIndex, content) => requestAssistant('edit', mid, groupIndex, content)

const switchMessagePage = async (groupIndex, direction) => {
  if (loading.value || sending.value || receiving.value || forking.value || disposed) return
  const group = messages.value[groupIndex]
  if (!group) return
  const currentPage = messagePagination.get(groupIndex) ?? (group.length - 1) // 默认显示最后一项
  const newPage = direction === 'prev' ? currentPage - 1 : currentPage + 1
  if (newPage < 0 || newPage >= group.length) return
  const cid = conversationId.value
  const version = ++fetchVersion
  const current = () => !disposed && version === fetchVersion && cid === conversationId.value
  loading.value = true
  try {
    const res = await conversationAPI('select_branch', { cid, mid: group[newPage].mid })
    if (!current()) return
    if (res.status !== 200) throw new Error('branch selection failed')
    applyConversation(res.data)
    loading.value = false
    await clearSearchTarget()
  } catch {
    if (current()) message.error(t('workspace.chatSpace.branch_switch_failed'))
  } finally {
    if (current()) loading.value = false
  }
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
            <div
              v-for="currentMessage in [chatMessageGroup[messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)]]"
              :key="currentMessage.mid" :data-message-mid="currentMessage.mid" class="message-focus-target"
              :class="{ 'message-focused': focusedMessageMid === currentMessage.mid }"
              :style="{ '--message-focus-color': token.colorPrimary, '--message-focus-background': token.colorPrimaryBg }">
            <ChatMessage :loading="currentMessage.loading" :cid="conversationId"
              editable :edit-loading="editingMid === currentMessage.mid"
              forkable :fork-disabled="!canFork" :fork-loading="forking && forkingMid === currentMessage.mid"
              :mid="currentMessage.mid" :retry-disabled="loading || sending || receiving || forking" v-model:status="currentMessage.status" :authorType="currentMessage.author_type"
              :contentType="currentMessage.content_type" :createTime="currentMessage.create_time"
              :metadata="currentMessage.metadata" :content="currentMessage.content"
              :workflowInvokeStep="currentMessage.workflow_invoke_step" :attachments="currentMessage?.attachments"
              :agent="{ name: conversation.agent.name, avatar: conversation.agent.avatar }"
              @append-answer="onAppendAnswer" @regenerate="regenerate(currentMessage.mid, groupIndex)"
              @fork="forkConversation(currentMessage.mid)"
              @edit="editMessage(currentMessage.mid, groupIndex, $event)"
              @delete="deleteMessage(currentMessage.mid, groupIndex)" />
            </div>

            <!-- 分页控件 -->
            <div v-if="chatMessageGroup.length > 1" class="message-pagination"
              :class="{ 'message-pagination-user': chatMessageGroup[0]?.author_type === 'U' }">
              <a-button type="text" size="small"
                :disabled="loading || sending || receiving || forking || (messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)) === 0"
                @click="switchMessagePage(groupIndex, 'prev')">
                &lt;
              </a-button>
              <span class="page-indicator">
                {{ (messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)) + 1 }} / {{
                  chatMessageGroup.length }}
              </span>
              <a-button type="text" size="small"
                :disabled="loading || sending || receiving || forking || (messagePagination.get(groupIndex) ?? (chatMessageGroup.length - 1)) === chatMessageGroup.length - 1"
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
            v-model:modelProvider="conversation.model_provider" v-model:settings="conversation.settings" />
          <AudioReplySettingButton :key="conversationId" v-model:audioReply="conversation.settings.agent_audio_reply"
            v-model:audioVoice="conversation.settings.agent_audio_voice" />
        </template>
      </div>
      <div class="chat-input-area">
        <a-textarea v-model:value="userInput" :placeholder="t('workspace.chatSpace.textarea_tip')"
          :auto-size="{ minRows: 2, maxRows: 10 }" style="padding-right: 7rem;"
          @keyup.ctrl.enter="sendMessage(userInput)" />
        <RecordingButton :key="conversationId" class="chat-recording-btn" :transcribe="true" v-model:text="userInput"
          @finished="sendMessage" />
        <a-tooltip :title="t('workspace.chatSpace.upload_attachments')">
          <UploaderFieldUse :key="conversationId" class="chat-attachment-btn" v-model="attachments" supportFileTypes="*.*" :acceptPaste="true"
            :multiple="true" :showUploadList="false" :singleButton="true"
            :singleButtonProps="{ type: 'text', disabled: sending || receiving }">
            <template #icon>
              <Link />
            </template>
          </UploaderFieldUse>
        </a-tooltip>
        <a-tooltip v-if="receiving" :title="t('workspace.chatSpace.stop_generation')">
          <a-button type="primary" class="chat-send-btn" :aria-label="t('workspace.chatSpace.stop_generation')"
            :loading="stopping" :disabled="stopping" @click="stopGeneration">
            <template #icon><HandleSquare v-if="!stopping" theme="filled" /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-else :title="t('workspace.chatSpace.send_message')">
          <a-button type="primary" class="chat-send-btn" :loading="sending"
            :disabled="userInput.length == 0 || loading || sending || receiving || forking" @click="sendMessage(userInput)">
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
.message-pagination-user { display: flex; justify-content: flex-end; align-items: center; padding-right: 32px; }
.message-focus-target { scroll-margin: 20px; border-radius: 6px; }
.message-focused { outline: 2px solid var(--message-focus-color); outline-offset: 6px; background: var(--message-focus-background); }
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
  gap: 12px;
  flex-wrap: wrap;
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
